from __future__ import annotations

import unittest
from unittest.mock import patch

from raglab.providers import ProviderConfig, generate_answer, generate_answer_with_metrics


class ProviderMetricsTests(unittest.TestCase):
    def test_environment_mode_ignores_client_provider_overrides(self) -> None:
        environment = {
            "PROVIDER_CONFIG_MODE": "environment",
            "GENERATION_KIND": "openai",
            "GENERATION_BASE_URL": "https://trusted.example/v1/",
            "GENERATION_MODEL": "trusted-model",
            "GENERATION_API_KEY": "server-secret",
        }
        payload = {
            "generation": {
                "kind": "ollama",
                "base_url": "http://untrusted.invalid",
                "model": "client-model",
                "api_key": "client-secret",
            }
        }

        with patch.dict("os.environ", environment, clear=False):
            config = ProviderConfig.from_payload(payload, "generation")

        self.assertEqual(config.kind, "openai")
        self.assertEqual(config.base_url, "https://trusted.example/v1")
        self.assertEqual(config.model, "trusted-model")
        self.assertEqual(config.api_key, "server-secret")

    def test_openai_generation_exposes_usage_without_breaking_text_api(self) -> None:
        response = {
            "choices": [{"message": {"content": "测试回答"}}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
                "prompt_cache_hit_tokens": 80,
            },
        }
        config = ProviderConfig("openai", "https://example.test", "chat-model", "secret")
        sources = [{"source_path": "a.md", "heading": "标题", "content": "证据"}]

        with patch("raglab.providers._post_json", return_value=response) as post:
            result = generate_answer_with_metrics(config, "问题", sources)
        self.assertEqual(result["answer"], "测试回答")
        self.assertEqual(result["api_calls"], 1)
        self.assertEqual(result["token_usage"]["total_tokens"], 150)
        self.assertEqual(result["token_usage"]["cached_tokens"], 80)
        system_prompt = post.call_args.args[1]["messages"][0]["content"]
        self.assertIn("游戏教练", system_prompt)
        self.assertIn("自然、具体、好读", system_prompt)

        with patch("raglab.providers._post_json", return_value=response):
            self.assertEqual(generate_answer(config, "问题", sources), "测试回答")

    def test_ollama_generation_maps_eval_counts_to_tokens(self) -> None:
        response = {
            "message": {"content": "本地回答"},
            "prompt_eval_count": 90,
            "eval_count": 25,
        }
        config = ProviderConfig("ollama", "http://127.0.0.1:11434", "qwen")
        sources = [{"source_path": "a.md", "heading": "标题", "content": "证据"}]

        with patch("raglab.providers._post_json", return_value=response):
            result = generate_answer_with_metrics(config, "问题", sources)
        self.assertEqual(result["token_usage"]["input_tokens"], 90)
        self.assertEqual(result["token_usage"]["output_tokens"], 25)
        self.assertEqual(result["token_usage"]["total_tokens"], 115)


if __name__ == "__main__":
    unittest.main()
