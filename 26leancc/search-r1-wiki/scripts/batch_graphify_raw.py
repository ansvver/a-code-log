#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from graphify.analyze import god_nodes, suggest_questions, surprising_connections
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.detect import detect
from graphify.export import to_html, to_json
from graphify.report import generate


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

MAX_GENERIC_DIR_FILES = 60
MAX_JSON_LIST_ITEMS = 30
MAX_TEXT_HEADINGS = 18
MAX_TEXT_LINKS = 24
MAX_CSV_ROWS = 60
MAX_CSV_VALUE_FIELDS = 8
MAX_VALUE_LENGTH = 120

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "via",
    "with",
    "without",
    "paper",
    "papers",
    "resource",
    "resources",
    "document",
    "documents",
    "research",
    "entry",
    "entries",
    "community",
    "section",
    "sections",
}

FIELD_RELATIONS = {
    "Method": "presents",
    "Paper Title": "titled",
    "RL Func. Role": "targets_role",
    "Training Env.": "uses_training_env",
    "RL Alg.": "uses_algorithm",
    "Reward Type": "uses_reward_type",
    "Reward Func.": "optimizes_reward_function",
    "Opt. Scope": "optimizes_scope",
    "Dataset": "evaluated_on",
    "Time": "published_at",
    "Role": "categorized_as",
    "Venue": "published_in",
    "Cold Start?": "has_cold_start",
    "Code": "has_code",
}

RESOURCE_RELATIONS = {
    "paper": "references",
    "dataset": "evaluated_on",
    "code": "has_code",
    "model": "releases_model",
    "space": "references",
    "collection": "references",
}

TITLE_FIELDS = ("title", "label", "name", "slug", "paper_title", "research_title", "question", "id", "url")

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", flags=re.MULTILINE)


