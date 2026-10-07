from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDES = {
    ".git",
    ".gitnexus",
    ".obsidian",
    ".rag-data",
    ".codex-temp",
    ".docx_tmp",
    ".tmp",
    ".tools",
    ".venv-video",
    "node_modules",
    "output",
}

FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
WIKILINK = re.compile(r"!?\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_path: str
    document_title: str
    heading_path: list[str]
    content: str
    modified_ns: int

    def to_dict(self) -> dict:
        return asdict(self)


def _is_excluded(path: Path, root: Path, experiment_dir: Path) -> bool:
    try:
        path.relative_to(experiment_dir)
        return True
    except ValueError:
        pass
    relative = path.relative_to(root)
    return any(part in DEFAULT_EXCLUDES or part.startswith(".tmp") for part in relative.parts)


def _matches_scope(path: Path, root: Path, include: list[str] | None) -> bool:
    if not include:
        return True
    relative = path.relative_to(root).as_posix()
    return any(relative == rule.rstrip("/") or relative.startswith(rule.rstrip("/") + "/") for rule in include)


def iter_markdown_files(
    root: Path,
    experiment_dir: Path,
    include: list[str] | None = None,
) -> Iterable[Path]:
    for path in root.rglob("*.md"):
        if not _is_excluded(path, root, experiment_dir) and _matches_scope(path, root, include):
            yield path


def clean_markdown(text: str) -> str:
    text = FRONTMATTER.sub("", text, count=1)
    text = HTML_COMMENT.sub("", text)
    text = WIKILINK.sub(lambda match: match.group(2) or match.group(1), text)
    text = MARKDOWN_LINK.sub(lambda match: match.group(1), text)
    return text.strip()


def _split_large_section(text: str, maximum: int) -> list[str]:
    if len(text) <= maximum:
        return [text]
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > maximum:
            pieces.append(current)
            current = ""
        if len(paragraph) > maximum:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(paragraph[index : index + maximum] for index in range(0, len(paragraph), maximum))
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        pieces.append(current)
    return pieces


def chunk_markdown(
    path: Path,
    root: Path,
    *,
    minimum: int = 80,
    maximum: int = 1800,
) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    text = clean_markdown(raw)
    if not text:
        return []

    relative = path.relative_to(root).as_posix()
    title = path.stem
    heading_stack: list[str] = []
    section_lines: list[str] = []
    sections: list[tuple[list[str], str]] = []

    def flush() -> None:
        body = "\n".join(section_lines).strip()
        if body:
            sections.append((list(heading_stack), body))
        section_lines.clear()

    for line in text.splitlines():
        match = HEADING.match(line)
        if not match:
            section_lines.append(line)
            continue
        flush()
        level = len(match.group(1))
        heading = match.group(2).strip()
        heading_stack[:] = heading_stack[: level - 1]
        heading_stack.append(heading)
        if level == 1:
            title = heading
    flush()

    modified_ns = path.stat().st_mtime_ns
    chunks: list[Chunk] = []
    for headings, body in sections:
        context = " > ".join(headings)
        combined = f"{context}\n{body}".strip() if context else body
        for piece in _split_large_section(combined, maximum):
            if len(piece.strip()) < minimum:
                continue
            digest = hashlib.sha256(
                f"{relative}\n{context}\n{piece}".encode("utf-8")
            ).hexdigest()[:20]
            chunks.append(
                Chunk(
                    chunk_id=digest,
                    source_path=relative,
                    document_title=title,
                    heading_path=headings,
                    content=piece,
                    modified_ns=modified_ns,
                )
            )
    return chunks


def load_vault(
    root: Path,
    experiment_dir: Path,
    include: list[str] | None = None,
) -> tuple[list[Path], list[Chunk]]:
    files = sorted(iter_markdown_files(root, experiment_dir, include))
    chunks: list[Chunk] = []
    for path in files:
        chunks.extend(chunk_markdown(path, root))
    return files, chunks


def corpus_fingerprint(chunks: list[Chunk]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk.chunk_id.encode("ascii"))
    return digest.hexdigest()
