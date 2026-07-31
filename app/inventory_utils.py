from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Mapping

DEFAULT_PARAMETERS: dict[str, str] = {
    "document_type": "Verkaufslieferung",
    "return_document_types": "Verkaufsrücksendung,Verkaufsgutschrift,Gutschrift",
    "months_average": "3",
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
    "return_document_types": ("Belegarten", "Kommagetrennte Belegarten, die als Rücklauf vom Absatz abgezogen werden."),
    "months_average": ("Monate", "Anzahl vollständig abgeschlossener Kalendermonate für Ø Absatz und Mindestbestand."),
    "abc_a_threshold": ("Anteil", "Kumulierte Absatzgrenze für A-Artikel."),
    "abc_b_threshold": ("Anteil", "Kumulierte Absatzgrenze für B-Artikel; der Rest ist C."),
    "xyz_x_threshold": ("VK", "Bis zu diesem Variationskoeffizienten gilt ein Artikel als X."),
    "xyz_y_threshold": ("VK", "Bis zu diesem Variationskoeffizienten gilt ein Artikel als Y; darüber Z."),
    "xyz_min_months": ("Monate", "Mindestanzahl Monate für eine belastbare XYZ-Klassifizierung."),
    "minimum_factor_a": ("Monate", "Mindestbestand für A = Ø Monatsabsatz × Faktor."),
    "minimum_factor_b": ("Monate", "Mindestbestand für B = Ø Monatsabsatz × Faktor."),
    "minimum_factor_c": ("Monate", "Mindestbestand für C = Ø Monatsabsatz × Faktor."),
    "order_interval_a": ("Wochen", "Bestellintervall für A-Artikel."),
    "order_interval_b": ("Wochen", "Bestellintervall für B-Artikel."),
    "order_interval_c": ("Wochen", "Bestellintervall für C-Artikel."),
    "automatic_locations": ("Codes", "Kommagetrennte Lagerorte für automatische IST-Bewertung."),
    "manual_locations": ("Codes", "Kommagetrennte Sonderlagerorte für manuelle Prüfung."),
    "max_import_rows": ("Zeilen", "Sicherheitsgrenze pro Tabellenblatt."),
}

_ARTICLE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._/+\-]*$")


def normalize_article_key(value: Any) -> str | None:
    """Normalize an ERP article identifier without interpreting text as a number.

    Text values retain letters and common ERP separators. Numeric Excel cells are
    converted to an integer string; short purely numeric identifiers are padded to
    six characters to remain compatible with the existing Business Central files.
    """

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return None
        text = str(int(value))
    else:
        text = re.sub(r"\s+", "", str(value).strip()).upper()
        if not text:
            return None

    if len(text) > 64 or not _ARTICLE_PATTERN.fullmatch(text):
        return None
    if text.isdigit() and len(text) < 6:
        return text.zfill(6)
    return text


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
    """Return gross outbound, returns and signed net demand for one ledger row."""

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
        # Positive reversal/return posted under the sales document type.
        return 0.0, quantity, -quantity

    if current_type in return_types:
        returned = abs(quantity)
        return 0.0, returned, -returned

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
