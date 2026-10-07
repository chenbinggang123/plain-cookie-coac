from __future__ import annotations

import re
from typing import Any


HEROES = ("镜", "澜", "露娜", "韩信", "李白", "娜可露露", "孙悟空", "曜")
STAGES = {
    "前期": ("前期", "开局", "一级", "四级前"),
    "中期": ("中期", "转线", "第一条龙"),
    "后期": ("后期", "大后期", "高地", "风暴龙王"),
    "逆风": ("逆风", "经济落后", "劣势"),
    "顺风": ("顺风", "经济领先", "优势"),
}
ACTIONS = (
    "入侵敌方蓝区", "入侵", "反野", "开大", "抓人", "推线", "带线", "参团",
    "进场", "刷野", "恢复经济", "训练", "复盘", "出装", "对位",
)


def normalize_question(question: str) -> dict[str, Any]:
    compact = re.sub(r"\s+", " ", question.strip())
    hero = next((name for name in HEROES if name in compact), None)
    stage = next(
        (label for label, words in STAGES.items() if any(word in compact for word in words)),
        "unknown",
    )
    action = next((item for item in ACTIONS if item in compact), None)
    if "进蓝" in compact and action is None:
        action = "入侵敌方蓝区"
    normalized = compact
    if compact in {"这波能不能进蓝？", "这波能不能进蓝", "能不能进蓝"}:
        normalized = "当前是否应该入侵敌方蓝区？"
    if hero and normalized.startswith(hero) is False and action:
        normalized = f"{hero}{normalized}"
    return {
        "original_question": question,
        "normalized_question": normalized,
        "hero": hero,
        "game_stage": stage,
        "decision_action": action,
        "goal": "获得可执行的游戏决策或训练建议",
        "known_conditions": [],
        "unknown_conditions": [],
        "requested_output": "决策建议与判断依据",
    }
