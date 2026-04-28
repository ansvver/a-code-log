#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import fetch_awesome as core


SECONDARY_HOSTS = {
    "huggingface.co",
    "www.huggingface.co",
    "modelscope.cn",
    "www.modelscope.cn",
    "xbench.org",
    "www.xbench.org",
}
HREF_RE = re.compile(r"""href=["']([^"']+)["']""", flags=re.IGNORECASE)
SKIP_HOSTS = {
    "img.shields.io",
    "raw.githubusercontent.com",
    "github.com",
    "www.github.com",
}
SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf", ".txt", ".json", ".csv", ".tsv"}


def extract_links(raw_text: str, base_url: str) -> list[tuple[str, str]]:
    links = []
    for label, url in core.extract_markdown_links(raw_text):
        if label.strip().startswith("!"):
            continue
        absolute = urllib.parse.urljoin(base_url, url)
        links.append((label, absolute))
    for match in HREF_RE.findall(raw_text):
        absolute = urllib.parse.urljoin(base_url, match)
        links.append(("", absolute))
    return links


def normalize_secondary_link(label: str, url: str) -> tuple[str, str] | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc in SKIP_HOSTS:
        return None
    if Path(parsed.path).suffix.lower() in SKIP_EXTENSIONS:
        return None
    if parsed.fragment:
        url = urllib.parse.urlunparse(parsed._replace(fragment=""))
        parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in SECONDARY_HOSTS:
        return None
    if "huggingface.co" in parsed.netloc:
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return None
        if parts[0] == "datasets" and len(parts) < 3:
            return None
        if parts[0] == "spaces" and len(parts) < 3:
            return None
        if parts[0] == "collections" and len(parts) < 3:
            return None
        if parts[0] not in {"datasets", "spaces", "collections"} and len(parts) < 2:
            return None
    if "modelscope.cn" in parsed.netloc and "/models/" not in parsed.path:
        return None
    return label or parsed.path.strip("/").split("/")[-1] or parsed.netloc, url


def discover_secondary_candidates(manifest: dict[str, object], entry_dir: Path) -> list[tuple[str, str, str]]:
    existing_urls = {item["source_url"] for item in manifest["results"]}  # type: ignore[index]
    candidates: list[tuple[str, str, str]] = []
    seen = set(existing_urls)
    for item in manifest["results"]:  # type: ignore[index]
        if item["kind"] != "code":
            continue
        files = item.get("files", {})
        raw_name = files.get("raw")
        if not raw_name:
            continue
        raw_path = entry_dir / raw_name
        if not raw_path.exists():
            continue
        raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
        base_url = item["fetch"].get("final_url") or item["source_url"]  # type: ignore[index]
        if not base_url:
            continue
        for label, url in extract_links(raw_text, str(base_url)):
            normalized = normalize_secondary_link(label, url)
            if not normalized:
                continue
            norm_label, norm_url = normalized
            if norm_url in seen:
                continue
            kind = core.guess_link_kind(norm_label, norm_url)
            if kind not in {"model", "dataset"}:
                if urllib.parse.urlparse(norm_url).netloc in {"huggingface.co", "www.huggingface.co"}:
                    kind = "model"
                elif urllib.parse.urlparse(norm_url).netloc in {"xbench.org", "www.xbench.org"}:
                    kind = "dataset"
                else:
                    continue
            seen.add(norm_url)
            candidates.append((norm_label, norm_url, kind))
    candidates.sort(key=lambda item: (item[2], item[1]))
    return candidates[:12]


def enrich_entry(entry_dir: Path, throttle: float) -> tuple[str, int]:
    manifest_path = entry_dir / "manifest.json"
    if not manifest_path.exists():
        return entry_dir.name, 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = discover_secondary_candidates(manifest, entry_dir)
    if not candidates:
        return entry_dir.name, 0

    added = 0
    next_index = len(manifest["results"]) + 1
    secondary_links = []
    for label, url, kind in candidates:
        time.sleep(throttle)
        try:
            payload = core.extract_text_content(url)
        except Exception as exc:
            payload = {
                "url": url,
                "normalized_url": url,
                "status": "error",
                "error": repr(exc),
            }
        link = core.LinkInfo(
            label=label,
            url=url,
            kind=kind,
            source_column="secondary:code_readme",
        )
        meta_payload = core.save_link_payload(entry_dir, next_index, link, payload)
        if "error" in payload:
            meta_payload["fetch"]["error"] = payload["error"]  # type: ignore[index]
        manifest["results"].append(meta_payload)
        secondary_links.append(
            {
                "label": label,
                "url": url,
                "kind": kind,
                "status": meta_payload["fetch"]["status"],
                "raw_file": meta_payload["files"].get("raw"),
                "text_file": meta_payload["files"].get("text"),
            }
        )
        next_index += 1
        added += 1

    manifest["link_count"] = len(manifest["results"])
    manifest["fetched_count"] = sum(1 for item in manifest["results"] if item["fetch"]["status"] == "ok")
    manifest["failed_count"] = sum(
        1 for item in manifest["results"] if item["fetch"]["status"] in {"error", "skipped"}
    )
    core.write_json(manifest_path, manifest)
    core.write_json(entry_dir / "secondary_links.json", secondary_links)
    return entry_dir.name, added


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
    parser = argparse.ArgumentParser(description="Enrich raw entries with secondary model/dataset links from code READMEs.")
    parser.add_argument("--raw-dir", default="raw")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--throttle", type=float, default=0.1)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    entry_dirs = [p for p in raw_dir.iterdir() if p.is_dir() and p.name != "_source"]

    total_added = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(enrich_entry, entry_dir, args.throttle) for entry_dir in entry_dirs]
        for future in as_completed(futures):
            slug, added = future.result()
            total_added += added
            if added:
                print(f"{slug}: +{added}", flush=True)

    rebuild_indexes(raw_dir)
    print(f"secondary links added: {total_added}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
