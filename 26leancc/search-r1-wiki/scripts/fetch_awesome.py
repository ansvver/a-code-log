#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


AWESOME_README_URL = (
    "https://raw.githubusercontent.com/ventr1c/"
    "Awesome-RL-based-Agentic-Search-Papers/main/README.md"
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 25
MAX_RESPONSE_BYTES = 8_000_000
MAX_FILENAME = 110
SKIP_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".7z",
    ".rar",
    ".mp4",
    ".mp3",
    ".wav",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
}
TEXT_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/xhtml+xml",
    "application/javascript",
    "application/x-javascript",
)


def log(message: str) -> None:
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def slugify(value: str, limit: int = 90) -> str:
    for dash in ("‐", "‑", "‒", "–", "—", "−"):
        value = value.replace(dash, "-")
    value = value.replace("++", " plus plus ")
    value = value.replace("+", " plus ")
    value = value.replace("&", " and ")
    value = value.replace("/", " ")
    normalized = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    normalized = re.sub(r"[-\s]+", "-", normalized)
    normalized = normalized.strip("-")
    if not normalized:
        normalized = "item"
    return normalized[:limit].rstrip("-")


def safe_filename(value: str, limit: int = MAX_FILENAME) -> str:
    base = slugify(value, limit=limit)
    return base or "file"


def short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_markdown(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", value)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"\*([^*]+)\*", r"\1", value)
    value = re.sub(r"_([^_]+)_", r"\1", value)
    return normalize_space(value)


def find_title_col_index(headers: list[str]) -> int | None:
    lowered = [header.lower() for header in headers]
    for key in ("paper", "title", "method", "work"):
        for idx, header in enumerate(lowered):
            if key in header:
                return idx
    has_time_like_col = any(token in header for header in lowered for token in ("time", "date", "year"))
    if has_time_like_col:
        for idx, header in enumerate(lowered):
            if "benchmark" in header:
                return idx
    return None


def split_markdown_table_line(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped:
        if char == "\\" and not escaped:
            escaped = True
            current.append(char)
            continue
        if char == "|" and not escaped:
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
        escaped = False
    cells.append("".join(current).strip())
    return cells


def is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped or "|" not in stripped:
        return False
    cells = split_markdown_table_line(stripped)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "-") for cell in cells)


MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def extract_markdown_links(value: str) -> list[tuple[str, str]]:
    return [(normalize_space(label), url.strip()) for label, url in MARKDOWN_LINK_RE.findall(value)]


def guess_link_kind(label: str, url: str) -> str:
    label_l = label.lower()
    url_l = url.lower()
    if any(token in url_l for token in ("arxiv.org", "openreview.net", "aclweb.org", "aclanthology.org")):
        return "paper"
    if "huggingface.co" in url_l:
        if "/datasets/" in url_l:
            return "dataset"
        return "model"
    if "github.com" in url_l or "gitlab.com" in url_l:
        return "code"
    if any(token in label_l for token in ("paper", "arxiv", "pdf", "openreview", "anthology")):
        return "paper"
    if any(token in label_l for token in ("code", "repo", "github", "gitlab", "implementation")):
        return "code"
    if any(token in label_l for token in ("model", "checkpoint", "weights", "huggingface")):
        return "model"
    if any(token in label_l for token in ("dataset", "data", "benchmark", "corpus")):
        return "dataset"
    if any(token in label_l for token in ("demo", "project", "website", "blog")):
        return "project"

    if any(token in url_l for token in ("dataset", "benchmark", "data")):
        return "dataset"
    return "other"


def refine_kind_by_column(kind: str, column: str) -> str:
    column_l = column.lower()
    if kind == "other" and any(token in column_l for token in ("code", "repo", "implementation")):
        return "code"
    if kind == "other" and any(token in column_l for token in ("dataset", "data", "benchmark", "corpus")):
        return "dataset"
    if kind == "other" and any(token in column_l for token in ("model", "checkpoint", "weights")):
        return "model"
    return kind


@dataclasses.dataclass
class LinkInfo:
    label: str
    url: str
    kind: str
    source_column: str


