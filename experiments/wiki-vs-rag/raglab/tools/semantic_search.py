from __future__ import annotations

from typing import Any

from ..index_store import IndexStore
from ..providers import ProviderConfig


def semantic_search(
    store: IndexStore,
    provider: ProviderConfig,
    query: str,
    settings: dict[str, Any],
    *,
    dimension_id: str,
    round_index: int,
) -> dict[str, Any]:
    candidates = store.search(query, provider, top_k=settings["semantic_top_k"])
    best = candidates[0]["score"] if candidates else 0.0
    threshold = max(settings["semantic_min_score"], best - settings["semantic_relative_drop"])
    kept: list[dict[str, Any]] = []
    per_source: dict[str, int] = {}
    for index, candidate in enumerate(candidates):
        source = candidate["source_path"]
        if per_source.get(source, 0) >= settings["max_per_source"]:
            continue
        if candidate["score"] < threshold and index >= settings["semantic_min_keep"]:
            continue
        item = dict(candidate)
        item.update(
            {
                "status": "unknown",
                "dimension_id": dimension_id,
                "retrieval_round": round_index,
                "channels": ["semantic"],
                "selection_reason": "规划子问题的语义入口",
                "score_components": {"semantic_score": candidate["score"]},
            }
        )
        kept.append(item)
        per_source[source] = per_source.get(source, 0) + 1
    return {
        "query": query,
        "results": kept,
        "trace": {
            "candidate_count": len(candidates),
            "returned_count": len(kept),
            "threshold": round(threshold, 4),
            "best_score": best,
            "minimum_kept": min(settings["semantic_min_keep"], len(candidates)),
        },
    }
