from __future__ import annotations

from typing import Any


CONDITION_KEYWORDS = {
    "prerequisite": ("前提", "需要", "满足", "线权", "状态", "距离", "视野", "位置"),
    "blocking": ("不要", "不能", "不应", "否决", "没视野", "未好", "风险高", "避免"),
    "risk": ("风险", "代价", "死亡", "丢失", "中断", "被抓", "失败"),
    "fallback": ("替代", "否则", "转而", "回到", "安全线", "自家野区", "撤退"),
    "success_conversion": ("成功后", "打赢后", "推塔", "控龙", "反野", "转换", "收益"),
}


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def audit_evidence(
    plan: dict[str, Any],
    evidence: list[dict[str, Any]],
    *,
    round_index: int,
    max_rounds: int,
) -> dict[str, Any]:
    if plan["task_type"] == "broad_tutorial":
        required = [item for item in plan["dimensions"] if item["required"]]
        covered_ids = {item.get("dimension_id") for item in evidence if item.get("content")}
        covered = [item["label"] for item in required if item["id"] in covered_ids]
        missing = [item for item in required if item["id"] not in covered_ids]
        need_more = bool(missing) and round_index < max_rounds
        return {
            "decision": "RETRIEVE_AGAIN" if need_more else ("INSUFFICIENT" if missing else "READY"),
            "required_dimensions": [item["label"] for item in required],
            "covered_dimensions": covered,
            "missing_dimensions": [item["label"] for item in missing],
            "duplicate_evidence_groups": max(0, len(evidence) - len({item["chunk_id"] for item in evidence})),
            "conflicts": [],
            "need_retrieval": need_more,
            "need_user_clarification": False,
            "recommended_next_queries": [
                {"dimension_id": item["id"], "query": f"{item['question']} 请补充具体条件、风险和可执行动作。"}
                for item in missing
            ],
            "completeness": round(len(covered) / max(1, len(required)), 4),
        }

    if plan["task_type"] == "targeted_decision":
        joined = "\n".join(item.get("content", "") for item in evidence)
        required = plan["required_relation_types"]
        covered = [name for name in required if _contains_any(joined, CONDITION_KEYWORDS[name])]
        missing = [name for name in required if name not in covered]
        need_more = bool(missing) and round_index < max_rounds
        if need_more:
            decision = "RETRIEVE_AGAIN"
        elif not evidence:
            decision = "INSUFFICIENT"
        elif missing:
            decision = "ASK_USER"
        else:
            decision = "READY"
        labels = {
            "prerequisite": "成立前提", "blocking": "否决条件", "risk": "失败风险",
            "fallback": "替代方案", "success_conversion": "成功后的收益转换",
        }
        return {
            "decision": decision,
            "covered_conditions": [labels[item] for item in covered],
            "missing_conditions": [labels[item] for item in missing],
            "blocking_conditions": [],
            "conflicts": [],
            "need_retrieval": need_more,
            "need_user_clarification": decision == "ASK_USER",
            "recommended_next_queries": [
                {"dimension_id": "decision", "query": f"{plan['core_query']}，重点补充{labels[item]}"}
                for item in missing[:3]
            ],
            "completeness": round(len(covered) / max(1, len(required)), 4),
        }

    return {
        "decision": "INSUFFICIENT",
        "need_retrieval": False,
        "need_user_clarification": plan["task_type"] == "clarification_required",
        "recommended_next_queries": [],
        "completeness": 0.0,
        "conflicts": [],
    }
