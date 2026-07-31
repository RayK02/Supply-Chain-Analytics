from __future__ import annotations

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
    vpe_values,
)


_ALLOWED_OVERRIDES = {
    "months_average",
    "analysis_start_date",
    "analysis_end_date",
}


def _apply_analysis_settings(
    parameters: dict[str, Any],
    analysis_settings: Mapping[str, Any] | None,
) -> dict[str, Any]:
    output = dict(parameters)
    for key, value in dict(analysis_settings or {}).items():
        if key in _ALLOWED_OVERRIDES and value not in (None, ""):
            output[key] = value
    return output


def analyse_workbook(
    file_object: BinaryIO,
    current_file_objects: Iterable[tuple[str, BinaryIO]] | None = None,
    analysis_settings: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workbook = load_workbook(file_object, data_only=True, read_only=True)
    parameters = _apply_analysis_settings(params(workbook), analysis_settings)
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
    if meta.get("overall_sales", 0) <= 0:
        raise ValueError("Im gewählten Analysezeitraum wurden keine Verkaufsabgänge gefunden.")

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

    for value in current.values():
        value.pop("_priority", None)
    meta["parameters"] = parameters
    meta["current_sources"] = current_sources
    meta["external_current_files"] = len(external_uploads)
    meta["current_articles"] = len(current)
    meta["matched_current_articles"] = matched_current_articles
    return sorted(results, key=lambda row: (-row["sales_total"], row["article_key"])), meta
