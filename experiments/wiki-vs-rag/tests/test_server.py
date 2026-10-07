from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from server import Handler, load_env_file


class ServerDeploymentTests(unittest.TestCase):
    def test_local_env_file_loads_values_without_overriding_existing_environment(self) -> None:
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "# comment\nPROVIDER_CONFIG_MODE=environment\n"
                "GENERATION_MODEL='deepseek-flash'\nGENERATION_API_KEY=file-secret\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"GENERATION_API_KEY": "cloud-secret"}, clear=True):
                load_env_file(env_file)
                self.assertEqual("environment", __import__("os").environ["PROVIDER_CONFIG_MODE"])
                self.assertEqual("deepseek-flash", __import__("os").environ["GENERATION_MODEL"])
                self.assertEqual("cloud-secret", __import__("os").environ["GENERATION_API_KEY"])

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

    def test_cloudbase_openid_overrides_client_user_id(self) -> None:
        handler = object.__new__(Handler)
        handler.headers = {"X-WX-OPENID": "trusted-openid"}
        self.assertEqual("trusted-openid", handler._user_id("spoofed-client-id"))

    def test_resource_sharing_original_openid_takes_priority(self) -> None:
        handler = object.__new__(Handler)
        handler.headers = {
            "X-WX-OPENID": "resource-owner-openid",
            "X-WX-FROM-OPENID": "actual-user-openid",
        }
        self.assertEqual("actual-user-openid", handler._user_id("spoofed-client-id"))

    def test_cloud_identity_can_be_required_in_production(self) -> None:
        handler = object.__new__(Handler)
        handler.headers = {}
        with patch.dict("os.environ", {"REQUIRE_CLOUDBASE_IDENTITY": "true"}, clear=True):
            with self.assertRaises(PermissionError):
                handler._user_id("client-id")


if __name__ == "__main__":
    unittest.main()
