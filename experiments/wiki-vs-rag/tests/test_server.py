from __future__ import annotations

import unittest
from unittest.mock import patch

from server import Handler


class ServerDeploymentTests(unittest.TestCase):
    def test_index_is_open_for_local_development_without_token(self) -> None:
        handler = object.__new__(Handler)
        handler.headers = {}
        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(handler._index_authorized())

    def test_index_requires_matching_cloud_token(self) -> None:
        handler = object.__new__(Handler)
        with patch.dict("os.environ", {"INDEX_ADMIN_TOKEN": "server-token"}, clear=True):
            handler.headers = {"X-Index-Admin-Token": "wrong-token"}
            self.assertFalse(handler._index_authorized())
            handler.headers = {"X-Index-Admin-Token": "server-token"}
            self.assertTrue(handler._index_authorized())


if __name__ == "__main__":
    unittest.main()
