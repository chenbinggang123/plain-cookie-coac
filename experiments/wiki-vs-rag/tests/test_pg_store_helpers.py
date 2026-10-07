from __future__ import annotations

import unittest

import numpy as np

from raglab.pg_store import _chunk_hash, _cosine_scores
from raglab.vault import Chunk


class PgStoreHelperTests(unittest.TestCase):
    def test_chunk_hash_changes_with_searchable_content(self) -> None:
        first = Chunk("id", "a.md", "A", ["标题"], "原内容", 1)
        changed = Chunk("id", "a.md", "A", ["标题"], "新内容", 2)
        self.assertNotEqual(_chunk_hash(first), _chunk_hash(changed))
        self.assertEqual(_chunk_hash(first), _chunk_hash(first))

    def test_cosine_scores_are_scale_independent(self) -> None:
        vectors = np.asarray([[2.0, 0.0], [0.0, 3.0], [-1.0, 0.0]], dtype=np.float32)
        scores = _cosine_scores(vectors, np.asarray([4.0, 0.0], dtype=np.float32))
        np.testing.assert_allclose(scores, [1.0, 0.0, -1.0])

    def test_cosine_scores_reject_dimension_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "维度不一致"):
            _cosine_scores(np.zeros((2, 3)), np.zeros(2))


if __name__ == "__main__":
    unittest.main()
