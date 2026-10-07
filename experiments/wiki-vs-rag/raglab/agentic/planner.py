from __future__ import annotations

from typing import Any


DIMENSION_TEMPLATES = [
    ("positioning", "核心定位", "{hero}的英雄定位和主要胜利方式是什么？", True),
    ("mechanics", "操作基础", "{hero}的基础操作应该按什么顺序训练？", True),
    ("economy", "发育与经济", "{hero}前中期如何建立和恢复经济循环？", True),
    ("engage", "进场与风险", "{hero}进场前需要检查哪些条件和否决信号？", True),
    ("map", "地图资源转换", "敌方位置变化时{hero}如何转换兵线、野区和防御塔收益？", True),
    ("review", "训练与复盘", "{hero}玩家如何从训练营过渡到实战并复盘？", False),
]


def build_plan(
    normalized: dict[str, Any],
    route: dict[str, Any],
    settings: dict[str, Any],
    level_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hero = normalized.get("hero") or "该英雄"
    level_context = dict(level_context or {})
    level = min(3, max(1, int(level_context.get("level", 2))))
    teaching_contracts = {
        1: {
            "focus": "只解决当前最影响上分的一个问题，让用户下一局就能照着做。",
            "structure": ["先指出最该改的事", "给两到三个具体动作", "给一个下一局训练任务"],
            "instruction": "使用短句和日常游戏语言；术语出现时马上解释；每条建议都说明在对局里怎么看、怎么做。",
            "avoid": "不要讲复杂博弈、机会成本或长篇原理，不要一次布置多个训练目标。",
        },
        2: {
            "focus": "帮助用户从凭感觉行动，进步到能看条件再做决定。",
            "structure": ["先给结论", "用如果—那么讲清判断信号", "指出常见误判", "给一个复盘练习"],
            "instruction": "围绕两到四个最重要的局面信号讲解，使用具体场景，不重复用户大概率已经掌握的基础定义。",
            "avoid": "不要把回答写成规则清单，不要为了显得高级而堆砌术语。",
        },
        3: {
            "focus": "定位高水平玩家最关键的决策瓶颈，并给出可以验证的改进方向。",
            "structure": ["先诊断真正瓶颈", "比较关键选择", "说明何时切换", "给一个高质量复盘任务"],
            "instruction": "省略基础定义；只有与问题直接相关时才讨论取舍和机会成本；用具体对局信号支撑判断。",
            "avoid": "不要机械使用“核心判断、机会成本、反事实复盘、证据边界”等报告标题。",
        },
    }
    teaching_contract = {
        "level": level,
        "level_label": level_context.get("level_label", f"L{level}"),
        "dimension": level_context.get("dimension", "decision"),
        "dimension_label": level_context.get("dimension_label", "局面决策"),
        "learning_goal": level_context.get("learning_goal", "建立可执行的判断方法"),
        "level_source": level_context.get("level_source", "profile"),
        "declared_power": level_context.get("declared_power"),
        "format_rule": "这些内容是写作重点，不是固定文章目录；根据问题自然组织，可用短段落或少量列表。",
        **teaching_contracts[level],
    }
    if route["route"] == "broad":
        dimensions = [
            {"id": key, "label": label, "question": template.format(hero=hero), "required": required}
            for key, label, template, required in DIMENSION_TEMPLATES[: settings["max_dimensions"]]
        ]
        return {
            "task_type": "broad_tutorial",
            "dimensions": dimensions,
            "max_rounds_per_dimension": settings["max_rounds"],
            "teaching_contract": teaching_contract,
        }
    if route["route"] == "targeted":
        action = normalized.get("decision_action") or normalized["normalized_question"]
        return {
            "task_type": "targeted_decision",
            "core_query": f"{hero}{action}需要满足哪些条件、有哪些否决信号和替代方案",
            "required_relation_types": [
                "prerequisite", "blocking", "risk", "fallback", "success_conversion"
            ],
            "max_rounds": settings["max_rounds"],
            "teaching_contract": teaching_contract,
        }
    return {
        "task_type": route["route"],
        "dimensions": [],
        "max_rounds": 0,
        "teaching_contract": teaching_contract,
    }


def initial_tasks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    if plan["task_type"] == "broad_tutorial":
        return [dict(item) for item in plan["dimensions"]]
    if plan["task_type"] == "targeted_decision":
        return [{"id": "decision", "label": "核心决策", "question": plan["core_query"], "required": True}]
    return []