@dataclasses.dataclass
class ResearchEntry:
    title: str
    slug: str
    primary_url: str | None
    sections: list[str]
    row_markdown: str
    links: list[LinkInfo]
    source_columns: dict[str, str]


def pick_title(headers: list[str], row_cells: list[str], row_line: str) -> str | None:
    title_col_idx = find_title_col_index(headers)
    if title_col_idx is not None and title_col_idx < len(row_cells):
        title_links = extract_markdown_links(row_cells[title_col_idx])
        for label, url in title_links:
            if not url.startswith("#"):
                return strip_markdown(label)
        text = strip_markdown(row_cells[title_col_idx])
        if text and text not in {"paper", "title", "benchmark"}:
            return text

    if row_cells:
        first_cell_links = extract_markdown_links(row_cells[0])
        for label, url in first_cell_links:
            if not url.startswith("#"):
                return strip_markdown(label)

    return None


def build_entry(
    title: str,
    sections: list[str],
    row_line: str,
    headers: list[str],
    row_cells: list[str],
) -> ResearchEntry:
    links: list[LinkInfo] = []
    source_columns: dict[str, str] = {}
    title_col_idx = find_title_col_index(headers)
    title_cell_links: list[tuple[str, str]] = []
    for idx, cell in enumerate(row_cells):
        column = headers[idx] if idx < len(headers) else f"column_{idx+1}"
        source_columns[column] = strip_markdown(cell)
        extracted_links = extract_markdown_links(cell)
        if idx == title_col_idx:
            title_cell_links = [(label, url) for label, url in extracted_links if not url.startswith("#")]
        for label, url in extracted_links:
            if url.startswith("#"):
                continue
            kind = refine_kind_by_column(guess_link_kind(label, url), column)
            links.append(
                LinkInfo(
                    label=label,
                    url=url,
                    kind=kind,
                    source_column=column,
                )
            )

    if not links:
        for label, url in extract_markdown_links(row_line):
            if url.startswith("#"):
                continue
            links.append(
                LinkInfo(label=label, url=url, kind=guess_link_kind(label, url), source_column="row")
            )

    dedup: OrderedDict[str, LinkInfo] = OrderedDict()
    for link in links:
        dedup.setdefault(link.url, link)

    primary_url = None
    for _, url in title_cell_links:
        primary_url = url
        if guess_link_kind(title, url) == "paper":
            break
    if primary_url is None:
        for link in dedup.values():
            if link.kind == "paper":
                primary_url = link.url
                break
    if primary_url is None and dedup:
        primary_url = next(iter(dedup.values())).url

    return ResearchEntry(
        title=normalize_space(title),
        slug=slugify(title),
        primary_url=primary_url,
        sections=sections[:],
        row_markdown=row_line,
        links=list(dedup.values()),
        source_columns=source_columns,
    )


