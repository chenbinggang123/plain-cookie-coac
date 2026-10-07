from __future__ import annotations

import json
import http.client
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

import numpy as np


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderConfig:
    kind: str
    base_url: str
    model: str
    api_key: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any], field: str) -> "ProviderConfig":
        mode = os.environ.get("PROVIDER_CONFIG_MODE", "payload").strip().lower()
        config = {} if mode == "environment" else (payload.get(field) or {})
        prefix = field.upper()
        return cls(
            kind=str(config.get("kind") or os.environ.get(f"{prefix}_KIND", "")).strip(),
            base_url=str(
                config.get("base_url") or os.environ.get(f"{prefix}_BASE_URL", "")
            ).strip().rstrip("/"),
            model=str(config.get("model") or os.environ.get(f"{prefix}_MODEL", "")).strip(),
            api_key=str(
                config.get("api_key") or os.environ.get(f"{prefix}_API_KEY", "")
            ).strip(),
        )

    def fingerprint(self) -> str:
        return f"{self.kind}|{self.base_url}|{self.model}"


def _post_json(url: str, payload: dict[str, Any], api_key: str = "") -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(3):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"模型服务返回 HTTP {exc.code}: {detail[:500]}") from exc
        except (
            urllib.error.URLError,
            http.client.IncompleteRead,
            http.client.RemoteDisconnected,
            ConnectionResetError,
        ) as exc:
            if attempt == 2:
                detail = getattr(exc, "reason", exc)
                raise ProviderError(f"模型服务连续连接或读取失败：{detail}") from exc
            time.sleep(0.5 * (attempt + 1))
    raise ProviderError("模型服务请求失败。")


def embed_texts(config: ProviderConfig, texts: list[str]) -> np.ndarray:
    if not config.base_url or not config.model:
        raise ProviderError("请填写嵌入服务地址和模型名。")
    if config.kind == "ollama":
        response = _post_json(
            f"{config.base_url}/api/embed",
            {"model": config.model, "input": texts},
            config.api_key,
        )
        vectors = response.get("embeddings")
    elif config.kind == "openai":
        response = _post_json(
            f"{config.base_url}/embeddings",
            {"model": config.model, "input": texts},
            config.api_key,
        )
        vectors = [item["embedding"] for item in response.get("data", [])]
    else:
        raise ProviderError("嵌入服务类型必须是 ollama 或 openai。")
    if not vectors or len(vectors) != len(texts):
        raise ProviderError("嵌入服务返回的向量数量与输入不一致。")
    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ProviderError("嵌入服务返回了零向量。")
    return matrix / norms


def generate_answer(
    config: ProviderConfig,
    question: str,
    sources: list[dict[str, Any]],
    *,
    method_label: str = "知识库检索",
) -> str:
    return str(
        generate_answer_with_metrics(
            config,
            question,
            sources,
            method_label=method_label,
        )["answer"]
    )


def generate_answer_with_metrics(
    config: ProviderConfig,
    question: str,
    sources: list[dict[str, Any]],
    *,
    method_label: str = "知识库检索",
) -> dict[str, Any]:
    if not config.base_url or not config.model:
        raise ProviderError("请填写生成服务地址和模型名。")
    context = "\n\n".join(
        f"[来源 {index}]\n文件：{item['source_path']}\n标题：{item['heading']}\n内容：{item['content']}"
        for index, item in enumerate(sources, start=1)
    )
    system = (
        f"你是一位熟悉普通玩家沟通方式的游戏教练。当前证据来自{method_label}。只能根据提供的来源回答。"
        "每个实质结论末尾标注[来源 N]。不得把推测写成库内事实。"
        "回答要自然、具体、好读，不写成审计报告，不为了显得完整而堆砌标题和术语。"
        "如果来源不足，用一句自然的话说明暂时不能确定，不要让证据说明淹没教学内容。"
    )
    user = f"问题：{question}\n\n可用来源：\n{context}"
    started = time.perf_counter()
    if config.kind == "ollama":
        response = _post_json(
            f"{config.base_url}/api/chat",
            {
                "model": config.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "options": {"temperature": 0.1},
            },
            config.api_key,
        )
        answer = str((response.get("message") or {}).get("content") or "").strip()
        input_tokens = response.get("prompt_eval_count")
        output_tokens = response.get("eval_count")
        usage_source = "ollama"
        cached_tokens = None
    elif config.kind == "openai":
        response = _post_json(
            f"{config.base_url}/chat/completions",
            {
                "model": config.model,
                "temperature": 0.1,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            config.api_key,
        )
        choices = response.get("choices") or []
        answer = str(((choices[0] if choices else {}).get("message") or {}).get("content") or "").strip()
        usage = response.get("usage") or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        usage_source = "openai"
        cached_tokens = usage.get("prompt_cache_hit_tokens")
        if cached_tokens is None:
            cached_tokens = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
    else:
        raise ProviderError("生成服务类型必须是 ollama 或 openai。")

    total_tokens = None
    if config.kind == "openai":
        total_tokens = (response.get("usage") or {}).get("total_tokens")
    if total_tokens is None and isinstance(input_tokens, int) and isinstance(output_tokens, int):
        total_tokens = input_tokens + output_tokens
    return {
        "answer": answer,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "api_calls": 1,
        "provider": config.kind,
        "model": config.model,
        "token_usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "available": total_tokens is not None,
            "source": usage_source,
        },
    }
