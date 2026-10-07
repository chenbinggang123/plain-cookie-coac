from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from raglab.index_store import IndexStore
from raglab.providers import ProviderConfig
from raglab.vault import Chunk
from helpers import workspace_tempdir


class IndexStoreTests(unittest.TestCase):
    def test_build_and_search(self) -> None:
        chunks = [
            Chunk("a", "a.md", "A", ["A"], "库存需要人工确认", 1),
            Chunk("b", "b.md", "B", ["B"], "镜的刷野节奏", 1),
        ]
        config = ProviderConfig("ollama", "http://localhost:11434", "embed")
        with workspace_tempdir() as directory:
            store = IndexStore(Path(directory))
            with patch("raglab.index_store.embed_texts", return_value=np.asarray([[1, 0], [0, 1]], dtype=np.float32)):
                store.build(chunks, config)
            with patch("raglab.index_store.embed_texts", return_value=np.asarray([[0.9, 0.1]], dtype=np.float32)):
                results = store.search("人工确认", config, top_k=1)
            self.assertEqual(results[0]["source_path"], "a.md")


if __name__ == "__main__":
    unittest.main()
