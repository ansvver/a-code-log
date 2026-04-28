#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import fetch_awesome as core


def reset_entry(entry_dir: Path) -> int:
    manifest_path = entry_dir / "manifest.json"
    if not manifest_path.exists():
        return 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    kept = []
    removed = 0
    for item in manifest["results"]:
        if item.get("source_column") == "secondary:code_readme":
            removed += 1
            file_values = list(item.get("files", {}).values())
            for filename in file_values:
                file_path = entry_dir / filename
                if file_path.exists():
                    file_path.unlink()
            if file_values:
                prefix = file_values[0].split(".meta.", 1)[0]
                for candidate in entry_dir.glob(f"{prefix}.meta.*"):
                    if candidate.exists():
                        candidate.unlink()
            continue
        kept.append(item)

    manifest["results"] = kept
    manifest["link_count"] = len(kept)
    manifest["fetched_count"] = sum(1 for item in kept if item["fetch"]["status"] == "ok")
    manifest["failed_count"] = sum(1 for item in kept if item["fetch"]["status"] in {"error", "skipped"})
    core.write_json(manifest_path, manifest)

    secondary_path = entry_dir / "secondary_links.json"
    if secondary_path.exists():
        secondary_path.unlink()
    return removed


def rebuild_indexes(raw_dir: Path) -> None:
    manifests = []
    for manifest_path in sorted(raw_dir.glob("*/manifest.json")):
        if manifest_path.parent.name == "_source":
            continue
        manifests.append(json.loads(manifest_path.read_text(encoding="utf-8")))
    core.write_json(raw_dir / "index.json", manifests)
    summary = {
        "entry_count": len(manifests),
        "fetched_count": sum(int(item["fetched_count"]) for item in manifests),
        "failed_count": sum(int(item["failed_count"]) for item in manifests),
    }
    core.write_json(raw_dir / "summary.json", summary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove secondary model/dataset enrichments from raw output.")
    parser.add_argument("--raw-dir", default="raw")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    removed = 0
    for entry_dir in raw_dir.iterdir():
        if entry_dir.is_dir() and entry_dir.name != "_source":
            removed += reset_entry(entry_dir)
    rebuild_indexes(raw_dir)
    print(f"secondary links removed: {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
