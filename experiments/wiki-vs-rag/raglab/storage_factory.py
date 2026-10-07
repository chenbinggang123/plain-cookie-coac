from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .index_store import IndexStore
from .personalization import LevelProfileStore


def storage_backend() -> str:
    backend = os.environ.get("STORAGE_BACKEND", "local").strip().lower()
    if backend not in {"local", "cloudbase_pg"}:
        raise ValueError("STORAGE_BACKEND 必须是 local 或 cloudbase_pg。")
    return backend


def _database_url() -> str:
    url = (
        os.environ.get("CLOUDBASE_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    if not url:
        raise ValueError("使用 cloudbase_pg 时必须配置 CLOUDBASE_DATABASE_URL。")
    return url


def create_index_store(data_dir: Path) -> Any:
    if storage_backend() == "local":
        return IndexStore(data_dir)
    from .pg_store import PgVectorStore

    return PgVectorStore(_database_url())


def create_profile_store(data_dir: Path) -> Any:
    if storage_backend() == "local":
        return LevelProfileStore(data_dir)
    from .pg_store import PgLevelProfileStore

    return PgLevelProfileStore(_database_url())


__all__ = ["create_index_store", "create_profile_store", "storage_backend"]
