from __future__ import annotations

import base64
import io
import re
from datetime import date, datetime
from typing import Any, BinaryIO, Iterable

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.inventory_analysis import calculate_analysis
from app.inventory_utils import DEFAULT_PARAMETERS, as_float, normalize_article_key, parse_code_set

SHEETS = {
    "sales": "Artikelposten",
    "articles": "Artikel_Stamm",
    "current": "Lagerhaltungsdaten_IST",
    "current_export": "Lagerhaltungsdatenübersicht",
    "vpe": "VPE",
    "params": "Parameter",
}

ALIASES = {
    "article": ["Artikelnummer", "Artikelnr.", "Artikelnr", "Artikel-Nr.", "Nr.", "Nr", "Item No."],
    "variant": ["Variantencode", "Variant Code"],
    "procurement": ["Beschaffungsmethode", "Replenishment System", "Procurement Method"],
    "description": ["Beschreibung", "Artikelbeschreibung", "Description"],
    "date": ["Buchungsdatum", "Posting Date", "Datum"],
    "type": ["Belegart", "Document Type"],
    "qty": ["Menge", "Quantity"],
    "location": ["Lagerortcode", "Lagerort", "Location Code"],
    "vpe": ["VPE", "Verpackungseinheit", "Menge je VPE"],
    "stock": ["Lagerbestand", "Bestand", "Inventory", "Current Inventory"],
    "minimum": ["Mindestbestand", "Minimalbestand", "Minimum Inventory", "Sicherheitsbestand"],
    "order": ["Bestellmenge", "Order Quantity", "Bestelllosgröße"],
    "maximum": ["Maximalbestand", "Maximum Inventory"],
}


def canon(value: Any) -> str:
    text = str(value or "").strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "", text)


def sheet(workbook, name: str, required: bool = True) -> str | None:
    found = {canon(value): value for value in workbook.sheetnames}.get(canon(name))
    if not found and required:
        raise ValueError(f"Tabellenblatt fehlt: {name}")
    return found


def rows(workbook, name: str) -> tuple[list[str], list[dict[str, Any]]]:
    worksheet = workbook[name]
    iterator = worksheet.iter_rows(values_only=True)
    try:
        raw_headers = next(iterator)
    except StopIteration:
        return [], []
    headers = [str(value).strip() if value is not None else f"Spalte_{index + 1}" for index, value in enumerate(raw_headers)]
    data = [
        {headers[index]: row[index] if index < len(row) else None for index in range(len(headers))}
        for row in iterator
        if any(value not in (None, "") for value in row)
    ]
    return headers, data


def col(headers: list[str], key: str, required: bool = True) -> str | None:
    by_canonical = {canon(value): value for value in headers}
    for alias in ALIASES[key]:
        if canon(alias) in by_canonical:
            return by_canonical[canon(alias)]
    for alias in ALIASES[key]:
        alias_key = canon(alias)
        for header_key, original in by_canonical.items():
            if alias_key in header_key or header_key in alias_key:
                return original
    if required:
        raise ValueError(f"Spalte fehlt: {ALIASES[key][0]}")
    return None


def as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for date_format in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value.strip(), date_format).date()
            except ValueError:
                pass
    return None


def params(workbook) -> dict[str, Any]:
    output: dict[str, Any] = dict(DEFAULT_PARAMETERS)
    name = sheet(workbook, SHEETS["params"], False)
    if not name:
        return output
    mapping = {
        "belegart": "document_type",
        "monate": "months_average",
        "abcagrenze": "abc_a_threshold",
        "abcbgrenze": "abc_b_threshold",
        "xyzxgrenze": "xyz_x_threshold",
        "xyzygrenze": "xyz_y_threshold",
        "mindestfaktora": "minimum_factor_a",
        "mindestfaktorb": "minimum_factor_b",
        "mindestfaktorc": "minimum_factor_c",
        "bestellintervalla": "order_interval_a",
        "bestellintervallb": "order_interval_b",
        "bestellintervallc": "order_interval_c",
        "automatischelagerorte": "automatic_locations",
        "manuellelagerorte": "manual_locations",
    }
    for row in workbook[name].iter_rows(values_only=True):
        if not row or row[0] in (None, ""):
            continue
        key = mapping.get(canon(row[0]))
        value = row[1] if len(row) > 1 else None
        if not key:
            continue
        if key in {"document_type", "automatic_locations", "manual_locations"}:
            output[key] = str(value).strip()
        else:
            parsed = as_float(value)
            if parsed is not None:
                output[key] = parsed
    return output