def clean_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\\_", "_")
    text = re.sub(r"<br\s*/?>", " | ", text, flags=re.IGNORECASE)
    text = re.sub(r"`+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slugify(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "node"


def split_metadata_values(raw: Any) -> list[str]:
    text = clean_text(raw)
    if not text:
        return []
    text = text.strip("[]")
    parts = re.split(r"\s*\|\s*|\s*,\s*", text)
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        part = clean_text(part).strip("[]")
        if not part:
            continue
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(part)
    return result


def pick_label(item: Any) -> str:
    if isinstance(item, dict):
        for field in TITLE_FIELDS:
            value = item.get(field)
            if value:
                return clean_text(value)
        return clean_text(json.dumps(item, ensure_ascii=False, sort_keys=True))[:MAX_VALUE_LENGTH]
    if isinstance(item, list):
        return f"List[{len(item)}]"
    return clean_text(item)[:MAX_VALUE_LENGTH]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def rel_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except Exception:
        return str(path)


class ExtractionBuilder:
    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.hyperedges: list[dict[str, Any]] = []
        self._nodes_seen: set[str] = set()
        self._edges_seen: set[tuple[str, str, str, str]] = set()
        self.input_tokens = 0
        self.output_tokens = 0

    def add_node(
        self,
        node_id: str,
        label: str,
        file_type: str,
        source_file: str,
        *,
        source_url: str | None = None,
        source_location: str | None = None,
    ) -> str:
        node_id = slugify(node_id)
        if node_id in self._nodes_seen:
            return node_id
        self._nodes_seen.add(node_id)
        self.nodes.append(
            {
                "id": node_id,
                "label": clean_text(label)[:200] or node_id,
                "file_type": file_type,
                "source_file": source_file,
                "source_location": source_location,
                "source_url": source_url,
            }
        )
        return node_id

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        source_file: str,
        *,
        confidence: str = "EXTRACTED",
        confidence_score: float = 1.0,
        source_location: str | None = None,
        weight: float = 1.0,
    ) -> None:
        key = (source, target, relation, source_file)
        if key in self._edges_seen:
            return
        self._edges_seen.add(key)
        self.edges.append(
            {
                "source": source,
                "target": target,
                "relation": relation,
                "confidence": confidence,
                "confidence_score": confidence_score,
                "source_file": source_file,
                "source_location": source_location,
                "weight": weight,
            }
        )

    def add_hyperedge(
        self,
        hyperedge_id: str,
        label: str,
        nodes: list[str],
        source_file: str,
        *,
        relation: str = "form",
        confidence: str = "EXTRACTED",
        confidence_score: float = 1.0,
    ) -> None:
        deduped = list(dict.fromkeys(nodes))
        if len(deduped) < 3:
            return
        self.hyperedges.append(
            {
                "id": slugify(hyperedge_id),
                "label": clean_text(label),
                "nodes": deduped,
                "relation": relation,
                "confidence": confidence,
                "confidence_score": confidence_score,
                "source_file": source_file,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "hyperedges": self.hyperedges,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def value_node_id(base: str, relation: str, value: str) -> str:
    return f"{base}__{slugify(relation)}__{slugify(value)}"


def resource_node_id(base: str, kind: str, label: str, source_url: str | None) -> str:
    seed = source_url or label
    return f"{base}__{slugify(kind)}__{slugify(seed)}"


def file_root_id(base: str, rel_path: str) -> str:
    return f"{base}__file__{slugify(rel_path)}"


def extract_text_file(builder: ExtractionBuilder, file_path: Path, rel_path: str, parent_id: str | None = None) -> str:
    text = read_text(file_path)
    root_id = builder.add_node(file_root_id(rel_path, rel_path), file_path.name, "document", rel_path)
    if parent_id:
        builder.add_edge(parent_id, root_id, "contains", rel_path)

    headings = []
    seen_heading_ids: set[str] = set()
    for idx, match in enumerate(HEADING_RE.finditer(text), start=1):
        if len(headings) >= MAX_TEXT_HEADINGS:
            break
        heading = clean_text(match.group(2))
        if not heading:
            continue
        heading_id = slugify(f"{root_id}__heading__{heading}")
        if heading_id in seen_heading_ids:
            continue
        seen_heading_ids.add(heading_id)
        headings.append(heading_id)
        builder.add_node(heading_id, heading, "document", rel_path, source_location=f"heading:{idx}")
        builder.add_edge(root_id, heading_id, "contains", rel_path, source_location=f"heading:{idx}")

    seen_links: set[str] = set()
    for idx, (label, url) in enumerate(MARKDOWN_LINK_RE.findall(text), start=1):
        if idx > MAX_TEXT_LINKS:
            break
        clean_label = clean_text(label)
        clean_url = clean_text(url)
        if not clean_label or clean_url in seen_links:
            continue
        seen_links.add(clean_url)
        link_id = slugify(f"{root_id}__link__{clean_url}")
        builder.add_node(link_id, clean_label, "document", rel_path, source_url=clean_url, source_location=f"link:{idx}")
        builder.add_edge(root_id, link_id, "references", rel_path, source_location=f"link:{idx}")

    if not headings and not seen_links:
        lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
        for idx, line in enumerate(lines[:8], start=1):
            node_id = slugify(f"{root_id}__line__{idx}")
            builder.add_node(node_id, line[:MAX_VALUE_LENGTH], "document", rel_path, source_location=f"line:{idx}")
            builder.add_edge(root_id, node_id, "contains", rel_path, source_location=f"line:{idx}")

    return root_id


def extract_json_value(
    builder: ExtractionBuilder,
    parent_id: str,
    rel_path: str,
    key: str,
    value: Any,
    *,
    max_items: int = MAX_JSON_LIST_ITEMS,
) -> None:
    relation = "has_field"
    field_id = slugify(f"{parent_id}__field__{key}")
    builder.add_node(field_id, key, "document", rel_path)
    builder.add_edge(parent_id, field_id, relation, rel_path)

    if isinstance(value, dict):
        for idx, (sub_key, sub_value) in enumerate(value.items(), start=1):
            if idx > max_items:
                break
            child_label = pick_label(sub_value)
            child_id = slugify(f"{field_id}__{sub_key}__{child_label}")
            builder.add_node(child_id, f"{sub_key}: {child_label}"[:200], "document", rel_path)
            builder.add_edge(field_id, child_id, "contains", rel_path)
    elif isinstance(value, list):
        count_id = slugify(f"{field_id}__count__{len(value)}")
        builder.add_node(count_id, f"{len(value)} item(s)", "document", rel_path)
        builder.add_edge(field_id, count_id, "summarizes", rel_path)
        for idx, item in enumerate(value[:max_items], start=1):
            item_label = pick_label(item)
            item_id = slugify(f"{field_id}__item__{idx}__{item_label}")
            builder.add_node(item_id, item_label[:200], "document", rel_path, source_location=f"item:{idx}")
            builder.add_edge(field_id, item_id, "contains", rel_path, source_location=f"item:{idx}")
    else:
        literal = clean_text(value)
        if not literal:
            return
        literal_id = slugify(f"{field_id}__value__{literal}")
        builder.add_node(literal_id, literal[:200], "document", rel_path)
        builder.add_edge(field_id, literal_id, "describes", rel_path)


def extract_json_file(builder: ExtractionBuilder, file_path: Path, rel_path: str, parent_id: str | None = None) -> str:
    data = load_json(file_path)
    root_id = builder.add_node(file_root_id(rel_path, rel_path), file_path.name, "document", rel_path)
    if parent_id:
        builder.add_edge(parent_id, root_id, "contains", rel_path)

    if isinstance(data, dict):
        for idx, (key, value) in enumerate(data.items(), start=1):
            if idx > MAX_JSON_LIST_ITEMS:
                break
            extract_json_value(builder, root_id, rel_path, key, value)
    elif isinstance(data, list):
        count_id = slugify(f"{root_id}__count__{len(data)}")
        builder.add_node(count_id, f"{len(data)} item(s)", "document", rel_path)
        builder.add_edge(root_id, count_id, "summarizes", rel_path)
        for idx, item in enumerate(data[:MAX_JSON_LIST_ITEMS], start=1):
            item_label = pick_label(item)
            item_id = slugify(f"{root_id}__item__{idx}__{item_label}")
            builder.add_node(item_id, item_label[:200], "document", rel_path, source_location=f"item:{idx}")
            builder.add_edge(root_id, item_id, "contains", rel_path, source_location=f"item:{idx}")
    else:
        value_id = slugify(f"{root_id}__value__{data}")
        builder.add_node(value_id, clean_text(data)[:200], "document", rel_path)
        builder.add_edge(root_id, value_id, "describes", rel_path)

    return root_id


def extract_csv_file(builder: ExtractionBuilder, file_path: Path, rel_path: str, parent_id: str | None = None) -> str:
    root_id = builder.add_node(file_root_id(rel_path, rel_path), file_path.name, "document", rel_path)
    if parent_id:
        builder.add_edge(parent_id, root_id, "contains", rel_path)

    with file_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        header_nodes: dict[str, str] = {}
        for field in fieldnames[:MAX_CSV_VALUE_FIELDS]:
            field_id = slugify(f"{root_id}__column__{field}")
            header_nodes[field] = builder.add_node(field_id, field, "document", rel_path)
            builder.add_edge(root_id, field_id, "has_field", rel_path)
        for idx, row in enumerate(reader, start=1):
            if idx > MAX_CSV_ROWS:
                break
            row_label = (
                clean_text(row.get("Paper Title"))
                or clean_text(row.get("Method"))
                or clean_text(row.get("title"))
                or f"row {idx}"
            )
            row_id = slugify(f"{root_id}__row__{idx}__{row_label}")
            builder.add_node(row_id, row_label[:200], "document", rel_path, source_location=f"row:{idx}")
            builder.add_edge(root_id, row_id, "contains", rel_path, source_location=f"row:{idx}")
            for field in fieldnames[:MAX_CSV_VALUE_FIELDS]:
                value = clean_text(row.get(field))
                if not value:
                    continue
                value_id = slugify(f"{row_id}__{field}__{value}")
                builder.add_node(value_id, value[:200], "document", rel_path)
                builder.add_edge(row_id, value_id, "describes", rel_path)
                header_id = header_nodes.get(field)
                if header_id:
                    builder.add_edge(header_id, value_id, "contains", rel_path)
    return root_id


def extract_generic_file(item_path: Path, rel_item_path: str, detection: dict[str, Any]) -> dict[str, Any]:
    builder = ExtractionBuilder()
    suffix = item_path.suffix.lower()
    if suffix in {".md", ".txt", ".html"}:
        extract_text_file(builder, item_path, rel_item_path)
    elif suffix == ".json":
        extract_json_file(builder, item_path, rel_item_path)
    elif suffix in {".csv", ".tsv"}:
        extract_csv_file(builder, item_path, rel_item_path)
    else:
        root_id = builder.add_node(file_root_id(rel_item_path, rel_item_path), item_path.name, "document", rel_item_path)
        note_id = builder.add_node(f"{root_id}__unsupported", "Structured extraction not available for this file type", "document", rel_item_path)
        builder.add_edge(root_id, note_id, "describes", rel_item_path)
    return builder.to_dict()


def extract_generic_directory(item_path: Path, rel_item_path: str, detection: dict[str, Any]) -> dict[str, Any]:
    builder = ExtractionBuilder()
    files_by_kind = detection.get("files", {})
    all_files: list[str] = []
    for kind in ("document", "paper", "code", "image", "video"):
        all_files.extend(files_by_kind.get(kind, []))

    file_paths = [Path(path) for path in all_files]
    file_paths = [path for path in file_paths if path.is_file()]

    preferred_names = {"metadata.json", "manifest.json", "README.md", "summary.json", "index.json", "awesome_entry.md"}

    def priority(path: Path) -> tuple[int, str]:
        name_priority = 0 if path.name in preferred_names else 1
        suffix_priority = 0 if path.suffix.lower() in {".json", ".md", ".txt"} else 1
        return (name_priority + suffix_priority, rel_to_repo(path))

    file_paths = sorted(file_paths, key=priority)[:MAX_GENERIC_DIR_FILES]

    root_source = rel_to_repo(file_paths[0]) if file_paths else rel_item_path
    root_id = builder.add_node(slugify(f"{rel_item_path}__root"), item_path.name, "document", root_source)

    for file_path in file_paths:
        rel_path = rel_to_repo(file_path)
        suffix = file_path.suffix.lower()
        if suffix in {".md", ".txt", ".html"}:
            extract_text_file(builder, file_path, rel_path, root_id)
        elif suffix == ".json":
            extract_json_file(builder, file_path, rel_path, root_id)
        elif suffix in {".csv", ".tsv"}:
            extract_csv_file(builder, file_path, rel_path, root_id)
        else:
            file_id = builder.add_node(file_root_id(rel_path, rel_path), file_path.name, "document", rel_path)
            builder.add_edge(root_id, file_id, "contains", rel_path)

    if len(file_paths) >= 3:
        file_nodes = [file_root_id(rel_to_repo(path), rel_to_repo(path)) for path in file_paths[:8]]
        builder.add_hyperedge(
            f"{rel_item_path}__file_cluster",
            f"{item_path.name} Files",
            file_nodes,
            root_source,
        )

    return builder.to_dict()


def load_manifest_results(manifest_path: Path) -> list[dict[str, Any]]:
    if not manifest_path.exists():
        return []
    payload = load_json(manifest_path)
    results = payload.get("results", [])
    return [item for item in results if isinstance(item, dict)]


def find_resource_source_file(item_path: Path, result: dict[str, Any]) -> str:
    files = result.get("files") or {}
    for key in ("text", "raw"):
        rel_name = files.get(key)
        if rel_name:
            path = item_path / rel_name
            if path.exists():
                return rel_to_repo(path)
    return rel_to_repo(item_path / "manifest.json")


def normalize_resource_label(value: str) -> str:
    label = clean_text(value).strip("[]")
    label = label.replace("  ", " ")
    return label


def build_research_extraction(item_path: Path, rel_item_path: str, detection: dict[str, Any]) -> dict[str, Any]:
    builder = ExtractionBuilder()
    metadata_path = item_path / "metadata.json"
    manifest_path = item_path / "manifest.json"
    awesome_path = item_path / "awesome_entry.md"

    metadata = load_json(metadata_path)
    results = load_manifest_results(manifest_path)

    paper_title = clean_text(metadata.get("title") or item_path.name)
    paper_slug = metadata.get("slug") or item_path.name
    primary_url = clean_text(metadata.get("primary_url"))
    paper_source = rel_to_repo(metadata_path)
    paper_id = builder.add_node(
        f"{paper_slug}__paper",
        paper_title,
        "paper",
        paper_source,
        source_url=primary_url or None,
    )

    resource_ids_by_label: dict[str, str] = {}
    grouped_resources: dict[str, list[str]] = {"paper": [], "dataset": [], "model": [], "code": []}
    field_hubs: dict[str, str] = {}
    kind_hubs: dict[str, str] = {}

    for field, raw_value in (metadata.get("source_columns") or {}).items():
        if not split_metadata_values(raw_value):
            continue
        hub_id = builder.add_node(
            f"{paper_slug}__field__{field}",
            field,
            "document",
            paper_source,
        )
        builder.add_edge(paper_id, hub_id, "has_field", paper_source)
        field_hubs[field] = hub_id

    for idx, result in enumerate(results, start=1):
        label = normalize_resource_label(result.get("label") or f"resource {idx}")
        kind = clean_text(result.get("kind") or "document").lower()
        source_url = clean_text(result.get("source_url") or result.get("fetch", {}).get("final_url"))
        source_file = find_resource_source_file(item_path, result)
        node_file_type = "paper" if kind == "paper" else ("code" if kind == "code" else "document")
        if kind == "paper" and source_url and source_url == primary_url:
            node_id = paper_id
        else:
            node_id = resource_node_id(paper_slug, kind, label, source_url)
            builder.add_node(node_id, label, node_file_type, source_file, source_url=source_url or None)
        relation = RESOURCE_RELATIONS.get(kind, "references")
        kind_label = {
            "paper": "Linked Papers",
            "dataset": "Datasets",
            "model": "Models",
            "code": "Code Artifacts",
        }.get(kind, f"{kind.title()} Resources")
        kind_hub = kind_hubs.get(kind)
        if not kind_hub:
            kind_hub = builder.add_node(
                f"{paper_slug}__kind__{kind}",
                kind_label,
                "document",
                rel_to_repo(manifest_path),
            )
            builder.add_edge(paper_id, kind_hub, "groups_resources", rel_to_repo(manifest_path))
            kind_hubs[kind] = kind_hub
        if node_id != kind_hub:
            builder.add_edge(kind_hub, node_id, relation, source_file)
        source_column = clean_text(result.get("source_column"))
        if source_column in field_hubs and node_id != field_hubs[source_column]:
            builder.add_edge(field_hubs[source_column], node_id, relation, source_file)
        resource_ids_by_label[slugify(label)] = node_id
        if node_id != paper_id:
            grouped_resources.setdefault(kind, []).append(node_id)

    for section in metadata.get("sections", []):
        clean_section = clean_text(section)
        if not clean_section:
            continue
        source_file = rel_to_repo(awesome_path) if awesome_path.exists() else paper_source
        section_id = builder.add_node(
            f"{paper_slug}__section__{clean_section}",
            clean_section,
            "document",
            source_file,
        )
        builder.add_edge(paper_id, section_id, "organized_into", source_file)

    for field, raw_value in (metadata.get("source_columns") or {}).items():
        values = split_metadata_values(raw_value)
        if not values:
            continue
        relation = FIELD_RELATIONS.get(field, "describes")
        hub_id = field_hubs.get(field, paper_id)
        for value in values:
            if field == "Paper Title" and value == paper_title:
                continue
            existing = resource_ids_by_label.get(slugify(value))
            if existing:
                node_id = existing
            else:
                node_id = builder.add_node(
                    value_node_id(paper_slug, relation, value),
                    value,
                    "document",
                    paper_source,
                )
            if hub_id != node_id:
                builder.add_edge(hub_id, node_id, relation, paper_source)

    for kind, node_ids in grouped_resources.items():
        if len(node_ids) >= 3:
            label = {
                "dataset": "Benchmark Datasets",
                "model": "Released Models",
                "code": "Code Artifacts",
                "paper": "Linked Papers",
            }.get(kind, f"{kind.title()} Resources")
            builder.add_hyperedge(
                f"{paper_slug}__{kind}_group",
                label,
                node_ids,
                rel_to_repo(manifest_path),
            )

    return builder.to_dict()


def auto_label_communities(G: Any, communities: dict[int, list[str]]) -> dict[int, str]:
    labels: dict[int, str] = {}
    for cid, nodes in communities.items():
        ranked = sorted(nodes, key=lambda node_id: G.degree(node_id), reverse=True)
        candidate_labels = [
            clean_text(G.nodes[node_id].get("label", ""))
            for node_id in ranked
            if clean_text(G.nodes[node_id].get("label", ""))
            and "." not in clean_text(G.nodes[node_id].get("label", ""))[:10]
        ]

        for candidate in candidate_labels:
            primary = candidate.split(":")[0].strip()
            words = primary.split()
            if 1 <= len(words) <= 4 and len(primary) <= 40:
                labels[cid] = primary
                break

        if cid in labels:
            continue

        token_counts: Counter[str] = Counter()
        for candidate in candidate_labels[:8]:
            for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9.+/-]*", candidate):
                norm = token.lower().strip(".")
                if len(norm) < 3 or norm in STOPWORDS or norm.isdigit():
                    continue
                token_counts[norm] += 1

        if token_counts:
            top_tokens = [token.title() for token, _ in token_counts.most_common(3)]
            labels[cid] = " ".join(top_tokens[:3])
        elif candidate_labels:
            labels[cid] = " ".join(candidate_labels[0].split()[:3])
        else:
            labels[cid] = f"Community {cid}"
    return labels


def process_item(item_path: Path, out_root: Path) -> dict[str, Any]:
    rel_item_path = rel_to_repo(item_path)
    detection = detect(item_path)

    if item_path.is_dir() and (item_path / "metadata.json").exists():
        extraction = build_research_extraction(item_path, rel_item_path, detection)
        mode = "research_dir"
    elif item_path.is_dir():
        extraction = extract_generic_directory(item_path, rel_item_path, detection)
        mode = "generic_dir"
    else:
        extraction = extract_generic_file(item_path, rel_item_path, detection)
        mode = "file"

    G = build_from_json(extraction)
    communities = cluster(G)
    cohesion = score_all(G, communities)
    labels = auto_label_communities(G, communities)
    surprises = surprising_connections(G, communities)
    questions = suggest_questions(G, communities, labels)
    report = generate(
        G,
        communities,
        cohesion,
        labels,
        god_nodes(G),
        surprises,
        detection,
        {"input": extraction.get("input_tokens", 0), "output": extraction.get("output_tokens", 0)},
        rel_item_path,
        suggested_questions=questions,
    )

    item_out = out_root / "items" / item_path.name
    graphify_out = item_out / "graphify-out"
    ensure_dir(graphify_out)

    (item_out / "extraction.json").write_text(json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8")
    (item_out / "analysis.json").write_text(
        json.dumps(
            {
                "mode": mode,
                "communities": {str(cid): members for cid, members in communities.items()},
                "cohesion": {str(cid): score for cid, score in cohesion.items()},
                "labels": {str(cid): label for cid, label in labels.items()},
                "questions": questions,
                "surprises": surprises,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (graphify_out / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    to_json(G, communities, str(graphify_out / "graph.json"))

    html_generated = False
    if G.number_of_nodes() <= 5000:
        to_html(G, communities, str(graphify_out / "graph.html"), community_labels=labels)
        html_generated = True

    return {
        "item": rel_item_path,
        "name": item_path.name,
        "kind": "dir" if item_path.is_dir() else "file",
        "mode": mode,
        "output_dir": rel_to_repo(item_out),
        "graphify_out": rel_to_repo(graphify_out),
        "total_files": detection.get("total_files", 0),
        "total_words": detection.get("total_words", 0),
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "communities": len(communities),
        "html_generated": html_generated,
    }


def write_batch_summary(out_root: Path, results: list[dict[str, Any]], failures: list[dict[str, str]]) -> None:
    summary = {
        "items": len(results),
        "failures": len(failures),
        "total_nodes": sum(item["nodes"] for item in results),
        "total_edges": sum(item["edges"] for item in results),
        "html_generated": sum(1 for item in results if item["html_generated"]),
        "results": results,
        "failures_detail": failures,
    }
    (out_root / "index.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Raw Batch Graphify",
        "",
        f"- Items processed: {len(results)}",
        f"- Failures: {len(failures)}",
        f"- Total nodes: {summary['total_nodes']}",
        f"- Total edges: {summary['total_edges']}",
        f"- HTML graphs: {summary['html_generated']}",
        "",
        "## Results",
    ]
    for item in results:
        lines.append(
            f"- `{item['item']}` -> `{item['graphify_out']}` "
            f"({item['nodes']} nodes, {item['edges']} edges, {item['communities']} communities)"
        )
    if failures:
        lines.extend(["", "## Failures"])
        for failure in failures:
            lines.append(f"- `{failure['item']}` - {failure['error']}")
    (out_root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run graphify-style graph generation for every top-level item in raw/.")
    parser.add_argument("--raw-dir", default="raw")
    parser.add_argument("--out-dir", default="graphify-batch/raw")
    parser.add_argument("--entry", action="append", default=[], help="Only process matching top-level item name(s).")
    args = parser.parse_args()

    raw_dir = (REPO_ROOT / args.raw_dir).resolve()
    out_root = (REPO_ROOT / args.out_dir).resolve()
    ensure_dir(out_root)
    ensure_dir(out_root / "items")

    wanted = set(args.entry or [])
    items = sorted(path for path in raw_dir.iterdir() if not wanted or path.name in wanted)

    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for item_path in items:
        try:
            result = process_item(item_path, out_root)
            results.append(result)
            print(
                f"[ok] {result['item']} -> {result['nodes']} nodes, "
                f"{result['edges']} edges, {result['communities']} communities",
                flush=True,
            )
        except Exception as exc:
            failures.append({"item": rel_to_repo(item_path), "error": repr(exc)})
            print(f"[fail] {rel_to_repo(item_path)} -> {exc!r}", flush=True)

    write_batch_summary(out_root, results, failures)
    print(
        f"batch complete: {len(results)} success, {len(failures)} failed, "
        f"summary -> {rel_to_repo(out_root / 'index.json')}",
        flush=True,
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