def parse_awesome_readme(markdown: str) -> list[ResearchEntry]:
    entries: OrderedDict[str, ResearchEntry] = OrderedDict()
    lines = markdown.splitlines()
    heading_stack: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            title = normalize_space(heading_match.group(2))
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            idx += 1
            continue

        if "|" in line and idx + 1 < len(lines) and is_table_separator(lines[idx + 1]):
            headers = [strip_markdown(cell) for cell in split_markdown_table_line(line)]
            idx += 2
            while idx < len(lines):
                row_line = lines[idx]
                if not row_line.strip() or "|" not in row_line:
                    break
                row_cells = split_markdown_table_line(row_line)
                title = pick_title(headers, row_cells, row_line)
                if title:
                    candidate = build_entry(title, heading_stack, row_line, headers, row_cells)
                    if not candidate.links:
                        idx += 1
                        continue
                    key = candidate.primary_url or normalize_space(candidate.title).casefold()
                    if key in entries:
                        existing = entries[key]
                        for section in candidate.sections:
                            if section not in existing.sections:
                                existing.sections.append(section)
                        seen_urls = {link.url for link in existing.links}
                        for link in candidate.links:
                            if link.url not in seen_urls:
                                existing.links.append(link)
                        if len(candidate.title) > len(existing.title):
                            existing.title = candidate.title
                            existing.slug = slugify(candidate.title)
                        if existing.primary_url is None and candidate.primary_url is not None:
                            existing.primary_url = candidate.primary_url
                        if len(candidate.row_markdown) > len(existing.row_markdown):
                            existing.row_markdown = candidate.row_markdown
                        existing.source_columns.update(candidate.source_columns)
                    else:
                        entries[key] = candidate
                idx += 1
            continue

        bullet_match = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bullet_match and "(" in line and ")" in line:
            content = bullet_match.group(1)
            if not content.lstrip().startswith("["):
                idx += 1
                continue
            links = [(label, url) for label, url in extract_markdown_links(content) if not url.startswith("#")]
            if links:
                title = strip_markdown(content)
                candidate = ResearchEntry(
                    title=title,
                    slug=slugify(title),
                    primary_url=links[0][1],
                    sections=heading_stack[:],
                    row_markdown=line,
                    links=[
                        LinkInfo(
                            label=label,
                            url=url,
                            kind=guess_link_kind(label, url),
                            source_column="bullet",
                        )
                        for label, url in links
                    ],
                    source_columns={"bullet": strip_markdown(content)},
                )
                entries.setdefault(candidate.primary_url or normalize_space(title).casefold(), candidate)

        idx += 1

    resolved = list(entries.values())
    seen_slugs: dict[str, int] = {}
    for entry in resolved:
        base_slug = slugify(entry.title)
        count = seen_slugs.get(base_slug, 0)
        if count == 0:
            entry.slug = base_slug
        else:
            entry.slug = f"{base_slug}-{short_hash(entry.primary_url or entry.title)}"
        seen_slugs[base_slug] = count + 1

    return resolved


class HTMLTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "p",
        "div",
        "article",
        "section",
        "header",
        "footer",
        "nav",
        "main",
        "aside",
        "ul",
        "ol",
        "li",
        "table",
        "tr",
        "td",
        "th",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "pre",
        "code",
        "blockquote",
        "br",
    }
    SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._pieces: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self._pieces.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self._pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = normalize_space(data)
        if text:
            self._pieces.append(text)
            self._pieces.append(" ")

    def get_text(self) -> str:
        joined = "".join(self._pieces)
        joined = re.sub(r"\n\s*\n\s*\n+", "\n\n", joined)
        joined = re.sub(r"[ \t]+\n", "\n", joined)
        return joined.strip()


def extract_text_from_html(html: str) -> str:
    extractor = HTMLTextExtractor()
    try:
        extractor.feed(html)
        extractor.close()
    except Exception:
        return normalize_space(re.sub(r"<[^>]+>", " ", html))
    return extractor.get_text()


