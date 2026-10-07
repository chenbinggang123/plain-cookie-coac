from __future__ import annotations

from typing import Any


AGENTIC_DEFAULTS: dict[str, Any] = {
    "max_rounds": 2,
    "max_dimensions": 6,
    "semantic_top_k": 12,
    "semantic_min_score": 0.35,
    "semantic_relative_drop": 0.18,
    "semantic_min_keep": 5,
    "max_per_source": 3,
    "wiki_max_hops": 1,
    "wiki_max_nodes": 12,
    "final_evidence": 10,
    "token_budget": 6000,
    "answer_max_chars": 800,
}


def resolve_agentic_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    values = dict(AGENTIC_DEFAULTS)
    if not payload:
        return values
    integer_fields = {
        "max_rounds": (1, 3),
        "max_dimensions": (4, 8),
        "semantic_top_k": (5, 30),
        "semantic_min_keep": (1, 8),
        "max_per_source": (1, 5),
        "wiki_max_hops": (0, 2),
        "wiki_max_nodes": (2, 24),
        "final_evidence": (4, 16),
        "token_budget": (1200, 16000),
        "answer_max_chars": (200, 3000),
    }
    float_fields = {
        "semantic_min_score": (0.0, 1.0),
        "semantic_relative_drop": (0.0, 1.0),
    }
    for name, (low, high) in integer_fields.items():
        if name in payload:
            values[name] = min(max(int(payload[name]), low), high)
    for name, (low, high) in float_fields.items():
        if name in payload:
            values[name] = min(max(float(payload[name]), low), high)
    return values
