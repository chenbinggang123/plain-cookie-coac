from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from .personalization.level_profile import (
    DIMENSIONS,
    LEVELS,
    _clean_user_id,
    _new_state,
    _utc_now,
    infer_dimension,
    infer_power_signal,
)
from .providers import ProviderConfig, embed_texts
from .vault import Chunk, corpus_fingerprint


def _connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - exercised only in misconfigured deployments
        raise RuntimeError("cloudbase_pg 需要安装 psycopg[binary]。") from exc
    return psycopg.connect(database_url, autocommit=True)


def _cosine_scores(vectors: np.ndarray, query_vector: np.ndarray) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float32)
    query = np.asarray(query_vector, dtype=np.float32)
    if matrix.ndim != 2 or query.ndim != 1 or matrix.shape[1] != query.shape[0]:
        raise ValueError("索引向量与问题向量维度不一致，请重新创建索引。")
    matrix_norms = np.linalg.norm(matrix, axis=1)
    query_norm = float(np.linalg.norm(query))
    if query_norm == 0:
        raise ValueError("嵌入模型返回了空问题向量。")
    denominators = matrix_norms * query_norm
    return np.divide(
        matrix @ query,
        denominators,
        out=np.zeros(len(matrix), dtype=np.float32),
        where=denominators != 0,
    )