def read_limited(response) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = response.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise ValueError(f"response too large: {total} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def request_url(url: str, accept: str | None = None) -> tuple[bytes, str, str]:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        data = read_limited(response)
        content_type = response.headers.get("Content-Type", "")
        final_url = response.geturl()
    return data, content_type, final_url


def decode_bytes(data: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([^\s;]+)", content_type, flags=re.IGNORECASE)
    if charset_match:
        charset = charset_match.group(1).strip("\"'")
        try:
            return data.decode(charset, errors="replace")
        except LookupError:
            pass
    for charset in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(charset, errors="replace")
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in {"http", "https"}:
        return url
    return urllib.parse.urljoin("https://github.com/", url)


def maybe_skip_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext in SKIP_EXTENSIONS:
        return f"unsupported extension: {ext}"
    return None


def normalize_arxiv_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if "arxiv.org" not in parsed.netloc:
        return url
    if parsed.path.startswith("/pdf/"):
        paper_id = parsed.path.removeprefix("/pdf/")
        paper_id = paper_id.removesuffix(".pdf")
        new_path = f"/abs/{paper_id}"
        return urllib.parse.urlunparse(parsed._replace(path=new_path, query="", fragment=""))
    return url


def parse_github_target(url: str) -> dict[str, str] | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in {"github.com", "www.github.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    info = {"owner": owner, "repo": repo}
    rest = parts[2:]
    if not rest:
        info["mode"] = "root"
        return info
    if rest[0] in {"tree", "blob"} and len(rest) >= 2:
        info["mode"] = rest[0]
        info["ref"] = rest[1]
        info["path"] = "/".join(rest[2:])
        return info
    info["mode"] = "other"
    info["path"] = "/".join(rest)
    return info


def github_default_branch(owner: str, repo: str) -> str | None:
    html_bytes, content_type, _ = request_url(f"https://github.com/{owner}/{repo}")
    if "html" not in content_type:
        return None
    html = decode_bytes(html_bytes, content_type)
    patterns = [
        r'"defaultBranch":"([^"]+)"',
        r'octolytics-dimension-repository_default_branch"\s+content="([^"]+)"',
        r'"default_branch":"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return None


def fetch_github_readme(url: str) -> tuple[str, str, str, str] | None:
    target = parse_github_target(url)
    if not target:
        return None

    owner = target["owner"]
    repo = target["repo"]
    mode = target["mode"]
    ref = target.get("ref")
    base_path = target.get("path", "")

    if mode == "blob" and base_path:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{base_path}"
        data, content_type, final_url = request_url(raw_url)
        text = decode_bytes(data, content_type)
        suffix = Path(base_path).suffix.lower() or ".txt"
        return text, "markdown" if "markdown" in content_type or suffix in {".md", ".rst"} else "text", final_url, content_type

    if mode == "other":
        return None

    branch = ref or github_default_branch(owner, repo) or "main"
    prefix = base_path.strip("/")
    candidates = ["README.md", "readme.md", "README.rst", "README.txt", "Readme.md"]
    branches = [branch]
    if branch not in {"main", "master"}:
        branches.extend(["main", "master"])
    else:
        branches.extend(["master"] if branch == "main" else ["main"])

    tried: set[str] = set()
    for branch_name in branches:
        for candidate in candidates:
            parts = [part for part in (prefix, candidate) if part]
            raw_path = "/".join(parts)
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch_name}/{raw_path}"
            if raw_url in tried:
                continue
            tried.add(raw_url)
            try:
                data, content_type, final_url = request_url(raw_url)
            except Exception:
                continue
            text = decode_bytes(data, content_type)
            suffix = Path(candidate).suffix.lower() or ".txt"
            kind = "markdown" if suffix in {".md", ".rst"} else "text"
            return text, kind, final_url, content_type
    return None


def parse_huggingface_target(url: str) -> dict[str, str] | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in {"huggingface.co", "www.huggingface.co"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    repo_type = "models"
    if parts[0] in {"datasets", "spaces"}:
        if len(parts) < 3:
            return None
        repo_type = parts[0]
        namespace = parts[1]
        repo = parts[2]
        rest = parts[3:]
    else:
        namespace = parts[0]
        repo = parts[1]
        rest = parts[2:]
    info = {"repo_type": repo_type, "namespace": namespace, "repo": repo}
    if not rest:
        info["mode"] = "root"
        return info
    if rest[0] in {"blob", "resolve", "raw"} and len(rest) >= 2:
        info["mode"] = rest[0]
        info["ref"] = rest[1]
        info["path"] = "/".join(rest[2:])
        return info
    info["mode"] = "other"
    info["path"] = "/".join(rest)
    return info


def build_hf_prefix(target: dict[str, str]) -> str:
    repo_type = target["repo_type"]
    namespace = target["namespace"]
    repo = target["repo"]
    if repo_type == "models":
        return f"https://huggingface.co/{namespace}/{repo}"
    return f"https://huggingface.co/{repo_type}/{namespace}/{repo}"


def fetch_huggingface_card(url: str) -> tuple[str, str, str, str] | None:
    target = parse_huggingface_target(url)
    if not target or target["mode"] == "other":
        return None

    prefix = build_hf_prefix(target)
    if target["mode"] in {"blob", "resolve", "raw"} and target.get("path"):
        raw_url = f"{prefix}/raw/{target['ref']}/{target['path']}"
        data, content_type, final_url = request_url(raw_url)
        text = decode_bytes(data, content_type)
        suffix = Path(target["path"]).suffix.lower() or ".txt"
        kind = "markdown" if suffix in {".md", ".rst"} else "text"
        return text, kind, final_url, content_type

    for branch in ("main", "master"):
        for candidate in ("README.md", "readme.md"):
            raw_url = f"{prefix}/raw/{branch}/{candidate}"
            try:
                data, content_type, final_url = request_url(raw_url)
            except Exception:
                continue
            text = decode_bytes(data, content_type)
            return text, "markdown", final_url, content_type
    return None


def extract_text_content(url: str) -> dict[str, object]:
    original_url = normalize_url(url)
    normalized_url = normalize_arxiv_url(original_url)
    skip_reason = maybe_skip_url(normalized_url)
    if skip_reason:
        return {
            "url": original_url,
            "normalized_url": normalized_url,
            "status": "skipped",
            "skip_reason": skip_reason,
        }

    special_fetchers = (fetch_github_readme, fetch_huggingface_card)
    for fetcher in special_fetchers:
        try:
            result = fetcher(normalized_url)
        except Exception as exc:
            result = None
            special_error = str(exc)
        else:
            special_error = None
        if result is None:
            if special_error:
                continue
            continue
        text, text_kind, final_url, content_type = result
        return {
            "url": original_url,
            "normalized_url": normalized_url,
            "final_url": final_url,
            "status": "ok",
            "content_type": content_type,
            "text_kind": text_kind,
            "raw_text": text,
            "extracted_text": text if text_kind in {"markdown", "text"} else normalize_space(text),
            "raw_bytes": None,
        }

    data, content_type, final_url = request_url(normalized_url)
    content_type_l = content_type.lower()
    if "application/pdf" in content_type_l or final_url.lower().endswith(".pdf"):
        return {
            "url": original_url,
            "normalized_url": normalized_url,
            "final_url": final_url,
            "status": "ok",
            "content_type": content_type,
            "text_kind": "pdf",
            "raw_bytes": data,
            "raw_text": None,
            "extracted_text": "",
        }

    text = decode_bytes(data, content_type)
    if "html" in content_type_l:
        extracted = extract_text_from_html(text)
        text_kind = "html"
    elif any(content_type_l.startswith(prefix) for prefix in TEXT_CONTENT_TYPES) or not content_type_l:
        extracted = text
        text_kind = "text"
    else:
        extracted = text
        text_kind = "text"

    return {
        "url": original_url,
        "normalized_url": normalized_url,
        "final_url": final_url,
        "status": "ok",
        "content_type": content_type,
        "text_kind": text_kind,
        "raw_text": text,
        "raw_bytes": None,
        "extracted_text": extracted,
    }


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def save_link_payload(entry_dir: Path, index: int, link: LinkInfo, payload: dict[str, object]) -> dict[str, object]:
    label_part = safe_filename(link.label or link.kind, limit=36)
    host_part = safe_filename(urllib.parse.urlparse(link.url).netloc or "site", limit=28)
    base = f"link_{index:02d}_{link.kind}_{host_part}_{label_part}"
    meta_path = unique_path(entry_dir / f"{base}.meta.json")

    file_info: dict[str, str] = {}
    if payload.get("raw_text") is not None:
        text_kind = payload.get("text_kind", "text")
        ext = ".md" if text_kind == "markdown" else ".html" if text_kind == "html" else ".txt"
        raw_path = meta_path.with_suffix(f".raw{ext}")
        write_text(raw_path, str(payload["raw_text"]))
        file_info["raw"] = raw_path.name

    if payload.get("raw_bytes") is not None:
        raw_path = meta_path.with_suffix(".raw.pdf")
        raw_path.write_bytes(payload["raw_bytes"])  # type: ignore[arg-type]
        file_info["raw"] = raw_path.name

    extracted_text = str(payload.get("extracted_text", "") or "")
    text_path = meta_path.with_suffix(".text.txt")
    write_text(text_path, extracted_text)
    file_info["text"] = text_path.name

    meta_payload = {
        "label": link.label,
        "kind": link.kind,
        "source_column": link.source_column,
        "source_url": link.url,
        "fetch": {
            "status": payload.get("status"),
            "url": payload.get("url"),
            "normalized_url": payload.get("normalized_url"),
            "final_url": payload.get("final_url"),
            "content_type": payload.get("content_type"),
            "text_kind": payload.get("text_kind"),
            "skip_reason": payload.get("skip_reason"),
        },
        "files": file_info,
    }
    write_json(meta_path, meta_payload)
    return meta_payload


def fetch_and_store_entry(entry: ResearchEntry, raw_dir: Path, throttle: float) -> dict[str, object]:
    entry_dir = raw_dir / entry.slug
    entry_dir.mkdir(parents=True, exist_ok=True)

    write_text(entry_dir / "awesome_entry.md", entry.row_markdown + "\n")
    write_json(
        entry_dir / "metadata.json",
        {
            "title": entry.title,
            "slug": entry.slug,
            "primary_url": entry.primary_url,
            "sections": entry.sections,
            "source_columns": entry.source_columns,
            "links": [dataclasses.asdict(link) for link in entry.links],
        },
    )

    results = []
    for index, link in enumerate(entry.links, start=1):
        time.sleep(throttle)
        try:
            payload = extract_text_content(link.url)
        except Exception as exc:
            payload = {
                "url": link.url,
                "normalized_url": normalize_arxiv_url(normalize_url(link.url)),
                "status": "error",
                "error": repr(exc),
            }
        meta_payload = save_link_payload(entry_dir, index, link, payload)
        if "error" in payload:
            meta_payload["fetch"]["error"] = payload["error"]  # type: ignore[index]
        results.append(meta_payload)

    manifest = {
        "title": entry.title,
        "slug": entry.slug,
        "primary_url": entry.primary_url,
        "sections": entry.sections,
        "link_count": len(entry.links),
        "fetched_count": sum(1 for item in results if item["fetch"]["status"] == "ok"),
        "failed_count": sum(1 for item in results if item["fetch"]["status"] in {"error", "skipped"}),
        "results": results,
    }
    write_json(entry_dir / "manifest.json", manifest)
    return manifest


def sort_links(entry: ResearchEntry) -> None:
    priority = {"paper": 0, "code": 1, "model": 2, "dataset": 3, "project": 4, "other": 5}
    entry.links.sort(key=lambda link: (priority.get(link.kind, 9), link.source_column, link.label, link.url))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect raw webpages for RL-based agentic search papers.")
    parser.add_argument("--raw-dir", default="raw", help="Output directory.")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N entries.")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent entry workers.")
    parser.add_argument("--throttle", type=float, default=0.2, help="Delay between requests within one entry.")
    parser.add_argument("--clean", action="store_true", help="Remove existing contents under the output directory before running.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    raw_dir = Path(args.raw_dir).resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    if args.clean:
        for child in raw_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    log(f"Downloading awesome README from {AWESOME_README_URL}")
    readme_bytes, content_type, final_url = request_url(AWESOME_README_URL)
    readme_text = decode_bytes(readme_bytes, content_type)

    source_dir = raw_dir / "_source"
    source_dir.mkdir(parents=True, exist_ok=True)
    write_text(source_dir / "awesome_README.md", readme_text)
    write_json(
        source_dir / "awesome_source.json",
        {
            "url": AWESOME_README_URL,
            "final_url": final_url,
            "content_type": content_type,
            "downloaded_at": int(time.time()),
        },
    )

    entries = parse_awesome_readme(readme_text)
    for entry in entries:
        sort_links(entry)

    if args.limit > 0:
        entries = entries[: args.limit]

    log(f"Parsed {len(entries)} research entries")
    index_lock = threading.Lock()
    completed = 0
    manifests: list[dict[str, object]] = []

    def worker(entry: ResearchEntry) -> dict[str, object]:
        manifest = fetch_and_store_entry(entry, raw_dir, args.throttle)
        nonlocal completed
        with index_lock:
            completed += 1
            log(f"[{completed}/{len(entries)}] {entry.slug}")
        return manifest

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(worker, entry) for entry in entries]
        for future in concurrent.futures.as_completed(futures):
            manifests.append(future.result())

    manifests.sort(key=lambda item: str(item["slug"]))
    write_json(raw_dir / "index.json", manifests)
    summary = {
        "entry_count": len(manifests),
        "fetched_count": sum(int(item["fetched_count"]) for item in manifests),
        "failed_count": sum(int(item["failed_count"]) for item in manifests),
    }
    write_json(raw_dir / "summary.json", summary)
    log(f"Finished. Entries={summary['entry_count']} fetched={summary['fetched_count']} failed={summary['failed_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
