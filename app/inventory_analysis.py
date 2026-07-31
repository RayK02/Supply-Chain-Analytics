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
    sales_quantity,
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


def calculate_analysis(
    sales_rows: Iterable[Mapping[str, Any]],
    articles: Mapping[str, str] | None = None,
    vpe_by_article: Mapping[str, Mapping[str, Any] | float | int] | None = None,
    parameters: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {**DEFAULT_PARAMETERS, **dict(parameters or {})}
    rows = list(sales_rows)
    document_type = str(params["document_type"])
    months = int(parameter_number(params, "months_average", 3))
    if not 1 <= months <= 36:
        raise ValueError("Durchschnittsmonate müssen zwischen 1 und 36 liegen.")

    a_limit = parameter_number(params, "abc_a_threshold", 0.8)
    b_limit = parameter_number(params, "abc_b_threshold", 0.95)
    if not 0 < a_limit < b_limit <= 1:
        raise ValueError("ABC-Grenzen müssen 0 < A < B <= 1 erfüllen.")
    x_limit = parameter_number(params, "xyz_x_threshold", 0.5)
    y_limit = parameter_number(params, "xyz_y_threshold", 1)
    if not 0 <= x_limit < y_limit:
        raise ValueError("XYZ-Grenzen müssen 0 <= X < Y erfüllen.")

    names = dict(articles or {})
    valid_sales: list[tuple[str, date, float]] = []
    for row in rows:
        key = normalize_article_key(row.get("article_key") or row.get("article_no"))
        if not key:
            continue
        if row.get("description") and not names.get(key):
            names[key] = str(row["description"]).strip()
        day = booking_date(row)
        quantity = sales_quantity(row, document_type)
        if day is not None and quantity > 0:
            valid_sales.append((key, day, quantity))

    dates = [day for _, day, _ in valid_sales]
    data_start = min(dates) if dates else None
    data_end = max(dates) if dates else None
    analysis_start = _parameter_date(params, "analysis_start_date") or data_start
    analysis_end = _parameter_date(params, "analysis_end_date") or data_end
    if analysis_start and analysis_end and analysis_start > analysis_end:
        raise ValueError("Das Startdatum darf nicht nach dem Enddatum liegen.")

    month_keys: list[tuple[int, int]] = []
    average_start = None
    if analysis_end:
        month_keys = [
            month_shift(analysis_end.year, analysis_end.month, delta)
            for delta in range(-(months - 1), 1)
        ]
        first_year, first_month = month_keys[0]
        average_start = _month_start(first_year, first_month)
    allowed_months = set(month_keys)

    total: dict[str, float] = defaultdict(float)
    monthly: dict[str, dict[tuple[int, int], float]] = defaultdict(lambda: defaultdict(float))
    rows_in_analysis = 0
    for key, day, quantity in valid_sales:
        if analysis_start and day < analysis_start:
            continue
        if analysis_end and day > analysis_end:
            continue
        total[key] += quantity
        rows_in_analysis += 1
        if (day.year, day.month) in allowed_months:
            monthly[key][(day.year, day.month)] += quantity

    keys = set(names) | set(total) | set(monthly)
    ranked = sorted(((key, total.get(key, 0)) for key in keys), key=lambda item: (-item[1], item[0]))
    grand_total = sum(value for _, value in ranked)
    cumulative = 0.0
    abc: dict[str, tuple[str, float, float]] = {}

    # Die Klasse richtet sich nach dem kumulierten Anteil VOR dem aktuellen Artikel.
    # Dadurch bleibt der umsatzstärkste Artikel A, auch wenn er die A-Grenze alleine überschreitet.
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
        klass, share, cumulative_share = abc.get(key, ("C", 0, 1 if grand_total else 0))
        values = [monthly[key].get(month_key, 0) for month_key in month_keys] if month_keys else []
        recent_sales = sum(values)
        average_month = recent_sales / months
        xyz_average = average_month
        deviation = pstdev(values) if values else 0.0
        if xyz_average <= 0:
            variation = None
            xyz = None
            xyz_reason = "Keine Absatzdaten im gewählten Durchschnittszeitraum."
        else:
            variation = deviation / xyz_average
            xyz = "X" if variation <= x_limit else ("Y" if variation <= y_limit else "Z")
            xyz_reason = None

        factor = factors[klass]
        minimum = math.ceil(average_month * factor) if average_month > 0 and factor >= 0 else None
        weekly = average_month * 12 / 52
        interval = intervals[klass]
        raw_order = weekly * interval if weekly > 0 and interval >= 0 else 0
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
            "average_end": analysis_end,
            "months_average": months,
            "sales_total": total.get(key, 0),
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
            "proposal_reason": "Kein Verkauf im gewählten Durchschnittszeitraum." if average_month <= 0 else None,
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
    if average_start and analysis_start and analysis_start > average_start:
        warnings.append(
            "Der Analysebeginn liegt innerhalb des Durchschnittsfensters. "
            "Der davorliegende Teil wird als Absatz 0 berücksichtigt."
        )
    if average_start and data_start and data_start > average_start:
        warnings.append(
            "Die Quelldaten beginnen nach dem Start des Durchschnittsfensters. "
            "Fehlende frühere Monate werden als Absatz 0 berücksichtigt."
        )
    if analysis_end and data_end and analysis_end > data_end:
        warnings.append("Das gewählte Enddatum liegt nach dem letzten vorhandenen Verkaufsabgang.")

    return results, {
        "stichtag": analysis_end,
        "period_start": average_start,
        "analysis_start": analysis_start,
        "analysis_end": analysis_end,
        "average_start": average_start,
        "average_end": analysis_end,
        "months_average": months,
        "data_start": data_start,
        "data_end": data_end,
        "rows_in_analysis": rows_in_analysis,
        "overall_sales": grand_total,
        "counts": dict(counts),
        "warnings": warnings,
    }
