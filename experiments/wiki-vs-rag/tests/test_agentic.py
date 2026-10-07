from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import workspace_tempdir
from raglab.agentic.auditor import audit_evidence
from raglab.agentic.composer import compose_answer_with_metrics
from raglab.agentic.normalizer import normalize_question
from raglab.agentic.orchestrator import AgenticOrchestrator
from raglab.agentic.planner import build_plan
from raglab.agentic.router import route_question
from raglab.agentic.schemas import resolve_agentic_settings
from raglab.providers import ProviderConfig


class QueryStore:
    def search(self, query, provider, *, top_k):
        labels = ["定位", "操作", "经济", "进场", "地图", "复盘"]
        matched = next((label for label in labels if label in query), "决策")
        return [
            {
                "rank": 1,
                "score": 0.78,
                "source_path": f"{matched}.md",
                "document_title": matched,
                "heading": matched,
                "content": f"{matched}需要满足视野和队友距离条件，并检查风险；不满足时回到安全线。" * 4,
                "chunk_id": matched,
            }
        ][:top_k]


class EntryStore:
    def search(self, query, provider, *, top_k):
        return [
            {
                "rank": 1,
                "score": 0.8,
                "source_path": "入口.md",
                "document_title": "入口",
                "heading": "入侵前提",
                "content": "入侵需要中路线权和队友距离。" * 12,
                "chunk_id": "entry",
            }
        ][:top_k]


class AgenticTests(unittest.TestCase):
    def test_broad_question_produces_required_dimensions(self) -> None:
        settings = resolve_agentic_settings({"max_dimensions": 6})
        normalized = normalize_question("镜怎么玩？")
        route = route_question(normalized)
        plan = build_plan(normalized, route, settings)
        self.assertEqual(route["route"], "broad")
        self.assertEqual(len(plan["dimensions"]), 6)
        self.assertEqual(sum(1 for item in plan["dimensions"] if item["required"]), 5)

    def test_plan_contains_level_specific_teaching_contract(self) -> None:
        settings = resolve_agentic_settings({})
        normalized = normalize_question("镜什么时候可以入侵？")
        route = route_question(normalized)
        plan = build_plan(
            normalized,
            route,
            settings,
            {"level": 3, "level_label": "L3 权衡复盘型", "dimension": "decision"},
        )
        self.assertEqual(plan["teaching_contract"]["level"], 3)
        self.assertIn("自然组织", plan["teaching_contract"]["format_rule"])
        self.assertIn("不要机械使用", plan["teaching_contract"]["avoid"])

    def test_three_levels_have_distinct_soft_teaching_strategies(self) -> None:
        settings = resolve_agentic_settings({})
        normalized = normalize_question("镜怎么玩？")
        route = route_question(normalized)
        contracts = [
            build_plan(normalized, route, settings, {"level": level})["teaching_contract"]
            for level in (1, 2, 3)
        ]
        self.assertEqual(len({item["focus"] for item in contracts}), 3)
        self.assertIn("下一局", contracts[0]["structure"][-1])
        self.assertIn("如果—那么", contracts[1]["structure"][1])
        self.assertIn("诊断", contracts[2]["structure"][0])

    def test_composer_uses_human_readable_soft_guidance(self) -> None:
        plan = {
            "teaching_contract": {
                "level_label": "L1 入门执行型",
                "learning_goal": "下一局能执行一个改进动作",
                "focus": "只解决一个问题",
                "structure": ["指出问题", "给具体动作", "给训练任务"],
                "instruction": "使用短句。",
                "avoid": "不要堆术语。",
                "format_rule": "不是固定文章目录。",
                "declared_power": 5000,
            }
        }
        generated = {
            "answer": "先把第一次死亡控制住。",
            "elapsed_ms": 1,
            "api_calls": 1,
            "token_usage": {"available": False},
        }
        with patch("raglab.agentic.composer.generate_answer_with_metrics", return_value=generated) as call:
            compose_answer_with_metrics(
                ProviderConfig("openai", "https://example.test", "model"),
                "我现在镜战力5000怎么提升",
                "targeted",
                [],
                {"decision": "READY"},
                plan,
                answer_max_chars=800,
            )
        prompt = call.call_args.args[1]
        self.assertIn("真人教练", prompt)
        self.assertIn("不是固定文章目录", prompt)
        self.assertNotIn("输出结构：", prompt)

    def test_auditor_never_marks_missing_blocking_condition_ready(self) -> None:
        plan = {
            "task_type": "targeted_decision",
            "core_query": "镜是否入侵",
            "required_relation_types": ["prerequisite", "blocking"],
        }
        evidence = [{"chunk_id": "a", "content": "入侵需要中路线权和队友距离。"}]
        audit = audit_evidence(plan, evidence, round_index=2, max_rounds=2)
        self.assertEqual(audit["decision"], "ASK_USER")
        self.assertIn("否决条件", audit["missing_conditions"])

    def test_broad_orchestrator_keeps_dimension_trace_and_logs(self) -> None:
        with workspace_tempdir() as directory:
            root = Path(directory)
            experiment = root / "experiment"
            experiment.mkdir()
            settings = resolve_agentic_settings({"max_dimensions": 6, "max_rounds": 2})
            result = AgenticOrchestrator(root, experiment, QueryStore(), None).run(
                "镜怎么玩？",
                ProviderConfig("ollama", "local", "embed"),
                settings,
            )
            self.assertEqual(result["route"], "broad")
            self.assertGreaterEqual(len(result["audit"]["covered_dimensions"]), 5)
            self.assertEqual(result["trace"]["rounds"], 1)
            self.assertTrue(list((experiment / ".rag-data" / "runs").glob("*.json")))

    def test_wiki_expansion_adds_unique_evidence_from_semantic_seed(self) -> None:
        with workspace_tempdir() as directory:
            root = Path(directory)
            experiment = root / "experiment"
            experiment.mkdir()
            (root / "入口.md").write_text(
                "# 入侵前提\n\n" + "入侵需要中路线权和队友距离。" * 12 + "\n\n[[撤退路线]]",
                encoding="utf-8",
            )
            (root / "撤退路线.md").write_text(
                "# 撤退路线\n\n" + "没视野时不要入侵，失败会死亡；否则回到安全线，成功后推塔控龙。" * 10,
                encoding="utf-8",
            )
            settings = resolve_agentic_settings({"max_rounds": 2, "wiki_max_hops": 1})
            result = AgenticOrchestrator(root, experiment, EntryStore(), None).run(
                "镜入侵敌方蓝区需要满足什么条件？",
                ProviderConfig("ollama", "local", "embed"),
                settings,
            )
            self.assertGreaterEqual(result["trace"]["wiki_added_evidence"], 1)
            self.assertTrue(result["trace"]["wiki_enabled"])
            self.assertTrue(any(call["tool"] == "wiki_expand" and call["paths"] for call in result["trace"]["tool_calls"]))


if __name__ == "__main__":
    unittest.main()
