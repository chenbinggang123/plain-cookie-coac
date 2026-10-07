from __future__ import annotations

from typing import Any


BROAD_SIGNALS = ("怎么玩", "完整教学", "从入门到进阶", "系统教学", "全面", "攻略", "怎么练")
GAME_SIGNALS = (
    "镜", "澜", "打野", "野区", "蓝区", "红区", "兵线", "大招", "经济", "团战",
    "进场", "对位", "王者", "训练营", "推塔", "参团", "视野", "英雄",
)


def route_question(normalized: dict[str, Any]) -> dict[str, Any]:
    question = normalized["normalized_question"]
    if any(signal in question for signal in BROAD_SIGNALS):
        return {
            "route": "broad",
            "confidence": 0.92,
            "reason": "问题要求体系化教学，不能归结为单一决策节点。",
            "must_cover": ["操作", "经济", "进场", "地图判断", "训练复盘"],
        }
    if normalized.get("decision_action") or any(signal in question for signal in GAME_SIGNALS):
        return {
            "route": "targeted",
            "confidence": 0.84,
            "reason": "问题围绕一个局面、动作或局部判断。",
            "must_cover": ["成立条件", "否决条件", "风险", "替代方案"],
        }
    if len(question) < 8:
        return {
            "route": "clarification_required",
            "confidence": 0.78,
            "reason": "缺少英雄、局面或目标，无法建立检索任务。",
            "must_cover": [],
        }
    return {
        "route": "out_of_scope",
        "confidence": 0.72,
        "reason": "未识别到当前游戏知识库支持的对象或决策。",
        "must_cover": [],
    }
