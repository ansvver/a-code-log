#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from graphify.analyze import god_nodes, suggest_questions, surprising_connections
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.export import to_html, to_json
from graphify.report import generate

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from batch_graphify_raw import auto_label_communities, clean_text, slugify  # noqa: E402


REPO_ROOT = SCRIPT_DIR.parent

GENERIC_LABELS = {
    "awesome rl-based agentic search papers",
    "recent evaluation / benchmarking papers (deep research / agentic search)",
    "linked papers",
    "code artifacts",
    "datasets",
    "models",
    "dataset",
    "code",
    "paper title",
    "venue",
    "time",
    "method",
    "role",
    "format",
    "focus",
    "retrieval control",
    "query optimization",
    "evaluation",
    "what rl is for: functional roles in agentic search",
    "how rl is used: optimization strategies",
    "where rl is applied: optimization scopes",
    "cold start?",
    "training env.",
    "rl func. role",
    "rl alg.",
    "reward type",
    "reward func.",
    "opt. scope",
    "r–s inter.",
    "representative survey",
}

CONCEPT_COUNT_MIN = 2
CONCEPT_COUNT_MAX = 64
ITEM_EDGE_MIN_SHARED = 2
ITEM_EDGE_TOP_K = 6
ITEM_NODE_FILE_TYPE = "document"
CONCEPT_NODE_FILE_TYPE = "document"


