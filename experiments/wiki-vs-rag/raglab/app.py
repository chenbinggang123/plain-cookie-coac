from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .agentic import AgenticOrchestrator, resolve_agentic_settings
from .agentic.normalizer import normalize_question
from .personalization import DIMENSIONS
from .providers import ProviderConfig, ProviderError
from .storage_factory import create_index_store, create_profile_store, storage_backend
from .vault import corpus_fingerprint, load_vault


SAMPLE_QUESTIONS = [
    "李白逆风时应该怎么找翻盘点？",
    "貂蝉四级第一波没抓到人，下一步做什么？",
    "我玩射手经济第一，团战为什么总是暴毙？",
]


class CoachAgentApp:
    def __init__(self, vault_root: Path, app_dir: Path):
        self.vault_root = vault_root.resolve()
        self.app_dir = app_dir.resolve()
        self.data_dir = self.app_dir / ".rag-data"
        self.store = create_index_store(self.data_dir)
        self.profiles = create_profile_store(self.data_dir)
        self.storage_backend = storage_backend()
        self.scope = self._load_scope()

    def _load_scope(self) -> dict[str, Any]:
        path = self.app_dir / "game_scope.json"
        if not path.exists():
            return {"name": "全部 Markdown", "include": None}
        return json.loads(path.read_text(encoding="utf-8"))

    def status(self) -> dict[str, Any]:
        files, chunks = load_vault(self.vault_root, self.app_dir, self.scope.get("include"))
        status: dict[str, Any] = {
            "vault_root": str(self.vault_root),
            "scope_name": self.scope.get("name", "游戏知识"),
            "file_count": len(files),
            "live_chunk_count": len(chunks),
            "index_ready": self.store.exists(),
            "sample_questions": SAMPLE_QUESTIONS,
            "level_dimensions": DIMENSIONS,
            "agent": "水平感知规划式 Agent（Wiki 开启）",
            "storage_backend": self.storage_backend,
        }
        if self.store.exists():
            manifest, _ = self.store.load()
            status.update(
                {
                    "indexed_chunk_count": len(manifest.get("chunks", [])),
                    "provider_fingerprint": manifest.get("provider_fingerprint", ""),
                    "index_stale": manifest.get("corpus_fingerprint") != corpus_fingerprint(chunks),
                }
            )
        return status

    def build_index(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider = ProviderConfig.from_payload(payload, "embedding")
        files, chunks = load_vault(self.vault_root, self.app_dir, self.scope.get("include"))
        started = time.perf_counter()
        result = self.store.build(chunks, provider)
        result.update({"file_count": len(files), "elapsed_ms": round((time.perf_counter() - started) * 1000)})
        return result

    def profile(self, user_id: Any, hero: str = "全英雄") -> dict[str, Any]:
        return self.profiles.get_profile(user_id, hero)

    def set_profile_level(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.profiles.set_level(
            payload.get("user_id"),
            str(payload.get("hero") or "全英雄"),
            str(payload.get("dimension") or ""),
            payload.get("level"),
        )

    def save_level_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.profiles.apply_feedback(payload)

    def coach_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        question = str(payload.get("question") or "").strip()
        if not question:
            raise ValueError("问题不能为空。")
        self._ensure_index_current()
        settings = resolve_agentic_settings(dict(payload.get("settings") or {}))
        embedding = ProviderConfig.from_payload(payload, "embedding")
        generation = ProviderConfig.from_payload(payload, "generation")
        normalized = normalize_question(question)
        hero = str(normalized.get("hero") or payload.get("hero") or "全英雄")
        level_context = self.profiles.context(
            payload.get("user_id"), hero, question, payload.get("declared_level")
        )
        orchestrator = AgenticOrchestrator(
            self.vault_root, self.app_dir, self.store, self.scope.get("include")
        )
        return orchestrator.run(
            question,
            embedding,
            settings,
            level_context=level_context,
            generation=generation,
            generate=True,
        )

    def _ensure_index_current(self) -> None:
        if not self.store.exists():
            raise FileNotFoundError("尚未创建向量索引。")
        _, chunks = load_vault(self.vault_root, self.app_dir, self.scope.get("include"))
        manifest, _ = self.store.load()
        if manifest.get("corpus_fingerprint") != corpus_fingerprint(chunks):
            raise ValueError("知识库已更新，向量索引过期，请先重建索引。")


__all__ = ["CoachAgentApp", "ProviderError"]
