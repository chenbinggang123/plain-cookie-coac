from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..vault import HEADING, WIKILINK, clean_markdown


WORD = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+")
TAG_LINE = re.compile(r"^tags\s*:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
STOP_CHARS = set("的了是在和与及或而也就都很还又把被让给从对以为于中上下来去个这那怎么何啥吗呢啊时会能可应要玩")


def _normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text.casefold())


def _features(text: str) -> set[str]:
    features: set[str] = set()
    for token in WORD.findall(text.casefold()):
        if token.isascii():
            if len(token) > 1:
                features.add(token)
            continue
        chars = [char for char in token if char not in STOP_CHARS]
        features.update(chars)
        features.update("".join(chars[index : index + 2]) for index in range(len(chars) - 1))
    return {item for item in features if item}


def lexical_similarity(query: str, text: str) -> float:
    query_features = _features(query)
    if not query_features:
        return 0.0
    target_features = _features(text)
    overlap = len(query_features & target_features) / len(query_features)
    phrase_bonus = 0.0
    normalized_query = _normalized(query)
    if len(normalized_query) >= 3 and normalized_query in _normalized(text):
        phrase_bonus = 0.22
    return min(1.0, overlap * 0.78 + phrase_bonus)


@dataclass
class Page:
    source_path: str
    title: str
    tags: list[str]
    headings: list[str]
    summary: str
    links: list[str]


def _frontmatter_tags(raw: str) -> list[str]:
    match = TAG_LINE.search(raw[:2000])
    if not match:
        return []
    value = match.group(1).strip().strip("[]")
    return [item.strip().strip("'\"") for item in re.split(r"[,，]", value) if item.strip()]


def build_pages(root: Path, files: list[Path]) -> tuple[dict[str, Page], dict[str, set[str]]]:
    pages: dict[str, Page] = {}
    title_to_path: dict[str, str] = {}
    raw_links: dict[str, list[str]] = {}
    for path in files:
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
        clean = clean_markdown(raw)
        source = path.relative_to(root).as_posix()
        headings = [match.group(2).strip() for match in map(HEADING.match, clean.splitlines()) if match]
        title = headings[0] if headings else path.stem
        links = [match.group(1).strip() for match in WIKILINK.finditer(raw)]
        pages[source] = Page(
            source_path=source,
            title=title,
            tags=_frontmatter_tags(raw),
            headings=headings,
            summary=re.sub(r"\s+", " ", clean)[:900],
            links=links,
        )
        title_to_path[path.stem.casefold()] = source
        title_to_path[title.casefold()] = source
        raw_links[source] = links

    graph: dict[str, set[str]] = {source: set() for source in pages}
    for source, links in raw_links.items():
        for link in links:
            target = title_to_path.get(Path(link).name.casefold())
            if target and target != source:
                graph[source].add(target)
    return pages, graph
