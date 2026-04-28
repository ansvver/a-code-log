#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import fetch_awesome as core


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_awesome_note(spec: dict[str, Any]) -> str:
    lines = [spec.get("entry_note", "Supplemental resource added manually."), ""]
    for link in spec.get("links", []):
        lines.append(f"- {link['source_column']}: [{link['label']}]({link['url']})")
    lines.append("")
    return "\n".join(lines)


def fetch_entry(spec: dict[str, Any], raw_dir: Path, throttle: float) -> dict[str, Any]:
    slug = spec["slug"]
    entry_dir = raw_dir / slug
    if entry_dir.exists():
        shutil.rmtree(entry_dir)
    entry_dir.mkdir(parents=True, exist_ok=True)

    links = []
    source_columns: dict[str, str] = {}
    for item in spec["links"]:
        link = core.LinkInfo(
            label=item["label"],
            url=item["url"],
            kind=item["kind"],
            source_column=item["source_column"],
        )
        links.append(link)
        source_columns.setdefault(item["source_column"], item["label"])

    metadata = {
        "title": spec["title"],
        "slug": slug,
        "primary_url": spec.get("primary_url"),
        "sections": spec.get("sections", ["Supplemental Resources"]),
        "source_columns": source_columns,
        "links": [link.__dict__ for link in links],
    }
    write_json(entry_dir / "metadata.json", metadata)
    (entry_dir / "awesome_entry.md").write_text(build_awesome_note(spec), encoding="utf-8")

    results = []
    for index, link in enumerate(links, start=1):
        time.sleep(throttle)
        try:
            payload = core.extract_text_content(link.url)
        except Exception as exc:
            payload = {
                "url": link.url,
                "normalized_url": link.url,
                "status": "error",
                "error": repr(exc),
            }
        meta_payload = core.save_link_payload(entry_dir, index, link, payload)
        if "error" in payload:
            meta_payload["fetch"]["error"] = payload["error"]  # type: ignore[index]
        results.append(meta_payload)

    manifest = {
        "title": spec["title"],
        "slug": slug,
        "primary_url": spec.get("primary_url"),
        "sections": spec.get("sections", ["Supplemental Resources"]),
        "link_count": len(results),
        "fetched_count": sum(1 for item in results if item["fetch"]["status"] == "ok"),
        "failed_count": sum(1 for item in results if item["fetch"]["status"] in {"error", "skipped"}),
        "results": results,
    }
    write_json(entry_dir / "manifest.json", manifest)
    return manifest


def rebuild_indexes(raw_dir: Path) -> None:
    manifests = []
    for manifest_path in sorted(raw_dir.glob("*/manifest.json")):
        if manifest_path.parent.name == "_source":
            continue
        manifests.append(read_json(manifest_path))
    write_json(raw_dir / "index.json", manifests)
    summary = {
        "entry_count": len(manifests),
        "fetched_count": sum(int(item["fetched_count"]) for item in manifests),
        "failed_count": sum(int(item["failed_count"]) for item in manifests),
    }
    write_json(raw_dir / "summary.json", summary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Add manually curated supplemental resources into raw output.")
    parser.add_argument("--spec", default=str(SCRIPT_DIR / "manual_resources.json"))
    parser.add_argument("--raw-dir", default="raw")
    parser.add_argument("--throttle", type=float, default=0.1)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    specs = read_json(Path(args.spec).resolve())

    for spec in specs:
        manifest = fetch_entry(spec, raw_dir, args.throttle)
        print(f"{spec['slug']}: fetched={manifest['fetched_count']} failed={manifest['failed_count']}", flush=True)

    rebuild_indexes(raw_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
