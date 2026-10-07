from __future__ import annotations

import argparse
import hmac
import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from raglab.app import CoachAgentApp, ProviderError


APP_DIR = Path(__file__).resolve().parent
DEFAULT_VAULT = APP_DIR.parents[1]
WEB_DIR = APP_DIR / "web"


class Handler(BaseHTTPRequestHandler):
    app: CoachAgentApp

    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 2_000_000:
            raise ValueError("请求体过大。")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _index_authorized(self) -> bool:
        expected = os.environ.get("INDEX_ADMIN_TOKEN", "")
        if not expected:
            return True
        supplied = self.headers.get("X-Index-Admin-Token", "")
        return hmac.compare_digest(supplied, expected)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json({"ok": True, "data": {"status": "ok"}})
            return
        if parsed.path == "/api/status":
            try:
                self._json({"ok": True, "data": self.app.status()})
            except Exception as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if parsed.path == "/api/profile":
            try:
                query = parse_qs(parsed.query)
                user_id = (query.get("user_id") or ["local-user"])[0]
                hero = (query.get("hero") or ["全英雄"])[0]
                self._json({"ok": True, "data": self.app.profile(user_id, hero)})
            except Exception as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        relative = unquote(parsed.path.lstrip("/") or "index.html")
        candidate = (WEB_DIR / relative).resolve()
        try:
            candidate.relative_to(WEB_DIR.resolve())
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            if self.path == "/api/index":
                if not self._index_authorized():
                    self._json({"ok": False, "error": "索引管理凭据无效。"}, HTTPStatus.FORBIDDEN)
                    return
                data = self.app.build_index(payload)
            elif self.path == "/api/coach/run":
                data = self.app.coach_run(payload)
            elif self.path == "/api/profile":
                data = self.app.set_profile_level(payload)
            elif self.path == "/api/feedback":
                data = self.app.save_level_feedback(payload)
            else:
                self._json({"ok": False, "error": "接口不存在。"}, HTTPStatus.NOT_FOUND)
                return
            self._json({"ok": True, "data": data})
        except (ValueError, FileNotFoundError, ProviderError, json.JSONDecodeError) as exc:
            print(f"[coach request rejected] {exc}", file=sys.stderr, flush=True)
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            print(f"[coach server error] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            self._json({"ok": False, "error": f"服务器错误：{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    parser = argparse.ArgumentParser(description="水平感知规划式 AI 教练")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    args = parser.parse_args()
    Handler.app = CoachAgentApp(args.vault, APP_DIR)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"AI 教练：http://{args.host}:{args.port}")
    print(f"只读知识库：{args.vault.resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