def article_names(workbook) -> dict[str, str]:
    name = sheet(workbook, SHEETS["articles"], False)
    if not name:
        return {}
    headers, data = rows(workbook, name)
    article_column = col(headers, "article")
    description_column = col(headers, "description", False)
    output: dict[str, str] = {}
    for row in data:
        key = normalize_article_key(row.get(article_column))
        if key:
            output[key] = str(row.get(description_column) or "").strip() if description_column else ""
    return output


def vpe_values(workbook) -> dict[str, float]:
    name = sheet(workbook, SHEETS["vpe"], False)
    if not name:
        return {}
    headers, data = rows(workbook, name)
    article_column = col(headers, "article")
    vpe_column = col(headers, "vpe")
    output: dict[str, float] = {}
    for row in data:
        key = normalize_article_key(row.get(article_column))
        value = as_float(row.get(vpe_column))
        if key and value and value > 0:
            output[key] = value
    return output


def _current_sheet_candidates(workbook) -> list[str]:
    ordered: list[str] = []
    for preferred in (SHEETS["current_export"], SHEETS["current"]):
        found = sheet(workbook, preferred, False)
        if found and found not in ordered:
            ordered.append(found)
    for name in workbook.sheetnames:
        if name not in ordered:
            ordered.append(name)
    return ordered


def _location_priority(location: str, automatic: set[str], manual: set[str]) -> int:
    if location in automatic:
        return 0
    if location in manual:
        return 1
    return 2


