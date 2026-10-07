from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import quote


APP_DIR = Path(__file__).resolve().parent
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def load_scope() -> list[str]:
    payload = json.loads((APP_DIR / "game_scope.json").read_text(encoding="utf-8"))
    return [str(item).replace("\\", "/") for item in payload.get("include", [])]


def is_allowed(relative_path: str, scope: list[str]) -> bool:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    if not normalized.lower().endswith(".md"):
        return False
    for item in scope:
        candidate = item.replace("\\", "/").lstrip("/")
        if candidate.endswith("/"):
            if normalized.startswith(candidate):
                return True
        elif normalized == candidate:
            return True
    return False


def extract_archive(archive_bytes: bytes, destination: Path, scope: list[str]) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    extracted = 0
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts
            if len(parts) < 2:
                continue
            relative = PurePosixPath(*parts[1:]).as_posix()
            if not is_allowed(relative, scope):
                continue
            source = archive.extractfile(member)
            if source is None:
                continue
            target = destination.joinpath(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            extracted += 1
    return extracted


def download_archive(repository: str, ref: str, token: str = "") -> bytes:
    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise ValueError("KNOWLEDGE_REPO 必须采用 owner/repository 格式。")
    url = f"https://api.github.com/repos/{repository}/tarball/{quote(ref, safe='')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "plain-cookie-coach",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def sync_knowledge(destination: Path) -> int:
    repository = os.environ.get(
        "KNOWLEDGE_REPO", "chenbinggang123/Cookie-s_Knowledge_Base"
    ).strip()
    ref = os.environ.get("KNOWLEDGE_REF", "main").strip() or "main"
    token = os.environ.get("KNOWLEDGE_GITHUB_TOKEN", "").strip()
    scope = load_scope()
    last_error: Exception | None = None

    for attempt in range(1, 4):
        try:
            archive = download_archive(repository, ref, token)
            staging = Path(tempfile.mkdtemp(prefix="plain-cookie-vault-"))
            count = extract_archive(archive, staging, scope)
            if count == 0:
                raise RuntimeError("知识仓库中没有找到检索范围内的 Markdown 文件。")
            if destination.exists():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging.replace(destination)
            print(
                f"已从 {repository}@{ref} 同步 {count} 个知识文件。",
                flush=True,
            )
            return count
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                print(f"知识同步第 {attempt} 次失败，准备重试。", file=sys.stderr, flush=True)
                time.sleep(attempt * 2)

    raise RuntimeError(f"无法同步知识仓库：{last_error}") from last_error


def main() -> None:
    vault = Path(
        os.environ.get("KNOWLEDGE_VAULT_DIR", "/tmp/plain-cookie-vault")
    ).resolve()
    sync_knowledge(vault)
    os.execv(
        sys.executable,
        [sys.executable, str(APP_DIR / "server.py"), "--vault", str(vault)],
    )


if __name__ == "__main__":
    main()
