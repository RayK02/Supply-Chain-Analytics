from __future__ import annotations


def comparison_status(current: float, proposed: float) -> str:
    if current == proposed:
        return "OK"
    if proposed > current:
        return "increase"
    return "decrease"
