from __future__ import annotations

import unittest
from pathlib import Path

from raglab.vault import chunk_markdown, clean_markdown
from helpers import workspace_tempdir


class VaultTests(unittest.TestCase):
    def test_frontmatter_and_wikilinks_are_cleaned(self) -> None:
        text = "---\ntags: [x]\n---\n# 标题\n参见 [[路径/笔记|显示名]]。"
        cleaned = clean_markdown(text)
        self.assertNotIn("tags:", cleaned)
        self.assertIn("显示名", cleaned)
        self.assertNotIn("[[", cleaned)

    def test_chunks_follow_markdown_headings(self) -> None:
        with workspace_tempdir() as directory:
            root = Path(directory)
            note = root / "note.md"
            note.write_text(
                "# 总标题\n\n" + "开场内容" * 20 + "\n\n## 子主题\n\n" + "具体结论" * 30,
                encoding="utf-8",
            )
            chunks = chunk_markdown(note, root, minimum=20, maximum=500)
            self.assertGreaterEqual(len(chunks), 2)
            self.assertEqual(chunks[-1].heading_path, ["总标题", "子主题"])
            self.assertEqual(chunks[-1].source_path, "note.md")


if __name__ == "__main__":
    unittest.main()
