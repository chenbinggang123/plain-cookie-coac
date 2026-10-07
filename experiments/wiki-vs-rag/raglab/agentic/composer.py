from __future__ import annotations

from typing import Any

from ..providers import ProviderConfig, generate_answer_with_metrics


def compose_answer(
    config: ProviderConfig,
    question: str,
    route: str,
    evidence: list[dict[str, Any]],
    audit: dict[str, Any],
    plan: dict[str, Any],
    *,
    answer_max_chars: int,
) -> str:
    return str(
        compose_answer_with_metrics(
            config,
            question,
            route,
            evidence,
            audit,
            plan,
            answer_max_chars=answer_max_chars,
        )["answer"]
    )


def compose_answer_with_metrics(
    config: ProviderConfig,
    question: str,
    route: str,
    evidence: list[dict[str, Any]],
    audit: dict[str, Any],
    plan: dict[str, Any],
    *,
    answer_max_chars: int,
) -> dict[str, Any]:
    contract = dict(plan.get("teaching_contract") or {})
    structure = "→".join(contract.get("structure") or ["结论", "依据", "行动建议", "来源"])
    level_label = str(contract.get("level_label") or "L2 条件判断型")
    instruction = str(contract.get("instruction") or "给出可执行、证据充分的回答。")
    focus = str(contract.get("focus") or "解决用户当前最重要的问题。")
    avoid = str(contract.get("avoid") or "不要机械堆砌术语。")
    format_rule = str(contract.get("format_rule") or "根据问题自然组织回答。")
    power_note = (
        f"用户在问题中声明英雄战力约为 {contract['declared_power']}；把它作为水平弱信号，不要仅凭战力武断评价。"
        if contract.get("declared_power")
        else ""
    )
    bounded_question = (
        f"{question}\n\n用户相关能力水平：{level_label}。本次教学目标："
        f"{contract.get('learning_goal', '建立可执行的判断方法')}。"
        f"本次重点：{focus}。可参考的内容顺序：{structure}。"
        f"表达要求：{instruction} {avoid} {format_rule} {power_note}"
        "像熟悉玩家的真人教练当面交流：先回应问题，再给少量真正有用的建议；"
        "不要写成研究报告，不要逐项复述内部审计过程。只使用审核后的来源；"
        f"不超过 {answer_max_chars} 个汉字。审查结论：{audit.get('decision')}。"
    )
    generation = generate_answer_with_metrics(
        config,
        bounded_question,
        evidence,
        method_label="水平感知规划式 Agent（Wiki 开启）",
    )
    answer = str(generation["answer"])
    if len(answer) > answer_max_chars:
        generation["answer"] = answer[: answer_max_chars - 1].rstrip() + "…"
        generation["truncated"] = True
    else:
        generation["truncated"] = False
    return generation
