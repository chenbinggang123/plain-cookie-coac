from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from raglab.index_store import IndexStore
from raglab.storage_factory import create_index_store, storage_backend
from helpers import workspace_tempdir


class StorageFactoryTests(unittest.TestCase):
    def test_local_is_default_and_keeps_existing_store(self) -> None:
        with workspace_tempdir() as directory, patch.dict("os.environ", {}, clear=True):
            self.assertEqual("local", storage_backend())
            self.assertIsInstance(create_index_store(Path(directory)), IndexStore)

    def test_cloudbase_pg_requires_database_url(self) -> None:
        with patch.dict("os.environ", {"STORAGE_BACKEND": "cloudbase_pg"}, clear=True):
            with self.assertRaisesRegex(ValueError, "CLOUDBASE_DATABASE_URL"):
                create_index_store(Path("unused"))

    def test_unknown_backend_is_rejected(self) -> None:
        with patch.dict("os.environ", {"STORAGE_BACKEND": "unknown"}, clear=True):
            with self.assertRaisesRegex(ValueError, "STORAGE_BACKEND"):
                storage_backend()


if __name__ == "__main__":
    unittest.main()
