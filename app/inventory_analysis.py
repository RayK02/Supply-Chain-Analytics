from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime
from statistics import pstdev
from typing import Any, Iterable, Mapping

from .inventory_utils import (
    DEFAULT_PARAMETERS,
    as_float,
    booking_date,
    month_shift,
    normalize_article_key,
    parameter_number,
    round_up_to_vpe,
    sales_components,
)


def _parameter_date(parameters: Mapping[str, Any], key: str) -> date | None:
    value = parameters.get(key)
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for date_format in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            pass
    raise ValueError(f"Ungültiges Datum für {key}: {value}")


def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _month_end(year: int, month: int) -> date:
    next_year, next_month = month_shift(year, month, 1)
    return date(next_year, next_month, 1) - date.resolution


def _is_month_end(value: date) -> bool:
    return value == _month_end(value.year, value.month)


def calculate_analysis(
    sales_rows: Iterable[Mapping[str, Any]],
    articles: Mapping[str, str] | None = None,
    vpe_by_article: Mapping[str, Mapping[str, Any] | float | int] | None = None,
    parameters: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {**DEFAULT_PARAMETERS, **dict(parameters or {})}
    rows = list(sales_rows)
    document_type = str(params["document_type"])
    return_document_types = params.get("return_document_types", "")
    months = int(parameter_number(params, "months_average", 3))
    if not 1 <= months <= 36:
        raise ValueError("Durchschnittsmonate müssen zwischen 1 und 36 liegen.")

    xyz_min_months = int(parameter_number(params, "xyz_min_months", 3))
    if not 3 <= xyz_min_months <= 36:
        raise ValueError("XYZ-Mindestmonate müssen zwischen 3 und 36 liegen.")

    a_limit = parameter_number(params, "abc_a_threshold", 0.8)
    b_limit = parameter_number(params, "abc_b_threshold", 0.95)
    if not 0 < a_limit < b_limit <= 1:
        raise ValueError("ABC-Grenzen müssen 0 < A < B <= 1 erfüllen.")
    x_limit = parameter_number(params, "xyz_x_threshold", 0.5)
    y_limit = parameter_number(params, "xyz_y_threshold", 1)
    if not 0 <= x_limit < y_limit:
        raise ValueError("XYZ-Grenzen müssen 0 <= X < Y erfüllen.")

    names = dict(articles or {})
    movements: list[tuple[str, date, float, float, float]] = []
    for row in rows:
        key = normalize_article_key(row.get("article_key") or row.get("article_no"))
        if not key:
            continue
        if row.get("description") and not names.get(key):
            names[key] = str(row["description"]).strip()
        day = booking_date(row)
        gross, returned, net = sales_components(row, document_type, return_document_types)
        if day is not None and (gross or returned or net):
            movements.append((key, day, gross, returned, net))

    dates = [day for _, day, _, _, _ in movements]
    data_start = min(dates) if dates else None
    data_end = max(dates) if dates else None
    requested_start = _parameter_date(params, "analysis_start_date")
    requested_end = _parameter_date(params, "analysis_end_date")
    analysis_start = requested_start or data_start
    analysis_end = requested_end or data_end
    if analysis_start and analysis_end and analysis_start > analysis_end:
        raise ValueError("Das Startdatum darf nicht nach dem Enddatum liegen.")

    # Only fully completed calendar months are used for demand, XYZ and proposals.
    average_end: date | None = None
    month_keys: list[tuple[int, int]] = []
    average_start: date | None = None
    partial_month_excluded = False
    if analysis_end:
        if _is_month_end(analysis_end):
            average_end = analysis_end
        else:
            previous_year, previous_month = month_shift(analysis_end.year, analysis_end.month, -1)
            average_end = _month_end(previous_year, previous_month)
            partial_month_excluded = True
        month_keys = [
            month_shift(average_end.year, average_end.month, delta)
            for delta in range(-(months - 1), 1)
        ]
        first_year, first_month = month_keys[0]
        average_start = _month_start(first_year, first_month)
    allowed_months = set(month_keys)

    total: dict[str, float] = defaultdict(float)
    gross_total: dict[str, float] = defaultdict(float)
    returns_total: dict[str, float] = defaultdict(float)
    monthly: dict[str, dict[tuple[int, int], float]] = defaultdict(lambda: defaultdict(float))
    active_keys: set[str] = set()
    rows_in_analysis = 0

    for key, day, gross, returned, net in movements:
        if analysis_start and day < analysis_start:
            continue
        if analysis_end and day > analysis_end:
            continue
        active_keys.add(key)
        total[key] += net
        gross_total[key] += gross
        returns_total[key] += returned
        rows_in_analysis += 1
        if (day.year, day.month) in allowed_months:
            monthly[key][(day.year, day.month)] += net

    # Master-data-only articles must not create phantom rows in the ABC analysis.
    keys = active_keys
    ranked = sorted(
        ((key, max(total.get(key, 0.0), 0.0)) for key in keys),
        key=lambda item: (-item[1], item[0]),
    )
    grand_total = sum(value for _, value in ranked)
    cumulative = 0.0
    abc: dict[str, tuple[str, float, float]] = {}

    for key, amount in ranked:
        share = amount / grand_total if grand_total else 0.0
        previous_cumulative = cumulative
        cumulative += share
        if amount <= 0:
            klass = "C"
        elif previous_cumulative < a_limit:
            klass = "A"
        elif previous_cumulative < b_limit:
            klass = "B"
        else:
            klass = "C"
        abc[key] = klass, share, cumulative

    factors = {
        klass: parameter_number(params, f"minimum_factor_{klass.lower()}", default)
        for klass, default in {"A": 3, "B": 2, "C": 2}.items()
    }
    intervals = {
        klass: parameter_number(params, f"order_interval_{klass.lower()}", default)
        for klass, default in {"A": 2, "B": 4, "C": 8}.items()
    }

    results: list[dict[str, Any]] = []
    for key in sorted(keys):
        klass, share, cumulative_share = abc.get(key, ("C", 0.0, 1.0 if grand_total else 0.0))
        values = [monthly[key].get(month_key, 0.0) for month_key in month_keys] if month_keys else []
        recent_sales = sum(values)
        average_month = recent_sales / months if months else 0.0
        deviation = pstdev(values) if values else 0.0

        if months < xyz_min_months:
            variation = None
            xyz = None
            xyz_reason = f"XYZ benötigt mindestens {xyz_min_months} Durchschnittsmonate."
        elif average_month <= 0:
            variation = None
            xyz = None
            xyz_reason = "Kein positiver Nettoabsatz im gewählten Durchschnittszeitraum."
        else:
            variation = deviation / average_month
            xyz = "X" if variation <= x_limit else ("Y" if variation <= y_limit else "Z")
            xyz_reason = None

        factor = factors[klass]
        minimum = math.ceil(average_month * factor) if average_month > 0 and factor >= 0 else None
        weekly = average_month * 12 / 52
        interval = intervals[klass]
        raw_order = weekly * interval if weekly > 0 and interval >= 0 else 0.0
        vpe = None
        if vpe_by_article and key in vpe_by_article:
            raw = vpe_by_article[key]
            vpe = as_float(raw.get("vpe")) if isinstance(raw, Mapping) else as_float(raw)
        order = round_up_to_vpe(raw_order, vpe) if raw_order > 0 else None

        legacy_values = ([0.0, 0.0, 0.0] + values)[-3:]
        results.append({
            "article_key": key,
            "description": names.get(key, ""),
            "stichtag": analysis_end,
            "period_start": average_start,
            "analysis_start": analysis_start,
            "analysis_end": analysis_end,
            "average_start": average_start,
            "average_end": average_end,
            "months_average": months,
            "sales_gross": gross_total.get(key, 0.0),
            "returns_total": returns_total.get(key, 0.0),
            "sales_total": total.get(key, 0.0),
            "share": share,
            "cumulative_share": cumulative_share,
            "abc_class": klass,
            "sales_recent": recent_sales,
            "average_month": average_month,
            "monthly_sales": values,
            "sales_m2": legacy_values[0],
            "sales_m1": legacy_values[1],
            "sales_m0": legacy_values[2],
            "standard_deviation": deviation,
            "variation_coefficient": variation,
            "xyz_class": xyz,
            "abcxyz": f"{klass}{xyz}" if xyz else None,
            "xyz_reason": xyz_reason,
            "minimum_factor": factor,
            "minimum_stock": minimum,
            "weekly_need": weekly,
            "order_interval": interval,
            "order_quantity_raw": raw_order,
            "vpe": vpe,
            "order_quantity": order,
            "proposal_reason": "Kein positiver Nettoabsatz im vollständigen Durchschnittszeitraum." if average_month <= 0 else None,
        })

    counts: dict[str, int] = defaultdict(int)
    for row in results:
        counts[row["abc_class"]] += 1
        if row["xyz_class"]:
            counts[row["xyz_class"]] += 1
        if row["abcxyz"]:
            counts[row["abcxyz"]] += 1

    warnings: list[str] = []
    if results and not counts["B"]:
        warnings.append("Die ABC-Analyse enthält keine B-Artikel.")
    if results and not counts["C"]:
        warnings.append("Die ABC-Analyse enthält keine C-Artikel.")
    if results and counts["A"] == len(results):
        warnings.append("Die ABC-Analyse enthält nur A-Artikel; Grenzwerte oder Datenbasis prüfen.")
    if months < xyz_min_months:
        warnings.append(f"Keine XYZ-Klassifizierung: mindestens {xyz_min_months} Durchschnittsmonate erforderlich.")
    if partial_month_excluded and analysis_end:
        warnings.append(
            f"Der angebrochene Monat bis {analysis_end:%d.%m.%Y} wurde für Durchschnitt, XYZ und Vorschläge ausgeschlossen."
        )
    if average_start and requested_start and requested_start > average_start:
        warnings.append(
            "Der gewählte Analysebeginn liegt innerhalb des Durchschnittsfensters. "
            "Davorliegende vollständige Monate werden als Absatz 0 berücksichtigt."
        )
    elif average_start and data_start and (data_start.year, data_start.month) > (average_start.year, average_start.month):
        warnings.append(
            "Die Quelldaten beginnen nach dem ersten benötigten Durchschnittsmonat. "
            "Fehlende frühere Monate werden als Absatz 0 berücksichtigt."
        )
    if analysis_end and data_end and analysis_end > data_end:
        warnings.append("Das gewählte Enddatum liegt nach der letzten vorhandenen Verkaufsbewegung.")

    return results, {
        "stichtag": analysis_end,
        "period_start": average_start,
        "analysis_start": analysis_start,
        "analysis_end": analysis_end,
        "average_start": average_start,
        "average_end": average_end,
        "months_average": months,
        "data_start": data_start,
        "data_end": data_end,
        "rows_in_analysis": rows_in_analysis,
        "overall_gross_sales": sum(gross_total.values()),
        "overall_returns": sum(returns_total.values()),
        "overall_sales": sum(total.values()),
        "abc_sales_basis": grand_total,
        "counts": dict(counts),
        "warnings": warnings,
    }