def current_values(
    workbook,
    parameters: dict[str, Any],
    *,
    source_file: str,
    required: bool = False,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    automatic = parse_code_set(parameters.get("automatic_locations"))
    manual = parse_code_set(parameters.get("manual_locations"))
    output: dict[str, dict[str, Any]] = {}
    recognized_sheets: list[str] = []
    parsed_rows = 0

    for sheet_name in _current_sheet_candidates(workbook):
        headers, data = rows(workbook, sheet_name)
        if not headers:
            continue
        article_column = col(headers, "article", False)
        if not article_column:
            continue
        location_column = col(headers, "location", False)
        stock_column = col(headers, "stock", False)
        minimum_column = col(headers, "minimum", False)
        order_column = col(headers, "order", False)
        maximum_column = col(headers, "maximum", False)
        description_column = col(headers, "description", False)
        variant_column = col(headers, "variant", False)
        procurement_column = col(headers, "procurement", False)
        if not any((stock_column, minimum_column, order_column, maximum_column)):
            continue

        recognized_sheets.append(sheet_name)
        parsed_rows += len(data)
        for row in data:
            article_key = normalize_article_key(row.get(article_column))
            if not article_key:
                continue
            location = str(row.get(location_column) or "").strip().upper() if location_column else ""
            priority = _location_priority(location, automatic, manual)
            value = {
                "location": location,
                "manual_review": location in manual,
                "stock_current": as_float(row.get(stock_column)) if stock_column else None,
                "minimum_stock_current": as_float(row.get(minimum_column)) if minimum_column else None,
                "order_quantity_current": as_float(row.get(order_column)) if order_column else None,
                "maximum_stock_current": as_float(row.get(maximum_column)) if maximum_column else None,
                "description_current": str(row.get(description_column) or "").strip() if description_column else "",
                "variant_code_current": str(row.get(variant_column) or "").strip() if variant_column else "",
                "procurement_method_current": str(row.get(procurement_column) or "").strip() if procurement_column else "",
                "current_source_file": source_file,
                "current_source_sheet": sheet_name,
                "_priority": priority,
            }
            existing = output.get(article_key)
            if existing is None or priority <= existing["_priority"]:
                output[article_key] = value

    if required and not recognized_sheets:
        expected = "Artikelnr., Lagerortcode, Lagerbestand, Minimalbestand, Bestellmenge und Maximalbestand"
        raise ValueError(f"{source_file}: Keine erkennbare Lagerhaltungsdatenliste gefunden. Erwartete Spalten: {expected}.")

    return output, {
        "filename": source_file,
        "sheets": recognized_sheets,
        "rows": parsed_rows,
        "articles": len(output),
    }


def merge_current_values(
    target: dict[str, dict[str, Any]],
    incoming: dict[str, dict[str, Any]],
    *,
    override_equal_priority: bool,
) -> None:
    for article_key, value in incoming.items():
        existing = target.get(article_key)
        if existing is None:
            target[article_key] = value
            continue
        incoming_priority = value.get("_priority", 99)
        existing_priority = existing.get("_priority", 99)
        if incoming_priority < existing_priority or (override_equal_priority and incoming_priority == existing_priority):
            target[article_key] = value


def sales_values(workbook, parameters: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    headers, data = rows(workbook, sheet(workbook, SHEETS["sales"]))
    article_column = col(headers, "article")
    description_column = col(headers, "description", False)
    date_column = col(headers, "date")
    type_column = col(headers, "type")
    quantity_column = col(headers, "qty")
    output: list[dict[str, Any]] = []
    names: dict[str, str] = {}
    for row in data:
        article_key = normalize_article_key(row.get(article_column))
        day = as_date(row.get(date_column))
        quantity = as_float(row.get(quantity_column))
        description = str(row.get(description_column) or "").strip() if description_column else ""
        if article_key and description:
            names.setdefault(article_key, description)
        if article_key and day and quantity is not None:
            output.append({
                "article_key": article_key,
                "description": description,
                "booking_date": day,
                "document_type": str(row.get(type_column) or "").strip(),
                "quantity": quantity,
            })
    return output, names


def compare(current: float | None, proposed: float | None) -> tuple[str, float | None]:
    if current is None or proposed is None:
        return "unknown", None
    delta = float(proposed) - float(current)
    return ("ok" if abs(delta) < 1e-9 else "increase" if delta > 0 else "decrease"), delta


def _load_current_uploads(
    uploads: Iterable[tuple[str, BinaryIO]],
    parameters: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    merged: dict[str, dict[str, Any]] = {}
    infos: list[dict[str, Any]] = []
    for filename, file_object in uploads:
        workbook = load_workbook(file_object, data_only=True, read_only=True)
        values, info = current_values(workbook, parameters, source_file=filename, required=True)
        merge_current_values(merged, values, override_equal_priority=True)
        infos.append(info)
    return merged, infos


def analyse_workbook(
    file_object: BinaryIO,
    current_file_objects: Iterable[tuple[str, BinaryIO]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workbook = load_workbook(file_object, data_only=True, read_only=True)
    parameters = params(workbook)
    names = article_names(workbook)
    vpes = vpe_values(workbook)
    sales, sales_names = sales_values(workbook, parameters)
    names = {**sales_names, **names}

    current: dict[str, dict[str, Any]] = {}
    current_sources: list[dict[str, Any]] = []
    embedded_current, embedded_info = current_values(
        workbook,
        parameters,
        source_file="Analyse-Arbeitsmappe",
        required=False,
    )
    if embedded_info["sheets"]:
        merge_current_values(current, embedded_current, override_equal_priority=True)
        current_sources.append(embedded_info)

    external_uploads = list(current_file_objects or [])
    if external_uploads:
        external_current, external_infos = _load_current_uploads(external_uploads, parameters)
        merge_current_values(current, external_current, override_equal_priority=True)
        current_sources.extend(external_infos)

    for article_key, value in current.items():
        description = value.get("description_current")
        if description and not names.get(article_key):
            names[article_key] = description

    results, meta = calculate_analysis(sales, names, vpes, parameters)
    matched_current_articles = 0
    for result in results:
        current_row = current.get(result["article_key"], {})
        if current_row:
            matched_current_articles += 1
        result.update({
            "location": current_row.get("location", ""),
            "manual_review": bool(current_row.get("manual_review")),
            "stock_current": current_row.get("stock_current"),
            "minimum_stock_current": current_row.get("minimum_stock_current"),
            "order_quantity_current": current_row.get("order_quantity_current"),
            "maximum_stock_current": current_row.get("maximum_stock_current"),
            "variant_code_current": current_row.get("variant_code_current", ""),
            "procurement_method_current": current_row.get("procurement_method_current", ""),
            "current_source_file": current_row.get("current_source_file", ""),
            "current_source_sheet": current_row.get("current_source_sheet", ""),
        })
        result["minimum_stock_status"], result["minimum_stock_delta"] = compare(
            result["minimum_stock_current"], result["minimum_stock"]
        )
        result["order_quantity_status"], result["order_quantity_delta"] = compare(
            result["order_quantity_current"], result["order_quantity"]
        )
        result["xyz_class"] = result["xyz_class"] or "–"
        result["abcxyz"] = result["abcxyz"] or f'{result["abc_class"]}–'
        if result["manual_review"]:
            result["overall_status"] = "manual"
        elif not current_row:
            result["overall_status"] = "missing"
        elif result["minimum_stock_status"] == "ok" and result["order_quantity_status"] == "ok":
            result["overall_status"] = "ok"
        else:
            result["overall_status"] = "change"

    if not results:
        raise ValueError("Keine auswertbaren Verkaufsabgänge gefunden.")

    for value in current.values():
        value.pop("_priority", None)
    meta["parameters"] = parameters
    meta["current_sources"] = current_sources
    meta["external_current_files"] = len(external_uploads)
    meta["current_articles"] = len(current)
    meta["matched_current_articles"] = matched_current_articles
    return sorted(results, key=lambda row: (-row["sales_total"], row["article_key"])), meta


EXPORT = [
    ("article_key", "Artikelnummer"),
    ("description", "Beschreibung"),
    ("abc_class", "ABC"),
    ("xyz_class", "XYZ"),
    ("abcxyz", "ABCXYZ"),
    ("sales_total", "Absatz gesamt"),
    ("average_month", "Ø Absatz/Monat"),
    ("stock_current", "Lagerbestand IST"),
    ("minimum_stock", "Mindestbestand Vorschlag"),
    ("minimum_stock_current", "Minimalbestand IST"),
    ("minimum_stock_delta", "Delta Mindestbestand"),
    ("weekly_need", "Wochenbedarf"),
    ("order_interval", "Bestellintervall Wochen"),
    ("vpe", "VPE"),
    ("order_quantity", "Bestellmenge Vorschlag"),
    ("order_quantity_current", "Bestellmenge IST"),
    ("order_quantity_delta", "Delta Bestellmenge"),
    ("maximum_stock_current", "Maximalbestand IST"),
    ("location", "Lagerort"),
    ("variant_code_current", "Variantencode IST"),
    ("procurement_method_current", "Beschaffungsmethode IST"),
    ("current_source_file", "IST-Quelldatei"),
    ("overall_status", "Status"),
]


def build_export(results: list[dict[str, Any]], meta: dict[str, Any]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ABC_Analyse"
    worksheet.append([label for _, label in EXPORT])
    for result in results:
        worksheet.append([result.get(key) for key, _ in EXPORT])
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    summary = workbook.create_sheet("Zusammenfassung")
    summary.append(["Kennzahl", "Wert"])
    summary.append(["Stichtag", meta.get("stichtag")])
    summary.append(["Gesamtabsatz", meta.get("overall_sales")])
    summary.append(["IST-Artikel eingelesen", meta.get("current_articles")])
    summary.append(["IST-Artikel zugeordnet", meta.get("matched_current_articles")])
    summary.append(["Zusätzliche IST-Dateien", meta.get("external_current_files")])
    for key, value in sorted((meta.get("counts") or {}).items()):
        summary.append([f"Anzahl {key}", value])

    sources = workbook.create_sheet("IST_Quellen")
    sources.append(["Datei", "Blätter", "Datenzeilen", "Artikel"])
    for source in meta.get("current_sources") or []:
        sources.append([
            source.get("filename"),
            ", ".join(source.get("sheets") or []),
            source.get("rows"),
            source.get("articles"),
        ])

    parameter_sheet = workbook.create_sheet("Parameter")
    parameter_sheet.append(["Parameter", "Wert"])
    for key, value in (meta.get("parameters") or {}).items():
        parameter_sheet.append([key, value])

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    for current_sheet in workbook.worksheets:
        for cell in current_sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
        for cells in current_sheet.columns:
            current_sheet.column_dimensions[get_column_letter(cells[0].column)].width = min(
                max(max(len(str(cell.value or "")) for cell in cells) + 2, 10),
                38,
            )

    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def export_data_uri(results: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    encoded = base64.b64encode(build_export(results, meta)).decode("ascii")
    return "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64," + encoded
