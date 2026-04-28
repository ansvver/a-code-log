#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import fetch_awesome as core


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text_if_exists(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def first_non_empty(items: list[str]) -> str:
    for item in items:
        if item:
            return item
    return ""


def build_resource_record(entry_dir: Path, entry_meta: dict[str, Any], item: dict[str, Any], index: int) -> dict[str, Any]:
    files = item.get("files", {})
    text_rel = files.get("text")
    raw_rel = files.get("raw")
    text_path = entry_dir / text_rel if text_rel else None
    raw_path = entry_dir / raw_rel if raw_rel else None
    fulltext = read_text_if_exists(text_path)

    fetch = item.get("fetch", {})
    source_column = item.get("source_column", "")
    source_type = "secondary" if str(source_column).startswith("secondary:") else "primary"
    final_url = fetch.get("final_url") or item.get("source_url")
    citation = {
        "label": item.get("label"),
        "kind": item.get("kind"),
        "source_type": source_type,
        "source_column": source_column,
        "source_url": item.get("source_url"),
        "final_url": final_url,
        "status": fetch.get("status"),
        "text_kind": fetch.get("text_kind"),
    }

    return {
        "record_type": "resource",
        "resource_id": f"{entry_meta['slug']}::res::{index:03d}",
        "research_slug": entry_meta["slug"],
        "research_title": entry_meta["title"],
        "research_primary_url": entry_meta.get("primary_url"),
        "research_sections": entry_meta.get("sections", []),
        "label": item.get("label"),
        "kind": item.get("kind"),
        "source_type": source_type,
        "source_column": source_column,
        "source_url": item.get("source_url"),
        "normalized_url": fetch.get("normalized_url"),
        "final_url": final_url,
        "status": fetch.get("status"),
        "content_type": fetch.get("content_type"),
        "text_kind": fetch.get("text_kind"),
        "raw_path": str(raw_path.relative_to(entry_dir.parent.parent)) if raw_path else None,
        "text_path": str(text_path.relative_to(entry_dir.parent.parent)) if text_path else None,
        "citation": citation,
        "fulltext": fulltext,
        "fulltext_length": len(fulltext),
    }


def pick_primary_resource(resources: list[dict[str, Any]], primary_url: str | None) -> dict[str, Any] | None:
    if primary_url:
        for resource in resources:
            if resource["source_url"] == primary_url or resource["final_url"] == primary_url:
                return resource
    for kind in ("paper", "code", "model", "dataset"):
        for resource in resources:
            if resource["kind"] == kind and resource["source_type"] == "primary":
                return resource
    return resources[0] if resources else None


def build_merged_fulltext(resources: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for resource in resources:
        text = resource["fulltext"].strip()
        if not text:
            continue
        header = (
            f"[{resource['kind']} | {resource['source_type']} | "
            f"{resource['label']} | {resource['final_url'] or resource['source_url']}]"
        )
        chunks.append(header)
        chunks.append(text)
    return "\n\n".join(chunks)


def compact_resource_for_citation(resource: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_id": resource["resource_id"],
        "label": resource["label"],
        "kind": resource["kind"],
        "source_type": resource["source_type"],
        "source_column": resource["source_column"],
        "source_url": resource["source_url"],
        "final_url": resource["final_url"],
        "text_kind": resource["text_kind"],
        "fulltext_length": resource["fulltext_length"],
        "text_path": resource["text_path"],
    }


def build_research_record(
    raw_dir: Path,
    entry_dir: Path,
    entry_meta: dict[str, Any],
    manifest: dict[str, Any],
    resources: list[dict[str, Any]],
) -> dict[str, Any]:
    awesome_entry = read_text_if_exists(entry_dir / "awesome_entry.md")
    primary_resource = pick_primary_resource(resources, entry_meta.get("primary_url"))
    primary_fulltext = primary_resource["fulltext"] if primary_resource else ""
    primary_resource_id = primary_resource["resource_id"] if primary_resource else None
    merged_fulltext = build_merged_fulltext(resources)

    primary_count = sum(1 for resource in resources if resource["source_type"] == "primary")
    secondary_count = sum(1 for resource in resources if resource["source_type"] == "secondary")

    return {
        "record_type": "research",
        "research_id": entry_meta["slug"],
        "title": entry_meta["title"],
        "slug": entry_meta["slug"],
        "primary_url": entry_meta.get("primary_url"),
        "sections": entry_meta.get("sections", []),
        "source_columns": entry_meta.get("source_columns", {}),
        "awesome_entry_markdown": awesome_entry,
        "metadata": {
            "link_count": manifest.get("link_count"),
            "fetched_count": manifest.get("fetched_count"),
            "failed_count": manifest.get("failed_count"),
            "resource_count": len(resources),
            "primary_resource_count": primary_count,
            "secondary_resource_count": secondary_count,
        },
        "fulltext": {
            "primary_resource_id": primary_resource_id,
            "primary_fulltext": primary_fulltext,
            "merged_fulltext": merged_fulltext,
            "merged_fulltext_length": len(merged_fulltext),
        },
        "citations": [compact_resource_for_citation(resource) for resource in resources],
        "resource_ids": [resource["resource_id"] for resource in resources],
        "direct_links": entry_meta.get("links", []),
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structured JSONL artifacts from raw research pages.")
    parser.add_argument("--raw-dir", default="raw")
    parser.add_argument("--out-dir", default="structured")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    research_records: list[dict[str, Any]] = []
    resource_records: list[dict[str, Any]] = []

    entry_dirs = sorted([p for p in raw_dir.iterdir() if p.is_dir() and p.name != "_source"])
    for entry_dir in entry_dirs:
        metadata_path = entry_dir / "metadata.json"
        manifest_path = entry_dir / "manifest.json"
        if not metadata_path.exists() or not manifest_path.exists():
            continue
        entry_meta = read_json(metadata_path)
        manifest = read_json(manifest_path)

        resources = []
        for index, item in enumerate(manifest.get("results", []), start=1):
            resource = build_resource_record(entry_dir, entry_meta, item, index)
            resources.append(resource)
        resource_records.extend(resources)
        research_records.append(build_research_record(raw_dir, entry_dir, entry_meta, manifest, resources))

    write_jsonl(out_dir / "resources.jsonl", resource_records)
    write_jsonl(out_dir / "research_entries.jsonl", research_records)

    summary = {
        "research_count": len(research_records),
        "resource_count": len(resource_records),
        "primary_resource_count": sum(1 for record in resource_records if record["source_type"] == "primary"),
        "secondary_resource_count": sum(1 for record in resource_records if record["source_type"] == "secondary"),
        "paper_count": sum(1 for record in resource_records if record["kind"] == "paper"),
        "code_count": sum(1 for record in resource_records if record["kind"] == "code"),
        "model_count": sum(1 for record in resource_records if record["kind"] == "model"),
        "dataset_count": sum(1 for record in resource_records if record["kind"] == "dataset"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
