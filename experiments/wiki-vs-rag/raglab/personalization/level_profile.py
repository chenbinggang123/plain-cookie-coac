from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DIMENSIONS: dict[str, dict[str, str]] = {
    "mechanics": {"label": "操作与连招", "description": "连招、换位、大招空间与操作稳定性"},
    "economy": {"label": "发育与资源", "description": "刷野、兵线、经济与资源转换"},
    "decision": {"label": "局面决策", "description": "入侵、抓边、接团、撤退与风险判断"},
}

LEVELS: dict[int, dict[str, str]] = {
    1: {"label": "L1 入门执行型", "goal": "先知道现在做什么，再理解最关键的原因"},
    2: {"label": "L2 条件判断型", "goal": "学习组合条件、否决信号与替代方案"},
    3: {"label": "L3 权衡复盘型", "goal": "比较机会成本、动态切换条件与反事实选择"},
}

POWER_PATTERN = re.compile(
    r"(?:英雄)?战力\s*(?:是|有|到|到了|大概|约)?\s*(\d+(?:\.\d+)?)\s*([wW万kK千]?)\s*(\d{0,3})"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_user_id(value: Any) -> str:
    user_id = str(value or "local-user").strip()[:64]
    return user_id or "local-user"


def infer_dimension(question: str) -> str:
    text = question.lower()
    decision_words = ("入侵", "抓边", "接团", "团战", "进场", "撤退", "能不能", "该不该", "什么时候", "视野")
    mechanics_words = ("连招", "飞雷神", "操作", "换位", "镜像", "刷新大招", "手法", "训练营")
    economy_words = ("经济", "刷野", "兵线", "发育", "资源", "推塔", "控龙", "反野", "野区")
    if any(word in text for word in decision_words):
        return "decision"
    if any(word in text for word in mechanics_words):
        return "mechanics"
    if any(word in text for word in economy_words):
        return "economy"
    return "decision"


def infer_power_signal(question: str) -> dict[str, Any] | None:
    """Treat an explicitly stated hero power as a weak, per-answer level prior."""
    match = POWER_PATTERN.search(question)
    if not match:
        return None
    major_text, unit, tail = match.groups()
    major = float(major_text)
    if unit.lower() in {"w", "万"}:
        power = round(major * 10_000)
        if tail and major.is_integer():
            power += int(tail) * (10 ** (4 - len(tail)))
    elif unit.lower() in {"k", "千"}:
        power = round(major * 1_000)
        if tail and major.is_integer():
            power += int(tail) * (10 ** (3 - len(tail)))
    else:
        power = round(major)
    if power <= 0:
        return None
    level = 1 if power < 8_000 else 2 if power < 12_000 else 3
    return {
        "declared_power": power,
        "level": level,
        "level_source": "question_power",
        "signal_confidence": 0.65,
    }


def _new_state() -> dict[str, Any]:
    return {
        "level": 2,
        "confidence": 0.0,
        "evidence_count": 0,
        "pending_direction": 0,
        "pending_count": 0,
        "updated_at": None,
    }


class LevelProfileStore:
    """Small, inspectable local store for level calibration only."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.profile_path = data_dir / "level_profiles.json"
        self.feedback_path = data_dir / "level_feedback.jsonl"
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Any]:
        if not self.profile_path.exists():
            return {"version": 1, "users": {}}
        try:
            payload = json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "users": {}}
        if not isinstance(payload, dict) or not isinstance(payload.get("users"), dict):
            return {"version": 1, "users": {}}
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.profile_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.profile_path)

    def _ensure_dimension(
        self,
        payload: dict[str, Any],
        user_id: str,
        hero: str,
        dimension: str,
    ) -> dict[str, Any]:
        user = payload["users"].setdefault(user_id, {"heroes": {}, "created_at": _utc_now()})
        hero_profile = user["heroes"].setdefault(hero, {"dimensions": {}})
        return hero_profile["dimensions"].setdefault(dimension, _new_state())

    def get_profile(self, user_id: Any, hero: str = "镜") -> dict[str, Any]:
        clean_id = _clean_user_id(user_id)
        clean_hero = str(hero or "镜").strip() or "镜"
        with self._lock:
            payload = self._read()
            states = {
                key: dict(self._ensure_dimension(payload, clean_id, clean_hero, key))
                for key in DIMENSIONS
            }
            self._write(payload)
        return {
            "user_id": clean_id,
            "hero": clean_hero,
            "dimensions": {
                key: {**DIMENSIONS[key], **states[key], "level_label": LEVELS[int(states[key]["level"])]["label"]}
                for key in DIMENSIONS
            },
        }

    def context(
        self,
        user_id: Any,
        hero: str,
        question: str,
        declared_level: Any = None,
    ) -> dict[str, Any]:
        clean_id = _clean_user_id(user_id)
        clean_hero = str(hero or "镜").strip() or "镜"
        dimension = infer_dimension(question)
        power_signal = infer_power_signal(question)
        with self._lock:
            payload = self._read()
            state = self._ensure_dimension(payload, clean_id, clean_hero, dimension)
            if declared_level not in (None, "", "auto"):
                level = min(3, max(1, int(declared_level)))
                state.update(
                    {
                        "level": level,
                        "confidence": max(float(state.get("confidence", 0.0)), 0.4),
                        "evidence_count": int(state.get("evidence_count", 0)) + 1,
                        "updated_at": _utc_now(),
                    }
                )
                self._write(payload)
            snapshot = dict(state)
        profile_level = int(snapshot["level"])
        if declared_level not in (None, "", "auto"):
            level = profile_level
            level_source = "manual_override"
        elif power_signal is not None:
            level = int(power_signal["level"])
            level_source = str(power_signal["level_source"])
        else:
            level = profile_level
            level_source = "profile"
        profile_confidence = round(float(snapshot.get("confidence", 0.0)), 3)
        effective_confidence = (
            float(power_signal["signal_confidence"])
            if level_source == "question_power" and power_signal is not None
            else profile_confidence
        )
        return {
            "user_id": clean_id,
            "hero": clean_hero,
            "dimension": dimension,
            "dimension_label": DIMENSIONS[dimension]["label"],
            "level": level,
            "level_label": LEVELS[level]["label"],
            "learning_goal": LEVELS[level]["goal"],
            "confidence": effective_confidence,
            "profile_confidence": profile_confidence,
            "needs_calibration": effective_confidence < 0.35,
            "profile_level": profile_level,
            "level_source": level_source,
            "declared_power": power_signal.get("declared_power") if power_signal else None,
            "signal_confidence": power_signal.get("signal_confidence") if power_signal else None,
        }

    def set_level(self, user_id: Any, hero: str, dimension: str, level: Any) -> dict[str, Any]:
        if dimension not in DIMENSIONS:
            raise ValueError("能力维度必须是 mechanics、economy 或 decision。")
        clean_id = _clean_user_id(user_id)
        clean_hero = str(hero or "镜").strip() or "镜"
        clean_level = min(3, max(1, int(level)))
        with self._lock:
            payload = self._read()
            state = self._ensure_dimension(payload, clean_id, clean_hero, dimension)
            state.update(
                {
                    "level": clean_level,
                    "confidence": max(0.7, float(state.get("confidence", 0.0))),
                    "evidence_count": int(state.get("evidence_count", 0)) + 1,
                    "pending_direction": 0,
                    "pending_count": 0,
                    "updated_at": _utc_now(),
                }
            )
            self._write(payload)
        return self.get_profile(clean_id, clean_hero)

    def apply_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        feedback = str(payload.get("feedback") or "").strip()
        if feedback not in {"too_easy", "right", "too_hard"}:
            raise ValueError("难度反馈必须是 too_easy、right 或 too_hard。")
        dimension = str(payload.get("dimension") or "")
        if dimension not in DIMENSIONS:
            raise ValueError("反馈缺少有效的能力维度。")
        user_id = _clean_user_id(payload.get("user_id"))
        hero = str(payload.get("hero") or "镜").strip() or "镜"
        with self._lock:
            data = self._read()
            state = self._ensure_dimension(data, user_id, hero, dimension)
            previous_level = int(state["level"])
            state["evidence_count"] = int(state.get("evidence_count", 0)) + 1
            if feedback == "right":
                state["confidence"] = min(1.0, float(state.get("confidence", 0.0)) + 0.15)
                state["pending_direction"] = 0
                state["pending_count"] = 0
            else:
                direction = 1 if feedback == "too_easy" else -1
                if int(state.get("pending_direction", 0)) == direction:
                    state["pending_count"] = int(state.get("pending_count", 0)) + 1
                else:
                    state["pending_direction"] = direction
                    state["pending_count"] = 1
                state["confidence"] = min(1.0, float(state.get("confidence", 0.0)) + 0.05)
                if int(state["pending_count"]) >= 2:
                    state["level"] = min(3, max(1, previous_level + direction))
                    state["pending_direction"] = 0
                    state["pending_count"] = 0
                    state["confidence"] = max(0.55, float(state["confidence"]))
            state["updated_at"] = _utc_now()
            self._write(data)
            event = {
                "created_at": _utc_now(),
                "run_id": str(payload.get("run_id") or ""),
                "user_id": user_id,
                "hero": hero,
                "dimension": dimension,
                "feedback": feedback,
                "previous_level": previous_level,
                "new_level": int(state["level"]),
            }
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with self.feedback_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return {
            "event": event,
            "profile": self.get_profile(user_id, hero),
            "message": "已记录。连续两次相同的难度反馈才会调整一级。",
        }
