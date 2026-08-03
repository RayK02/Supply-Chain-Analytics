from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Mapping

DEFAULT_PARAMETERS: dict[str, str] = {
    "document_type": "Verkaufslieferung",
    "return_document_types": "Verkaufsrücksendung,Verkaufsgutschrift,Gutschrift",
    "months_average": "3",
    "xyz_months": "12",
    "abc_a_threshold": "0.80",
    "abc_b_threshold": "0.95",
    "xyz_x_threshold": "0.50",
    "xyz_y_threshold": "1.00",
    "xyz_min_months": "3",
    "minimum_factor_a": "3",
    "minimum_factor_b": "2",
    "minimum_factor_c": "2",
    "order_interval_a": "2",
    "order_interval_b": "4",
    "order_interval_c": "8",
    "automatic_locations": "FERTIG",
    "manual_locations": "AUSTAUSCH,DEFEKT,ERSATZ",
    "max_import_rows": "100000",
}

PARAMETER_META: dict[str, tuple[str, str]] = {
    "document_type": ("Belegart", "Diese Belegart wird als Verkaufsbewegung berücksichtigt."),
    "return_document_types": ("Rückgabebelegarten", "Kommagetrennte Belegarten, die als Rücklauf vom Absatz abgezogen werden."),
    "months_average": ("Durchschnittsmonate", "Anzahl vollständig abgedeckter Kalendermonate für Ø Absatz und Mindestbestand."),
    "xyz_months": ("XYZ-Monate", "Separater Zeitraum für die XYZ-Klassifizierung."),
    "abc_a_threshold": ("ABC A Grenze", "Kumulierte Absatzgrenze für A-Artikel."),
    "abc_b_threshold": ("ABC B Grenze", "Kumulierte Absatzgrenze für B-Artikel; der Rest ist C."),
    "xyz_x_threshold": ("XYZ X Grenze", "Bis zu diesem Variationskoeffizienten gilt ein Artikel als X."),
    "xyz_y_threshold": ("XYZ Y Grenze", "Bis zu diesem Variationskoeffizienten gilt ein Artikel als Y; darüber Z."),
    "xyz_min_months": ("XYZ Mindestmonate", "Mindestanzahl vollständig abgedeckter Monate für eine XYZ-Klassifizierung."),
    "minimum_factor_a": ("Mindestfaktor A", "Mindestbestand für A = Ø Monatsabsatz × Faktor."),
    "minimum_factor_b": ("Mindestfaktor B", "Mindestbestand für B = Ø Monatsabsatz × Faktor."),
    "minimum_factor_c": ("Mindestfaktor C", "Mindestbestand für C = Ø Monatsabsatz × Faktor."),
    "order_interval_a": ("Bestellintervall A", "Bestellintervall für A-Artikel in Wochen."),
    "order_interval_b": ("Bestellintervall B", "Bestellintervall für B-Artikel in Wochen."),
    "order_interval_c": ("Bestellintervall C", "Bestellintervall für C-Artikel in Wochen."),
    "automatic_locations": ("Automatische Lagerorte", "Kommagetrennte Lagerorte für automatische IST-Bewertung."),
    "manual_locations": ("Manuelle Lagerorte", "Kommagetrennte Sonderlagerorte für manuelle Prüfung."),
    "max_import_rows": ("Maximale Importzeilen", "Wirksame Zeilengrenze pro Tabellenblatt; maximal 100'000."),
    "analysis_start_date": ("Startdatum", "Erster eingeschlossener Tag der Analyse."),
    "analysis_end_date": ("Enddatum", "Letzter eingeschlossener Tag der Analyse."),
}

PARAMETER_EXPORT_NAMES: dict[str, str] = {
    key: label for key, (label, _description) in PARAMETER_META.items()
}

_ARTICLE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._/+\-]*$")


def display_article_key(value: Any) -> str | None:
    """Return a cleaned ERP article identifier while preserving its letter case."""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return None
        text = str(int(value))
    else:
        text = re.sub(r"\s+", "", str(value).strip())
        if not text:
            return None

    canonical = text.upper()
    if len(text) > 64 or not _ARTICLE_PATTERN.fullmatch(canonical):
        return None
    if text.isdigit() and len(text) < 6:
        return text.zfill(6)
    return text


def normalize_article_key(value: Any) -> str | None:
    """Return a case-insensitive internal key without reinterpreting text as a number."""

    display = display_article_key(value)
    return display.upper() if display is not None else None


def as_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip().replace("'", "")
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def parameter_number(parameters: Mapping[str, Any], key: str, default: float) -> float:
    value = as_float(parameters.get(key))
    return default if value is None else value


def parse_code_set(value: Any) -> set[str]:
    return {part.strip().upper() for part in str(value or "").split(",") if part.strip()}


def parse_document_types(value: Any) -> set[str]:
    return {part.strip().casefold() for part in str(value or "").split(",") if part.strip()}


def add_months(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return date(year, month, min(value.day, (next_month - date.resolution).day))


def month_shift(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + delta
    y, m0 = divmod(index, 12)
    return y, m0 + 1


def booking_date(row: Mapping[str, Any]) -> date | None:
    value = row.get("booking_date")
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def sales_components(
    row: Mapping[str, Any],
    document_type: str,
    return_document_types: Any = None,
) -> tuple[float, float, float]:
    """Return gross outbound, signed net returns and signed net demand.

    Positive quantities on return document types reduce demand. A negative return
    quantity is treated as a correction/reversal and therefore increases demand.
    The identity is always: net demand = gross outbound - net returns.
    """

    quantity = as_float(row.get("quantity"))
    if quantity is None or quantity == 0:
        return 0.0, 0.0, 0.0

    current_type = str(row.get("document_type") or "").strip().casefold()
    sales_type = str(document_type or "").strip().casefold()
    return_types = parse_document_types(return_document_types)

    if current_type == sales_type:
        if quantity < 0:
            gross = -quantity
            return gross, 0.0, gross
        return 0.0, quantity, -quantity

    if current_type in return_types:
        return 0.0, quantity, -quantity

    return 0.0, 0.0, 0.0


def sales_quantity(
    row: Mapping[str, Any],
    document_type: str,
    return_document_types: Any = None,
) -> float:
    return sales_components(row, document_type, return_document_types)[2]


def round_up_to_vpe(value: float, vpe: float | None) -> int:
    if value <= 0:
        return 0
    if vpe is None or vpe <= 0:
        return math.ceil(value)
    return int(math.ceil(value / vpe) * vpe)