def _chunk_hash(chunk: Chunk) -> str:
    canonical = json.dumps(chunk.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class PgVectorStore:
    database_url: str
    connection_factory: Callable[[str], Any] = _connect
    _cache_version: str | None = field(default=None, init=False, repr=False)
    _cache_manifest: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _cache_vectors: np.ndarray | None = field(default=None, init=False, repr=False)
    _cache_lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def _connection(self):
        return self.connection_factory(self.database_url)

    def _invalidate_cache(self) -> None:
        with self._cache_lock:
            self._cache_version = None
            self._cache_manifest = None
            self._cache_vectors = None

    def exists(self) -> bool:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT EXISTS (SELECT 1 FROM coach_index_versions WHERE status = 'active')")
            return bool(cursor.fetchone()[0])

    def build(
        self,
        chunks: list[Chunk],
        config: ProviderConfig,
        *,
        batch_size: int = 24,
        progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        if not chunks:
            raise ValueError("知识库中没有可索引的 Markdown 内容。")
        version_id = str(uuid.uuid4())
        provider_fingerprint = config.fingerprint()
        corpus_hash = corpus_fingerprint(chunks)
        dimensions = int(os.environ.get("EMBEDDING_DIMENSIONS", "1024"))
        embedded_count = 0
        reused_count = 0

        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(hashtext('plain-cookie-coach:index'))")
            if not cursor.fetchone()[0]:
                raise RuntimeError("已有索引任务正在运行，请稍后再试。")
            try:
                cursor.execute(
                    """
                    INSERT INTO coach_index_versions
                        (version_id, status, provider_fingerprint, corpus_fingerprint, chunk_count, dimensions)
                    VALUES (%s::uuid, 'building', %s, %s, %s, %s)
                    """,
                    (version_id, provider_fingerprint, corpus_hash, len(chunks), dimensions),
                )
                cursor.execute(
                    """
                    SELECT version_id::text FROM coach_index_versions
                    WHERE status = 'active' AND provider_fingerprint = %s
                    ORDER BY activated_at DESC NULLS LAST LIMIT 1
                    """,
                    (provider_fingerprint,),
                )
                active_row = cursor.fetchone()
                active_version = active_row[0] if active_row else None
                existing: dict[str, str] = {}
                if active_version:
                    cursor.execute(
                        "SELECT chunk_id, content_hash FROM coach_knowledge_chunks WHERE version_id = %s::uuid",
                        (active_version,),
                    )
                    existing = {str(row[0]): str(row[1]) for row in cursor.fetchall()}

                changed: list[tuple[int, Chunk, str]] = []
                for ordinal, chunk in enumerate(chunks):
                    content_hash = _chunk_hash(chunk)
                    if active_version and existing.get(chunk.chunk_id) == content_hash:
                        cursor.execute(
                            """
                            INSERT INTO coach_knowledge_chunks
                                (version_id, chunk_id, source_path, document_title, heading_path,
                                 content, content_hash, ordinal, embedding)
                            SELECT %s::uuid, chunk_id, source_path, document_title, heading_path,
                                   content, content_hash, %s, embedding
                            FROM coach_knowledge_chunks
                            WHERE version_id = %s::uuid AND chunk_id = %s
                            """,
                            (version_id, ordinal, active_version, chunk.chunk_id),
                        )
                        reused_count += 1
                    else:
                        changed.append((ordinal, chunk, content_hash))

                for start in range(0, len(changed), batch_size):
                    batch = changed[start : start + batch_size]
                    vectors = embed_texts(config, [item[1].content for item in batch])
                    if vectors.ndim != 2 or vectors.shape[1] != dimensions:
                        raise ValueError(
                            f"Embedding 返回 {vectors.shape[1] if vectors.ndim == 2 else '未知'} 维，"
                            f"数据库配置为 {dimensions} 维。"
                        )
                    for (ordinal, chunk, content_hash), vector in zip(batch, vectors, strict=True):
                        cursor.execute(
                            """
                            INSERT INTO coach_knowledge_chunks
                                (version_id, chunk_id, source_path, document_title, heading_path,
                                 content, content_hash, ordinal, embedding)
                            VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                            """,
                            (
                                version_id,
                                chunk.chunk_id,
                                chunk.source_path,
                                chunk.document_title,
                                json.dumps(chunk.heading_path, ensure_ascii=False),
                                chunk.content,
                                content_hash,
                                ordinal,
                                np.asarray(vector, dtype=np.float64).tolist(),
                            ),
                        )
                    embedded_count += len(batch)
                    if progress:
                        progress(reused_count + embedded_count, len(chunks))

                cursor.execute(
                    "SELECT count(*) FROM coach_knowledge_chunks WHERE version_id = %s::uuid",
                    (version_id,),
                )
                if int(cursor.fetchone()[0]) != len(chunks):
                    raise RuntimeError("新索引片段数量校验失败，旧索引仍保持可用。")
                with connection.transaction():
                    cursor.execute(
                        "UPDATE coach_index_versions SET status = 'superseded' WHERE status = 'active'"
                    )
                    cursor.execute(
                        """
                        UPDATE coach_index_versions
                        SET status = 'active', activated_at = now()
                        WHERE version_id = %s::uuid
                        """,
                        (version_id,),
                    )
                self._invalidate_cache()
                return {
                    "chunk_count": len(chunks),
                    "dimensions": dimensions,
                    "embedded_chunk_count": embedded_count,
                    "reused_chunk_count": reused_count,
                    "index_version": version_id,
                }
            except Exception as exc:
                cursor.execute(
                    """
                    UPDATE coach_index_versions
                    SET status = 'failed', error = %s
                    WHERE version_id = %s::uuid AND status = 'building'
                    """,
                    (str(exc)[:1000], version_id),
                )
                raise
            finally:
                cursor.execute("SELECT pg_advisory_unlock(hashtext('plain-cookie-coach:index'))")

    def load(self) -> tuple[dict[str, Any], np.ndarray]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT version_id::text, provider_fingerprint, corpus_fingerprint, dimensions
                FROM coach_index_versions WHERE status = 'active'
                ORDER BY activated_at DESC NULLS LAST LIMIT 1
                """
            )
            version = cursor.fetchone()
            if not version:
                raise FileNotFoundError("尚未创建向量索引。")
            with self._cache_lock:
                if self._cache_version == version[0] and self._cache_manifest is not None and self._cache_vectors is not None:
                    return self._cache_manifest, self._cache_vectors
            cursor.execute(
                """
                SELECT chunk_id, source_path, document_title, heading_path, content, embedding
                FROM coach_knowledge_chunks WHERE version_id = %s::uuid ORDER BY ordinal
                """,
                (version[0],),
            )
            rows = cursor.fetchall()
            chunks = []
            raw_vectors = []
            for row in rows:
                chunks.append(
                    {
                        "chunk_id": row[0],
                        "source_path": row[1],
                        "document_title": row[2],
                        "heading_path": row[3] if isinstance(row[3], list) else json.loads(row[3]),
                        "content": row[4],
                    }
                )
                raw_vectors.append(row[5])
            vectors = np.asarray(raw_vectors, dtype=np.float32)
            expected_dimensions = int(version[3])
            if vectors.ndim != 2 or vectors.shape != (len(chunks), expected_dimensions):
                raise ValueError("数据库中的索引向量数量或维度不一致，请重新创建索引。")
            manifest = {
                "version": 2,
                "index_version": version[0],
                "provider_fingerprint": version[1],
                "corpus_fingerprint": version[2],
                "dimensions": int(version[3]),
                "chunks": chunks,
            }
            with self._cache_lock:
                self._cache_version = version[0]
                self._cache_manifest = manifest
                self._cache_vectors = vectors
            return manifest, vectors

    def search(self, query: str, config: ProviderConfig, *, top_k: int = 5) -> list[dict[str, Any]]:
        manifest, vectors = self.load()
        if manifest.get("provider_fingerprint") != config.fingerprint():
            raise ValueError("当前嵌入配置与索引不一致，请重新创建索引或恢复原配置。")
        query_vector = embed_texts(config, [query])[0]
        scores = _cosine_scores(vectors, query_vector)
        count = min(max(1, top_k), len(scores))
        indices = np.argsort(scores)[::-1][:count]
        results = []
        for rank, index in enumerate(indices, 1):
            chunk = manifest["chunks"][int(index)]
            results.append(
                {
                    "rank": rank,
                    "score": round(float(scores[int(index)]), 4),
                    "source_path": chunk["source_path"],
                    "document_title": chunk["document_title"],
                    "heading": " > ".join(chunk.get("heading_path") or []) or chunk["document_title"],
                    "content": chunk["content"],
                    "chunk_id": chunk["chunk_id"],
                }
            )
        return results


@dataclass
class PgLevelProfileStore:
    database_url: str
    connection_factory: Callable[[str], Any] = _connect

    def _connection(self):
        return self.connection_factory(self.database_url)

    @staticmethod
    def _state(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "level": int(row[0]),
            "confidence": float(row[1]),
            "evidence_count": int(row[2]),
            "pending_direction": int(row[3]),
            "pending_count": int(row[4]),
            "updated_at": row[5].isoformat() if hasattr(row[5], "isoformat") else row[5],
        }

    def _ensure(self, cursor, user_id: str, hero: str) -> None:
        for dimension in DIMENSIONS:
            cursor.execute(
                """
                INSERT INTO coach_user_profiles (user_id, hero, dimension)
                VALUES (%s, %s, %s) ON CONFLICT (user_id, hero, dimension) DO NOTHING
                """,
                (user_id, hero, dimension),
            )

    def _read_state(self, cursor, user_id: str, hero: str, dimension: str, *, lock: bool = False):
        cursor.execute(
            """
            SELECT level, confidence, evidence_count, pending_direction, pending_count, updated_at
            FROM coach_user_profiles
            WHERE user_id = %s AND hero = %s AND dimension = %s
            """ + (" FOR UPDATE" if lock else ""),
            (user_id, hero, dimension),
        )
        row = cursor.fetchone()
        return self._state(row) if row else _new_state()

    def get_profile(self, user_id: Any, hero: str = "全英雄") -> dict[str, Any]:
        clean_id = _clean_user_id(user_id)
        clean_hero = str(hero or "全英雄").strip() or "全英雄"
        with self._connection() as connection, connection.transaction(), connection.cursor() as cursor:
            self._ensure(cursor, clean_id, clean_hero)
            states = {
                dimension: self._read_state(cursor, clean_id, clean_hero, dimension)
                for dimension in DIMENSIONS
            }
        return {
            "user_id": clean_id,
            "hero": clean_hero,
            "dimensions": {
                key: {**DIMENSIONS[key], **states[key], "level_label": LEVELS[int(states[key]["level"])]["label"]}
                for key in DIMENSIONS
            },
        }

    def context(self, user_id: Any, hero: str, question: str, declared_level: Any = None) -> dict[str, Any]:
        clean_id = _clean_user_id(user_id)
        clean_hero = str(hero or "全英雄").strip() or "全英雄"
        dimension = infer_dimension(question)
        power_signal = infer_power_signal(question)
        with self._connection() as connection, connection.transaction(), connection.cursor() as cursor:
            self._ensure(cursor, clean_id, clean_hero)
            state = self._read_state(cursor, clean_id, clean_hero, dimension, lock=True)
            if declared_level not in (None, "", "auto"):
                state.update(
                    {
                        "level": min(3, max(1, int(declared_level))),
                        "confidence": max(float(state["confidence"]), 0.4),
                        "evidence_count": int(state["evidence_count"]) + 1,
                    }
                )
                cursor.execute(
                    """
                    UPDATE coach_user_profiles SET level=%s, confidence=%s, evidence_count=%s, updated_at=now()
                    WHERE user_id=%s AND hero=%s AND dimension=%s
                    """,
                    (state["level"], state["confidence"], state["evidence_count"], clean_id, clean_hero, dimension),
                )
        profile_level = int(state["level"])
        if declared_level not in (None, "", "auto"):
            level, level_source = profile_level, "manual_override"
        elif power_signal is not None:
            level, level_source = int(power_signal["level"]), str(power_signal["level_source"])
        else:
            level, level_source = profile_level, "profile"
        profile_confidence = round(float(state["confidence"]), 3)
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
        clean_hero = str(hero or "全英雄").strip() or "全英雄"
        clean_level = min(3, max(1, int(level)))
        with self._connection() as connection, connection.transaction(), connection.cursor() as cursor:
            self._ensure(cursor, clean_id, clean_hero)
            cursor.execute(
                """
                UPDATE coach_user_profiles
                SET level=%s, confidence=GREATEST(confidence, 0.7), evidence_count=evidence_count+1,
                    pending_direction=0, pending_count=0, updated_at=now()
                WHERE user_id=%s AND hero=%s AND dimension=%s
                """,
                (clean_level, clean_id, clean_hero, dimension),
            )
        return self.get_profile(clean_id, clean_hero)

    def apply_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        feedback = str(payload.get("feedback") or "").strip()
        if feedback not in {"too_easy", "right", "too_hard"}:
            raise ValueError("难度反馈必须是 too_easy、right 或 too_hard。")
        dimension = str(payload.get("dimension") or "")
        if dimension not in DIMENSIONS:
            raise ValueError("反馈缺少有效的能力维度。")
        user_id = _clean_user_id(payload.get("user_id"))
        hero = str(payload.get("hero") or "全英雄").strip() or "全英雄"
        with self._connection() as connection, connection.transaction(), connection.cursor() as cursor:
            self._ensure(cursor, user_id, hero)
            state = self._read_state(cursor, user_id, hero, dimension, lock=True)
            previous_level = int(state["level"])
            state["evidence_count"] += 1
            if feedback == "right":
                state["confidence"] = min(1.0, state["confidence"] + 0.15)
                state["pending_direction"] = state["pending_count"] = 0
            else:
                direction = 1 if feedback == "too_easy" else -1
                state["pending_count"] = state["pending_count"] + 1 if state["pending_direction"] == direction else 1
                state["pending_direction"] = direction
                state["confidence"] = min(1.0, state["confidence"] + 0.05)
                if state["pending_count"] >= 2:
                    state["level"] = min(3, max(1, previous_level + direction))
                    state["pending_direction"] = state["pending_count"] = 0
                    state["confidence"] = max(0.55, state["confidence"])
            cursor.execute(
                """
                UPDATE coach_user_profiles
                SET level=%s, confidence=%s, evidence_count=%s, pending_direction=%s,
                    pending_count=%s, updated_at=now()
                WHERE user_id=%s AND hero=%s AND dimension=%s
                """,
                (
                    state["level"], state["confidence"], state["evidence_count"],
                    state["pending_direction"], state["pending_count"], user_id, hero, dimension,
                ),
            )
            cursor.execute(
                """
                INSERT INTO coach_feedback_events
                    (run_id, user_id, hero, dimension, feedback, previous_level, new_level)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (str(payload.get("run_id") or ""), user_id, hero, dimension, feedback, previous_level, state["level"]),
            )
        event = {
            "created_at": _utc_now(), "run_id": str(payload.get("run_id") or ""),
            "user_id": user_id, "hero": hero, "dimension": dimension, "feedback": feedback,
            "previous_level": previous_level, "new_level": int(state["level"]),
        }
        return {
            "event": event,
            "profile": self.get_profile(user_id, hero),
            "message": "已记录。连续两次相同的难度反馈才会调整一级。",
        }


__all__ = ["PgLevelProfileStore", "PgVectorStore", "_cosine_scores"]
