from __future__ import annotations

import copy
import math
from typing import Any, BinaryIO, Iterable, Mapping

from openpyxl import load_workbook

from app.inventory_analysis import calculate_analysis
from inventory import (
    _load_current_uploads,
    article_names,
    compare,
    current_values,
    merge_current_values,
    params,
    sales_values,
    validate_xlsx_archive,
    vpe_values,
)

_ALLOWED_OVERRIDES = {
    "months_average",
    "xyz_months",
    "analysis_start_date",
    "analysis_end_date",
}


def _apply_analysis_settings(
    parameters: dict[str, Any],
    analysis_settings: Mapping[str, Any] | None,
) -> dict[str, Any]:
    output = dict(parameters)
    overridden: list[str] = []
    for key, value in dict(analysis_settings or {}).items():
        if key in _ALLOWED_OVERRIDES and value not in (None, ""):
            output[key] = value
            overridden.append(key)
    output["_web_overrides"] = ", ".join(overridden)
    return output


def _is_multiple(value: float, divisor: float) -> bool:
    if divisor <= 0:
        return True
    quotient = value / divisor
    return math.isclose(quotient, round(quotient), abs_tol=1e-9)


def _plausibility_messages(result: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    numeric_fields = {
        "Lagerbestand IST": result.get("stock_current"),
        "Minimalbestand IST": result.get("minimum_stock_current"),
        "Bestellmenge IST": result.get("order_quantity_current"),
        "Maximalbestand IST": result.get("maximum_stock_current"),
    }
    for label, value in numeric_fields.items():
        if value is not None and value < 0:
            messages.append(f"{label} ist negativ")

    maximum = result.get("maximum_stock_current")
    minimum_current = result.get("minimum_stock_current")
    minimum_proposed = result.get("minimum_stock")
    order_current = result.get("order_quantity_current")
    order_proposed = result.get("order_quantity")
    vpe = result.get("vpe")

    # In Business Central frequently 0 means that no maximum is used.
    if maximum is not None and maximum > 0:
        if minimum_current is not None and minimum_current > maximum:
            messages.append("Minimalbestand IST liegt über dem Maximalbestand IST")
        if minimum_proposed is not None and minimum_proposed > maximum:
            messages.append("Mindestbestand-Vorschlag liegt über dem Maximalbestand IST")
        if order_current is not None and order_current > maximum:
            messages.append("Bestellmenge IST liegt über dem Maximalbestand IST")
        if order_proposed is not None and order_proposed > maximum:
            messages.append("Bestellmengen-Vorschlag liegt über dem Maximalbestand IST")

    if order_current is not None and order_current > 0 and vpe and vpe > 0 and not _is_multiple(order_current, vpe):
        messages.append("Bestellmenge IST ist kein Vielfaches der VPE")
    if result.get("sales_total", 0) <= 0 and (minimum_current or order_current):
        messages.append("IST-Lagerparameter vorhanden, aber Nettoabsatz im Analysezeitraum ist nicht positiv")

    return messages


def _count_sentence(count: int, singular: str, plural: str) -> str:
    return singular.format(count=count) if count == 1 else plural.format(count=count)


def prepare_analysis_workbook(
    file_object: BinaryIO,
    analysis_settings: Mapping[str, Any] | None = None,
    *,
    source_filename: str = "Analyse-Arbeitsmappe",
) -> dict[str, Any]:
    """Parse and calculate the analysis workbook without persisting uploaded data.

    The returned payload contains only normalized/aggregated Python data and can be
    compressed into a short-lived browser token. External IST workbooks can then be
    added one request at a time without relying on server memory or a database.
    """

    validate_xlsx_archive(file_object, "Analyse-Arbeitsmappe")
    workbook = load_workbook(file_object, data_only=True, read_only=True)
    parameters = _apply_analysis_settings(params(workbook), analysis_settings)
    names = article_names(workbook, parameters)
    vpes = vpe_values(workbook, parameters)
    sales, sales_names, sales_import = sales_values(workbook, parameters)
    names = {**sales_names, **names}

    current: dict[str, dict[str, Any]] = {}
    current_sources: list[dict[str, Any]] = []
    embedded_current, embedded_info = current_values(
        workbook,
        parameters,
        source_file="Analyse-Arbeitsmappe",
        required=False,
        scan_all_sheets=False,
    )
    if embedded_info["sheets"]:
        merge_current_values(current, embedded_current, override_equal_priority=True)
        current_sources.append(embedded_info)

    results, meta = calculate_analysis(sales, names, vpes, parameters)
    if meta.get("abc_sales_basis", 0) <= 0:
        raise ValueError("Im gewählten Analysezeitraum wurden keine positiven Netto-Verkaufsabgänge gefunden.")

    return {
        "results": results,
        "meta": meta,
        "parameters": parameters,
        "sales_import": sales_import,
        "current": current,
        "current_sources": current_sources,
        "external_current_files": 0,
        "source_filename": source_filename,
        "current_filenames": [],
    }


def add_current_workbook(
    payload: dict[str, Any],
    filename: str,
    file_object: BinaryIO,
) -> dict[str, Any]:
    parameters = payload["parameters"]
    values, infos = _load_current_uploads([(filename, file_object)], parameters)
    merge_current_values(payload["current"], values, override_equal_priority=True)
    payload["current_sources"].extend(infos)
    payload["external_current_files"] = int(payload.get("external_current_files", 0)) + 1
    payload["current_filenames"].append(filename)
    return payload


def finalize_prepared_analysis(payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results = copy.deepcopy(list(payload["results"]))
    meta = copy.deepcopy(dict(payload["meta"]))
    parameters = copy.deepcopy(dict(payload["parameters"]))
    sales_import = copy.deepcopy(dict(payload["sales_import"]))
    current = copy.deepcopy(dict(payload["current"]))
    current_sources = copy.deepcopy(list(payload["current_sources"]))

    matched_current_articles = 0
    validation_count = 0
    missing_vpe_count = 0
    for result in results:
        current_row = current.get(result["article_key"], {})
        if current_row:
            matched_current_articles += 1
            if not result.get("description") and current_row.get("description_current"):
                result["description"] = current_row["description_current"]
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
        result["vpe_missing"] = bool(
            result.get("order_quantity") is not None
            and result.get("order_quantity", 0) > 0
            and (result.get("vpe") is None or result.get("vpe", 0) <= 0)
        )
        if result["vpe_missing"]:
            missing_vpe_count += 1

        result["validation_messages"] = _plausibility_messages(result)
        result["validation_text"] = "; ".join(result["validation_messages"])
        if result["validation_messages"]:
            validation_count += 1

        if result["manual_review"] or result["validation_messages"]:
            result["overall_status"] = "manual"
        elif not current_row:
            result["overall_status"] = "missing"
        elif result["minimum_stock_status"] == "ok" and result["order_quantity_status"] == "ok":
            result["overall_status"] = "ok"
        else:
            result["overall_status"] = "change"

    for value in current.values():
        value.pop("_priority", None)

    warnings = list(meta.get("warnings") or [])
    if sales_import["invalid_article_rows"]:
        warnings.append(_count_sentence(
            sales_import["invalid_article_rows"],
            "{count} Artikelposten-Zeile wurde wegen einer ungültigen Artikelnummer verworfen.",
            "{count} Artikelposten-Zeilen wurden wegen ungültiger Artikelnummern verworfen.",
        ))
    if sales_import["invalid_date_rows"]:
        warnings.append(_count_sentence(
            sales_import["invalid_date_rows"],
            "{count} Artikelposten-Zeile enthält kein gültiges Buchungsdatum.",
            "{count} Artikelposten-Zeilen enthalten kein gültiges Buchungsdatum.",
        ))
    if sales_import["invalid_quantity_rows"]:
        warnings.append(_count_sentence(
            sales_import["invalid_quantity_rows"],
            "{count} Artikelposten-Zeile enthält keine gültige Menge.",
            "{count} Artikelposten-Zeilen enthalten keine gültige Menge.",
        ))
    invalid_current_rows = sum(source.get("invalid_article_rows", 0) for source in current_sources)
    if invalid_current_rows:
        warnings.append(_count_sentence(
            invalid_current_rows,
            "{count} IST-Zeile wurde wegen einer ungültigen Artikelnummer verworfen.",
            "{count} IST-Zeilen wurden wegen ungültiger Artikelnummern verworfen.",
        ))
    if parameters.get("_parameter_ignored"):
        ignored = [part.strip() for part in str(parameters["_parameter_ignored"]).split(",") if part.strip()]
        warnings.append(_count_sentence(
            len(ignored),
            f"1 Parameter wurde nicht erkannt: {parameters['_parameter_ignored']}.",
            f"{len(ignored)} Parameter wurden nicht erkannt: {parameters['_parameter_ignored']}.",
        ))
    if missing_vpe_count:
        warnings.append(_count_sentence(
            missing_vpe_count,
            "Für {count} Artikel fehlt die VPE; die Bestellmenge wurde auf ganze Stück aufgerundet.",
            "Für {count} Artikel fehlt die VPE; die Bestellmengen wurden auf ganze Stück aufgerundet.",
        ))
    if validation_count:
        warnings.append(_count_sentence(
            validation_count,
            "{count} Artikel benötigt eine Plausibilitätsprüfung.",
            "{count} Artikel benötigen eine Plausibilitätsprüfung.",
        ))

    meta["warnings"] = warnings
    meta["parameters"] = parameters
    meta["sales_import"] = sales_import
    meta["current_sources"] = current_sources
    meta["external_current_files"] = int(payload.get("external_current_files", 0))
    meta["current_articles"] = len(current)
    meta["matched_current_articles"] = matched_current_articles
    meta["validation_count"] = validation_count
    meta["missing_vpe_count"] = missing_vpe_count
    return sorted(results, key=lambda row: (-max(row["sales_total"], 0), row["article_key"])), meta


def analyse_workbook(
    file_object: BinaryIO,
    current_file_objects: Iterable[tuple[str, BinaryIO]] | None = None,
    analysis_settings: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = prepare_analysis_workbook(file_object, analysis_settings)
    for filename, current_file in list(current_file_objects or []):
        add_current_workbook(payload, filename, current_file)
    return finalize_prepared_analysis(payload)
