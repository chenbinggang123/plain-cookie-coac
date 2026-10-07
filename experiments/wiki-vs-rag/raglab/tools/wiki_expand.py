from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from ..vault import Chunk, load_vault
from .wiki_graph import build_pages, lexical_similarity


class WikiGraph:
    def __init__(self, root: Path, experiment_dir: Path, include: list[str] | None):
        self.root = root
        files, chunks = load_vault(root, experiment_dir, include)
        self.pages, self.graph = build_pages(root, files)
        self.chunks_by_source: dict[str, list[Chunk]] = defaultdict(list)
        for chunk in chunks:
            self.chunks_by_source[chunk.source_path].append(chunk)
        self.backlinks: dict[str, set[str]] = defaultdict(set)
        for source, targets in self.graph.items():
            for target in targets:
                self.backlinks[target].add(source)

    def expand(
        self,
        seed_results: list[dict[str, Any]],
        question: str,
        settings: dict[str, Any],
        *,
        dimension_id: str,
        round_index: int,
    ) -> dict[str, Any]:
        seeds = list(dict.fromkeys(item["source_path"] for item in seed_results if item["source_path"] in self.pages))
        visited = set(seeds)
        queue = deque((source, source, 0, [source]) for source in seeds)
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        paths: list[list[str]] = []
        while queue and len(nodes) < settings["wiki_max_nodes"]:
            current, seed, depth, path = queue.popleft()
            if depth >= settings["wiki_max_hops"]:
                continue
            neighbors = [(target, "forward") for target in self.graph.get(current, set())]
            neighbors += [(target, "backlink") for target in self.backlinks.get(current, set())]
            neighbors.sort(key=lambda item: lexical_similarity(question, self.pages[item[0]].summary), reverse=True)
            for target, direction in neighbors:
                if target in visited or len(nodes) >= settings["wiki_max_nodes"]:
                    continue
                visited.add(target)
                next_path = path + [target]
                page = self.pages[target]
                nodes.append(
                    {
                        "card_id": target,
                        "title": page.title,
                        "source_path": target,
                        "status": "unknown",
                        "hops": depth + 1,
                    }
                )
                edges.append(
                    {
                        "from": current,
                        "to": target,
                        "type": "related",
                        "direction": direction,
                        "confidence": "wiki-link",
                    }
                )
                paths.append(next_path)
                queue.append((target, seed, depth + 1, next_path))

        results: list[dict[str, Any]] = []
        for node in nodes:
            ranked = sorted(
                self.chunks_by_source.get(node["source_path"], []),
                key=lambda chunk: lexical_similarity(question, f"{' '.join(chunk.heading_path)} {chunk.content}"),
                reverse=True,
            )
            if not ranked:
                continue
            chunk = ranked[0]
            score = lexical_similarity(question, f"{' '.join(chunk.heading_path)} {chunk.content}")
            results.append(
                {
                    "rank": len(results) + 1,
                    "score": round(score, 4),
                    "source_path": chunk.source_path,
                    "document_title": chunk.document_title,
                    "heading": " > ".join(chunk.heading_path) or chunk.document_title,
                    "content": chunk.content,
                    "chunk_id": chunk.chunk_id,
                    "status": "unknown",
                    "dimension_id": dimension_id,
                    "retrieval_round": round_index,
                    "channels": ["wiki"],
                    "relation_type": "related",
                    "selection_reason": f"从语义种子沿 Wiki 关系扩展 {node['hops']} 跳",
                    "score_components": {"wiki_relevance": round(score, 4), "wiki_hops": node["hops"]},
                }
            )
        return {
            "seeds": seeds,
            "results": results,
            "nodes": nodes,
            "edges": edges,
            "paths": paths,
            "trace": {"visited": len(visited), "returned": len(results), "max_hops": settings["wiki_max_hops"]},
        }
