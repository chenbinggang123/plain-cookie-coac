from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from bootstrap import extract_archive, is_allowed


class KnowledgeBootstrapTests(unittest.TestCase):
    def test_scope_accepts_only_markdown_from_allowed_paths(self) -> None:
        scope = ["02-Areas/王者荣耀/", "01-Projects/指定资料.md"]
        self.assertTrue(is_allowed("02-Areas/王者荣耀/打野.md", scope))
        self.assertTrue(is_allowed("01-Projects/指定资料.md", scope))
        self.assertFalse(is_allowed("02-Areas/编程/后端.md", scope))
        self.assertFalse(is_allowed("02-Areas/王者荣耀/截图.png", scope))

    def test_archive_extraction_drops_unrelated_and_binary_files(self) -> None:
        archive_buffer = io.BytesIO()
        with tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
            files = {
                "repo-main/02-Areas/王者荣耀/李白.md": b"allowed",
                "repo-main/02-Areas/编程/private.md": b"blocked",
                "repo-main/02-Areas/王者荣耀/image.png": b"blocked",
            }
            for name, content in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            count = extract_archive(
                archive_buffer.getvalue(), destination, ["02-Areas/王者荣耀/"]
            )
            self.assertEqual(count, 1)
            self.assertEqual(
                (destination / "02-Areas/王者荣耀/李白.md").read_text(),
                "allowed",
            )
            self.assertFalse((destination / "02-Areas/编程/private.md").exists())
            self.assertFalse((destination / "02-Areas/王者荣耀/image.png").exists())


if __name__ == "__main__":
    unittest.main()
