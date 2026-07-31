from __future__ import annotations

import math
from collections import defaultdict
from statistics import pstdev
from typing import Any, Iterable, Mapping

from .inventory_utils import (
    DEFAULT_PARAMETERS,
    add_months,
    as_float,
    booking_date,
    month_shift,
    normalize_article_key,
    parameter_number,
    round_up_to_vpe,
    sales_quantity,
)


def calculate_analysis(
    sales_rows: Iterable[Mapping[str, Any]],
    articles: Mapping[str, str] | None = None,
    vpe_by_article: Mapping[str, Mapping[str, Any] | float | int] | None = None,
    parameters: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {**DEFAULT_PARAMETERS, **dict(parameters or {})}
    rows = list(sales_rows)
    document_type = str(params["document_type"])
    months = max(1, int(parameter_number(params, "months_average", 3)))
    a_limit = parameter_number(params, "abc_a_threshold", 0.8)
    b_limit = parameter_number(params, "abc_b_threshold", 0.95)
    if not 0 < a_limit < b_limit <= 1:
        raise ValueError("ABC-Grenzen müssen 0 < A < B <= 1 erfüllen.")
    x_limit = parameter_number(params, "xyz_x_threshold", 0.5)
    y_limit = parameter_number(params, "xyz_y_threshold", 1)
    if not 0 <= x_limit < y_limit:
        raise ValueError("XYZ-Grenzen müssen 0 <= X < Y erfüllen.")

    dates = [day for row in rows if (day := booking_date(row)) is not None]
    stichtag = max(dates) if dates else None
    period_start = add_months(stichtag, -months) if stichtag else None
    total: dict[str, float] = defaultdict(float)
    recent: dict[str, float] = defaultdict(float)
    monthly: dict[str, dict[tuple[int, int], float]] = defaultdict(lambda: defaultdict(float))
    names = dict(articles or {})
    allowed_months = {month_shift(stichtag.year, stichtag.month, delta) for delta in (-2, -1, 0)} if stichtag else set()

    for row in rows:
        key = normalize_article_key(row.get("article_key") or row.get("article_no"))
        if not key:
            continue
        if row.get("description") and not names.get(key):
            names[key] = str(row["description"]).strip()
        quantity = sales_quantity(row, document_type)
        if quantity <= 0:
            continue
        total[key] += quantity
        day = booking_date(row)
        if not day or not stichtag:
            continue
        if period_start <= day <= stichtag:
            recent[key] += quantity
        if (day.year, day.month) in allowed_months and day <= stichtag:
            monthly[key][(day.year, day.month)] += quantity

    keys = set(names) | set(total) | set(recent)
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
        recent_sales = recent.get(key, 0)
        average_month = recent_sales / months
        values = [monthly[key].get(month_shift(stichtag.year, stichtag.month, delta), 0) for delta in (-2, -1, 0)] if stichtag else [0, 0, 0]
        xyz_average = sum(values) / 3
        deviation = pstdev(values)
        if xyz_average <= 0:
            variation = None
            xyz = None
            xyz_reason = "Keine Absatzdaten in den drei Stichtagsmonaten."
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
        results.append({
            "article_key": key,
            "description": names.get(key, ""),
            "stichtag": stichtag,
            "period_start": period_start,
            "sales_total": total.get(key, 0),
            "share": share,
            "cumulative_share": cumulative_share,
            "abc_class": klass,
            "sales_recent": recent_sales,
            "average_month": average_month,
            "sales_m2": values[0],
            "sales_m1": values[1],
            "sales_m0": values[2],
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
            "proposal_reason": "Kein Verkauf im betrachteten Durchschnittszeitraum." if average_month <= 0 else None,
        })

    counts: dict[str, int] = defaultdict(int)
    for row in results:
        counts[row["abc_class"]] += 1
        if row["xyz_class"]:
            counts[row["xyz_class"]] += 1
        if row["abcxyz"]:
            counts[row["abcxyz"]] += 1
    warnings = []
    if results and not counts["B"]:
        warnings.append("Die ABC-Analyse enthält keine B-Artikel.")
    if results and not counts["C"]:
        warnings.append("Die ABC-Analyse enthält keine C-Artikel.")
    if results and counts["A"] == len(results):
        warnings.append("Die ABC-Analyse enthält nur A-Artikel; Grenzwerte oder Datenbasis prüfen.")
    return results, {
        "stichtag": stichtag,
        "period_start": period_start,
        "overall_sales": grand_total,
        "counts": dict(counts),
        "warnings": warnings,
    }
