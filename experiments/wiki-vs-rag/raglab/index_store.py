from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .providers import ProviderConfig, embed_texts
from .vault import Chunk, corpus_fingerprint


@dataclass
class IndexStore:
    data_dir: Path

    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "manifest.json"

    @property
    def vectors_path(self) -> Path:
        return self.data_dir / "vectors.npy"

    def exists(self) -> bool:
        return self.manifest_path.exists() and self.vectors_path.exists()

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
        matrices: list[np.ndarray] = []
        total = len(chunks)
        for start in range(0, total, batch_size):
            batch = chunks[start : start + batch_size]
            matrices.append(embed_texts(config, [chunk.content for chunk in batch]))
            if progress:
                progress(min(start + len(batch), total), total)
        vectors = np.vstack(matrices).astype(np.float32)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        np.save(self.vectors_path, vectors)
        manifest = {
            "version": 1,
            "provider_fingerprint": config.fingerprint(),
            "corpus_fingerprint": corpus_fingerprint(chunks),
            "dimensions": int(vectors.shape[1]),
            "chunks": [chunk.to_dict() for chunk in chunks],
        }
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"chunk_count": total, "dimensions": int(vectors.shape[1])}

    def load(self) -> tuple[dict[str, Any], np.ndarray]:
        if not self.exists():
            raise FileNotFoundError("尚未创建向量索引。")
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        vectors = np.load(self.vectors_path)
        if len(manifest.get("chunks", [])) != len(vectors):
            raise ValueError("索引清单与向量数量不一致，请重新创建索引。")
        return manifest, vectors

    def search(
        self,
        query: str,
        config: ProviderConfig,
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        manifest, vectors = self.load()
        if manifest.get("provider_fingerprint") != config.fingerprint():
            raise ValueError("当前嵌入配置与索引不一致，请重新创建索引或恢复原配置。")
        query_vector = embed_texts(config, [query])[0]
        scores = vectors @ query_vector
        count = min(max(top_k, 1), len(scores))
        indices = np.argsort(scores)[::-1][:count]
        results: list[dict[str, Any]] = []
        for rank, index in enumerate(indices, start=1):
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