def rel_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except Exception:
        return str(path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_label(label: str) -> str:
    text = clean_text(label)
    text = text.replace("‑", "-").replace("–", "-").replace("—", "-")
    text = re.sub(r"^\[+", "", text)
    text = re.sub(r"\]+(?:\(\))?$", "", text)
    text = text.strip("[]() ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def canonical_key(label: str) -> str:
    return slugify(normalize_label(label))


def is_date_like(label: str) -> bool:
    return bool(re.fullmatch(r"[12][0-9]{3}(?:[./-][0-9]{1,2}){0,2}", label))


def is_noise_label(label: str) -> bool:
    if not label:
        return True
    lower = label.lower()
    if lower in GENERIC_LABELS:
        return True
    if is_date_like(label):
        return True
    if lower in {"✓", "✗", "-", "n/a"}:
        return True
    if label.startswith("http://") or label.startswith("https://"):
        return True
    if len(label) > 120:
        return True
    if re.fullmatch(r"[\W_]+", label):
        return True
    return False


def pick_item_label(item_result: dict[str, Any], extraction: dict[str, Any]) -> str:
    paper_nodes = [n for n in extraction.get("nodes", []) if n.get("file_type") == "paper"]
    if paper_nodes:
        longest = max(paper_nodes, key=lambda n: len(clean_text(n.get("label"))))
        return clean_text(longest.get("label")) or item_result["name"]
    nodes = extraction.get("nodes", [])
    if nodes:
        return clean_text(nodes[0].get("label")) or item_result["name"]
    return item_result["name"]


def concept_candidates(extraction: dict[str, Any], item_label: str) -> list[str]:
    labels: set[str] = set()
    item_key = canonical_key(item_label)
    for node in extraction.get("nodes", []):
        label = normalize_label(node.get("label", ""))
        if not label or is_noise_label(label):
            continue
        if canonical_key(label) == item_key:
            continue
        if len(label.split()) > 10:
            continue
        labels.add(label)
    return sorted(labels)


def concept_label_score(label: str, count: int) -> tuple[int, int, int]:
    token_count = len(label.split())
    length = len(label)
    return (count, -token_count, -length)


def build_navigation_extraction(batch_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    index = load_json(batch_dir / "index.json")
    results = index["results"]
    items_dir = batch_dir / "items"

    item_records: list[dict[str, Any]] = []
    concept_to_items: dict[str, set[str]] = defaultdict(set)
    concept_display: dict[str, str] = {}
    concept_sources: dict[str, set[str]] = defaultdict(set)

    for item in results:
        item_dir = items_dir / item["name"]
        extraction = load_json(item_dir / "extraction.json")
        item_label = pick_item_label(item, extraction)
        item_id = f"item__{slugify(item['name'])}"
        source_path = item["item"]
        concepts = concept_candidates(extraction, item_label)
        item_records.append(
            {
                "id": item_id,
                "name": item["name"],
                "label": item_label,
                "source_file": source_path,
                "item_result": item,
                "concepts": concepts,
            }
        )
        for concept in concepts:
            key = canonical_key(concept)
            concept_to_items[key].add(item_id)
            concept_display.setdefault(key, concept)
            concept_sources[key].add(source_path)

    selected_concepts: dict[str, dict[str, Any]] = {}
    total_items = len(item_records)
    for key, item_ids in concept_to_items.items():
        count = len(item_ids)
        label = concept_display[key]
        if count < CONCEPT_COUNT_MIN:
            continue
        if count > min(CONCEPT_COUNT_MAX, max(12, int(total_items * 0.38))):
            continue
        if is_noise_label(label):
            continue
        selected_concepts[key] = {
            "label": label,
            "items": sorted(item_ids),
            "count": count,
            "source_file": sorted(concept_sources[key])[0],
        }

    pair_to_concepts: dict[tuple[str, str], list[str]] = defaultdict(list)
    for payload in selected_concepts.values():
        concept_label = payload["label"]
        item_ids = payload["items"]
        if len(item_ids) < 2:
            continue
        for a, b in combinations(sorted(item_ids), 2):
            pair_to_concepts[(a, b)].append(concept_label)

    extraction = {
        "nodes": [],
        "edges": [],
        "hyperedges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }

    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    def add_node(node_id: str, label: str, file_type: str, source_file: str) -> None:
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        extraction["nodes"].append(
            {
                "id": node_id,
                "label": label,
                "file_type": file_type,
                "source_file": source_file,
                "source_location": None,
                "source_url": None,
            }
        )

    def add_edge(
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
        key = (source, target, relation)
        if key in seen_edges:
            return
        seen_edges.add(key)
        extraction["edges"].append(
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

    batch_index_source = rel_to_repo(batch_dir / "index.json")

    for item in item_records:
        add_node(item["id"], item["label"], ITEM_NODE_FILE_TYPE, item["source_file"])

    for concept_key, payload in selected_concepts.items():
        concept_id = f"concept__{concept_key}"
        add_node(concept_id, payload["label"], CONCEPT_NODE_FILE_TYPE, payload["source_file"])
        for item_id in payload["items"]:
            add_edge(item_id, concept_id, "mentions_concept", batch_index_source)
        if len(payload["items"]) >= 3:
            extraction["hyperedges"].append(
                {
                    "id": f"shared_concept__{concept_key}",
                    "label": payload["label"],
                    "nodes": payload["items"],
                    "relation": "participate_in",
                    "confidence": "EXTRACTED",
                    "confidence_score": 1.0,
                    "source_file": batch_index_source,
                }
            )

    pair_scores: dict[str, list[tuple[int, str, list[str]]]] = defaultdict(list)
    for (a, b), concepts in pair_to_concepts.items():
        if len(concepts) < ITEM_EDGE_MIN_SHARED:
            continue
        pair_scores[a].append((len(concepts), b, concepts))
        pair_scores[b].append((len(concepts), a, concepts))

    emitted_pairs: set[tuple[str, str]] = set()
    for item_id, neighbors in pair_scores.items():
        neighbors.sort(key=lambda row: (-row[0], row[1]))
        for shared_count, other_id, concepts in neighbors[:ITEM_EDGE_TOP_K]:
            pair = tuple(sorted((item_id, other_id)))
            if pair in emitted_pairs:
                continue
            emitted_pairs.add(pair)
            source_location = ", ".join(concepts[:5])
            confidence_score = min(0.95, 0.55 + min(shared_count, 8) * 0.05)
            add_edge(
                pair[0],
                pair[1],
                "related_via_shared_concepts",
                batch_index_source,
                confidence="INFERRED",
                confidence_score=confidence_score,
                source_location=source_location,
                weight=float(shared_count),
            )

    meta = {
        "index": index,
        "selected_concepts": selected_concepts,
        "item_records": item_records,
        "pair_to_concepts": {f"{a}::{b}": concepts for (a, b), concepts in pair_to_concepts.items()},
    }
    return extraction, meta


def write_navigation_summary(out_dir: Path, G: Any, concepts: dict[str, Any], item_records: list[dict[str, Any]]) -> None:
    concept_items = sorted(
        (
            {
                "label": payload["label"],
                "count": payload["count"],
                "items": payload["items"][:12],
            }
            for payload in concepts.values()
        ),
        key=lambda row: concept_label_score(row["label"], row["count"]),
        reverse=True,
    )
    summary = {
        "item_count": len(item_records),
        "concept_count": len(concepts),
        "graph_nodes": G.number_of_nodes(),
        "graph_edges": G.number_of_edges(),
        "top_concepts": concept_items[:50],
    }
    (out_dir / "navigation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a total cross-item navigation graph from graphify batch outputs.")
    parser.add_argument("--batch-dir", default="graphify-batch/raw")
    parser.add_argument("--out-dir", default="graphify-batch/raw/global-navigation")
    args = parser.parse_args()

    batch_dir = (REPO_ROOT / args.batch_dir).resolve()
    out_dir = (REPO_ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    extraction, meta = build_navigation_extraction(batch_dir)
    G = build_from_json(extraction)
    communities = cluster(G)
    cohesion = score_all(G, communities)
    labels = auto_label_communities(G, communities)
    surprises = surprising_connections(G, communities)
    questions = suggest_questions(G, communities, labels)

    total_words = sum(item["item_result"].get("total_words", 0) for item in meta["item_records"])
    detection = {
        "total_files": len(meta["item_records"]),
        "total_words": total_words,
        "warning": None,
        "files": {"document": [item["source_file"] for item in meta["item_records"]]},
    }
    report = generate(
        G,
        communities,
        cohesion,
        labels,
        god_nodes(G),
        surprises,
        detection,
        {"input": 0, "output": 0},
        "raw (global navigation)",
        suggested_questions=questions,
    )

    graphify_out = out_dir / "graphify-out"
    graphify_out.mkdir(parents=True, exist_ok=True)

    (out_dir / "navigation_extraction.json").write_text(json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "navigation_meta.json").write_text(
        json.dumps(
            {
                "concepts": meta["selected_concepts"],
                "items": [
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "label": item["label"],
                        "source_file": item["source_file"],
                        "concepts": item["concepts"],
                    }
                    for item in meta["item_records"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (graphify_out / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    to_json(G, communities, str(graphify_out / "graph.json"))
    to_html(G, communities, str(graphify_out / "graph.html"), community_labels=labels)
    write_navigation_summary(out_dir, G, meta["selected_concepts"], meta["item_records"])

    print(
        f"global navigation graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, "
        f"{len(meta['item_records'])} items, {len(meta['selected_concepts'])} shared concepts",
        flush=True,
    )
    print(f"output -> {rel_to_repo(graphify_out)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
