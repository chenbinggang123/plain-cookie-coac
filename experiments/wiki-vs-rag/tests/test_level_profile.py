from __future__ import annotations

import unittest
from pathlib import Path

from helpers import workspace_tempdir
from raglab.personalization.level_profile import LevelProfileStore, infer_dimension, infer_power_signal


class LevelProfileTests(unittest.TestCase):
    def test_dimension_is_inferred_from_question(self) -> None:
        self.assertEqual(infer_dimension("镜飞雷神连招怎么练"), "mechanics")
        self.assertEqual(infer_dimension("逆风怎样刷野补经济"), "economy")
        self.assertEqual(infer_dimension("中路线权不足能不能入侵"), "decision")

    def test_power_signal_maps_common_shorthand_to_distinct_levels(self) -> None:
        self.assertEqual(infer_power_signal("我现在镜战力5000怎么提升")["level"], 1)
        self.assertEqual(infer_power_signal("我现在镜战力1w怎么提升")["level"], 2)
        signal = infer_power_signal("我现在镜战力1w3怎么提升")
        self.assertEqual(signal["declared_power"], 13_000)
        self.assertEqual(signal["level"], 3)

    def test_question_power_is_per_answer_prior_without_overwriting_profile(self) -> None:
        with workspace_tempdir() as directory:
            store = LevelProfileStore(Path(directory))
            store.set_level("u1", "镜", "decision", 3)
            context = store.context("u1", "镜", "我现在镜战力5000怎么提升")
            self.assertEqual(context["level"], 1)
            self.assertEqual(context["profile_level"], 3)
            self.assertEqual(context["level_source"], "question_power")
            self.assertEqual(context["confidence"], 0.65)
            self.assertEqual(store.get_profile("u1", "镜")["dimensions"]["decision"]["level"], 3)

    def test_two_matching_feedback_events_adjust_one_level(self) -> None:
        with workspace_tempdir() as directory:
            store = LevelProfileStore(Path(directory))
            context = store.context("u1", "镜", "什么时候可以入侵", 2)
            payload = {
                "user_id": "u1",
                "hero": "镜",
                "dimension": context["dimension"],
                "feedback": "too_easy",
                "run_id": "run-1",
            }
            first = store.apply_feedback(payload)
            second = store.apply_feedback({**payload, "run_id": "run-2"})
            self.assertEqual(first["profile"]["dimensions"]["decision"]["level"], 2)
            self.assertEqual(second["profile"]["dimensions"]["decision"]["level"], 3)

    def test_right_feedback_increases_confidence_without_level_drift(self) -> None:
        with workspace_tempdir() as directory:
            store = LevelProfileStore(Path(directory))
            store.context("u1", "镜", "镜大招换位怎么练", 1)
            result = store.apply_feedback(
                {
                    "user_id": "u1",
                    "hero": "镜",
                    "dimension": "mechanics",
                    "feedback": "right",
                }
            )
            state = result["profile"]["dimensions"]["mechanics"]
            self.assertEqual(state["level"], 1)
            self.assertGreaterEqual(state["confidence"], 0.55)


if __name__ == "__main__":
    unittest.main()
