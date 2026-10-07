from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..index_store import IndexStore
from ..providers import ProviderConfig, ProviderError
from ..tools import WikiGraph, merge_evidence, semantic_search
from .auditor import CONDITION_KEYWORDS, audit_evidence
from .composer import compose_answer_with_metrics
from .normalizer import normalize_question
from .planner import build_plan, initial_tasks
from .prompts import PROMPT_VERSION
from .router import route_question


class AgenticOrchestrator:
    def __init__(
        self,
        vault_root: Path,
        experiment_dir: Path,
        store: IndexStore,
        include: list[str] | None,
    ) -> None:
        self.vault_root = vault_root
        self.experiment_dir = experiment_dir
        self.store = store
        self.include = include

    def run(
        self,
        question: str,
        embedding: ProviderConfig,
        settings: dict[str, Any],
        *,
        level_context: dict[str, Any] | None = None,
        generation: ProviderConfig | None = None,
        generate: bool = False,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        states: list[dict[str, Any]] = []
        timings: dict[str, int] = {}

        def mark(state: str) -> None:
            states.append({"state": state, "elapsed_ms": round((time.perf_counter() - started) * 1000)})

        mark("RECEIVED")
        step_started = time.perf_counter()
        normalized = normalize_question(question)
        timings["normalize"] = round((time.perf_counter() - step_started) * 1000)
        mark("NORMALIZED")

        step_started = time.perf_counter()
        route = route_question(normalized)
        timings["route"] = round((time.perf_counter() - step_started) * 1000)
        mark("ROUTED")
        plan = build_plan(normalized, route, settings, level_context)
        mark("PLANNED")

        tool_calls: list[dict[str, Any]] = []
        all_candidates: list[dict[str, Any]] = []
        audit: dict[str, Any]
        merged = {"results": [], "trace": {"candidate_count": 0, "returned_count": 0, "estimated_tokens": 0}}
        rounds = 0
        tasks = initial_tasks(plan)
        wiki_graph = WikiGraph(self.vault_root, self.experiment_dir, self.include) if tasks else None

        if not tasks:
            audit = audit_evidence(plan, [], round_index=0, max_rounds=settings["max_rounds"])
        else:
            while tasks and rounds < settings["max_rounds"]:
                rounds += 1
                mark("RETRIEVING_SEMANTIC")
                next_round_candidates: list[dict[str, Any]] = []
                for task in tasks:
                    semantic_started = time.perf_counter()
                    try:
                        semantic = semantic_search(
                            self.store,
                            embedding,
                            task["question"],
                            settings,
                            dimension_id=task["id"],
                            round_index=rounds,
                        )
                    except ProviderError as exc:
                        raise ProviderError(f"Embedding 检索阶段失败：{exc}") from exc
                    timings["semantic"] = timings.get("semantic", 0) + round(
                        (time.perf_counter() - semantic_started) * 1000
                    )
                    next_round_candidates.extend(semantic["results"])
                    tool_calls.append(
                        {
                            "tool": "semantic_search",
                            "round": rounds,
                            "dimension_id": task["id"],
                            "query": task["question"],
                            "trace": semantic["trace"],
                            "results": [
                                {"chunk_id": item["chunk_id"], "source_path": item["source_path"], "score": item["score"]}
                                for item in semantic["results"]
                            ],
                        }
                    )
                    if wiki_graph is not None:
                        mark("EXPANDING_WIKI")
                        wiki_started = time.perf_counter()
                        expansion = wiki_graph.expand(
                            semantic["results"],
                            task["question"],
                            settings,
                            dimension_id=task["id"],
                            round_index=rounds,
                        )
                        timings["wiki"] = timings.get("wiki", 0) + round(
                            (time.perf_counter() - wiki_started) * 1000
                        )
                        next_round_candidates.extend(expansion["results"])
                        tool_calls.append(
                            {
                                "tool": "wiki_expand",
                                "round": rounds,
                                "dimension_id": task["id"],
                                "seeds": expansion["seeds"],
                                "nodes": expansion["nodes"],
                                "edges": expansion["edges"],
                                "paths": expansion["paths"],
                                "trace": expansion["trace"],
                            }
                        )

                all_candidates.extend(next_round_candidates)
                mark("MERGING_EVIDENCE")
                merge_started = time.perf_counter()
                merged = merge_evidence(all_candidates, settings)
                timings["merge"] = timings.get("merge", 0) + round((time.perf_counter() - merge_started) * 1000)
                mark("AUDITING")
                audit = audit_evidence(
                    plan,
                    merged["results"],
                    round_index=rounds,
                    max_rounds=settings["max_rounds"],
                )
                if audit["decision"] != "RETRIEVE_AGAIN":
                    break
                mark("RETRIEVE_AGAIN")
                tasks = [
                    {
                        "id": item["dimension_id"],
                        "label": item["dimension_id"],
                        "question": item["query"],
                        "required": True,
                    }
                    for item in audit["recommended_next_queries"]
                ]

        evidence = merged["results"]
        answer = ""
        generation_metrics: dict[str, Any] | None = None
        if route["route"] == "clarification_required":
            answer = "请补充英雄、当前局面和你想判断的动作，我再建立检索任务。"
            mark("WAITING_FOR_USER")
        elif route["route"] == "out_of_scope":
            answer = "当前问题超出这套王者荣耀知识库的检索范围。"
            mark("COMPOSING_LIMITED_ANSWER")
        elif generate and generation is not None:
            mark("COMPOSING")
            compose_started = time.perf_counter()
            try:
                generation_metrics = compose_answer_with_metrics(
                    generation,
                    question,
                    route["route"],
                    evidence,
                    audit,
                    plan,
                    answer_max_chars=settings["answer_max_chars"],
                )
            except ProviderError as exc:
                raise ProviderError(f"回答生成阶段失败：{exc}") from exc
            answer = str(generation_metrics["answer"])
            timings["compose"] = round((time.perf_counter() - compose_started) * 1000)

        semantic_ids = {
            item["chunk_id"] for item in all_candidates if "semantic" in item.get("channels", [])
        }
        wiki_only = [
            item for item in evidence if "wiki" in item.get("channels", []) and item["chunk_id"] not in semantic_ids
        ]
        wiki_text = "\n".join(item["content"] for item in wiki_only)
        wiki_condition_count = sum(
            1 for words in CONDITION_KEYWORDS.values() if any(word in wiki_text for word in words)
        )
        mark("COMPLETED")
        timings["total"] = round((time.perf_counter() - started) * 1000)
        retrieval_ms = max(0, timings["total"] - timings.get("compose", 0))
        result = {
            "answer": answer,
            "route": route["route"],
            "normalization": normalized,
            "route_detail": route,
            "plan": plan,
            "results": evidence,
            "evidence": evidence,
            "audit": audit,
            "trace": {
                "prompt_version": PROMPT_VERSION,
                "states": states,
                "tool_calls": tool_calls,
                "rounds": rounds,
                "wiki_enabled": True,
                "wiki_added_evidence": len(wiki_only),
                "wiki_added_required_conditions": wiki_condition_count,
                "merge": merged["trace"],
                "timing_ms": timings,
                "token_usage": {"evidence_estimated": merged["trace"].get("estimated_tokens", 0)},
            },
            "timing_ms": timings["total"],
            "retrieval_ms": retrieval_ms,
            "personalization": dict(level_context or {}),
        }
        if generation_metrics is not None:
            result["generation"] = {key: value for key, value in generation_metrics.items() if key != "answer"}
            result["generation_ms"] = generation_metrics["elapsed_ms"]
        result["run_id"] = self._write_run_log(question, result)
        return result

    def _write_run_log(self, question: str, result: dict[str, Any]) -> str:
        run_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = self.experiment_dir / ".rag-data" / "runs"
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {"run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(), "question": question, **result}
        (run_dir / f"{timestamp}-{run_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return run_id
