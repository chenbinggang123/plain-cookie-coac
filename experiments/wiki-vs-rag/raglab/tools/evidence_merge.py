from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


STATUS_QUALITY = {"accepted": 1.0, "incubating": 0.75, "candidate": 0.55, "unknown": 0.5, "rejected": 0.0}
RELATION_NECESSITY = {
    "prerequisite": 1.0,
    "blocking": 1.0,
    "fallback": 0.85,
    "success_conversion": 0.8,
    "risk": 0.8,
    "related": 0.25,
}


def estimate_tokens(text: str) -> int:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z0-9_]+", text))
    punctuation = len(re.findall(r"[^\w\s\u4e00-\u9fff]", text))
    return cjk + latin + max(0, punctuation // 2)


def merge_evidence(candidates: list[dict[str, Any]], settings: dict[str, Any]) -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    dimension_counts: dict[str, int] = defaultdict(int)
    for candidate in candidates:
        chunk_id = candidate["chunk_id"]
        if chunk_id in by_id:
            existing = by_id[chunk_id]
            existing["channels"] = sorted(set(existing.get("channels", [])) | set(candidate.get("channels", [])))
            if candidate.get("dimension_id") != existing.get("dimension_id"):
                existing.setdefault("also_supports", []).append(candidate.get("dimension_id"))
            if candidate["score"] > existing["score"]:
                existing["score"] = candidate["score"]
            continue
        item = dict(candidate)
        semantic = item["score"] if "semantic" in item.get("channels", []) else 0.0
        relation = RELATION_NECESSITY.get(item.get("relation_type", "related"), 0.0)
        quality = STATUS_QUALITY.get(item.get("status", "unknown"), 0.5)
        coverage = 1.0 if dimension_counts[item.get("dimension_id", "decision")] == 0 else 0.45
        item["evidence_score"] = round(semantic * 0.45 + relation * 0.25 + quality * 0.15 + coverage * 0.15, 4)
        item["score_components"] = {
            **item.get("score_components", {}),
            "relation_necessity": relation,
            "source_quality": quality,
            "dimension_coverage": coverage,
        }
        by_id[chunk_id] = item
        dimension_counts[item.get("dimension_id", "decision")] += 1

    ranked = sorted(by_id.values(), key=lambda item: (item["evidence_score"], item["score"]), reverse=True)
    selected: list[dict[str, Any]] = []
    per_source: dict[str, int] = defaultdict(int)
    used_tokens = 0
    rejected: list[dict[str, Any]] = []
    for item in ranked:
        source = item["source_path"]
        tokens = estimate_tokens(item["content"])
        reason = None
        if len(selected) >= settings["final_evidence"]:
            reason = "超过最终证据数量"
        elif per_source[source] >= settings["max_per_source"]:
            reason = "超过单来源上限"
        elif selected and used_tokens + tokens > settings["token_budget"]:
            reason = "超过 token 预算"
        if reason:
            rejected.append({"chunk_id": item["chunk_id"], "reason": reason})
            continue
        item["estimated_tokens"] = tokens
        item["score"] = item["evidence_score"]
        selected.append(item)
        per_source[source] += 1
        used_tokens += tokens
    return {
        "results": selected,
        "trace": {
            "candidate_count": len(candidates),
            "deduplicated_count": len(ranked),
            "returned_count": len(selected),
            "estimated_tokens": used_tokens,
            "rejected": rejected,
            "score_formula": "语义45%＋关系必要性25%＋来源质量15%＋维度覆盖15%",
        },
    }
