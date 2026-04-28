from __future__ import annotations

import csv
import html
import json
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

import requests

ROOT = Path(__file__).resolve().parent
README_URL = "https://raw.githubusercontent.com/ventr1c/Awesome-RL-based-Agentic-Search-Papers/main/README.md"
SNAPSHOT_DATE = "2026-04-14"

KEY_RELEVANCE_RULES = [
    ("enterprise-local", [r"domain", r"medical", r"knowledge graph", r"structured", r"retriever", r"retrieval", r"tool", r"entity", r"memory", r"citation", r"faithful", r"boundary", r"abstain", r"offline", r"simulation"]),
    ("efficiency", [r"efficient", r"efficiency", r"cost", r"latency", r"parallel", r"token-efficient", r"search intensity", r"turn", r"count", r"redundancy", r"summary", r"memory"]),
    ("tool-routing", [r"tool", r"planner", r"executor", r"orchestration", r"multi-tool"]),
    ("retriever-training", [r"retriever", r"retrieve", r"ranking", r"query refinement", r"query reformulation"]),
    ("reliability", [r"citation", r"faithful", r"boundary", r"i don.t know", r"idk", r"uncertainty", r"evidence"]),
    ("memory", [r"memory", r"summary", r"context", r"long-horizon", r"condens"]),
    ("kg-hybrid", [r"knowledge graph", r"graph", r"hybrid"]),
    ("offline-rl", [r"offline", r"simulation", r"simulated", r"without searching", r"cost-effective"]),
]

FOCUS_PAPERS = {
    "2503.09516",
    "2503.05592",
    "2505.17005",
    "2505.04588",
    "2601.14615",
    "2505.16834",
    "2504.03160",
    "2508.14880",
    "2509.10446",
    "2601.11888",
    "2601.04888",
    "2602.22576",
    "2603.09203",
    "2601.06021",
    "2601.21912",
    "2601.11037",
    "2509.13313",
    "2511.02805",
    "2603.07853",
    "2602.22675",
    "2508.09303",
    "2505.17281",
}

HEADERS = {"User-Agent": "Mozilla/5.0"}


def request_text(session: requests.Session, url: str, timeout: int = 30) -> str:
    resp = session.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def clean_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sentence_highlight(abstract: str, title: str) -> str:
    if not abstract:
        return title
    parts = re.split(r"(?<=[.!?])\s+", abstract)
    chosen = []
    size = 0
    for part in parts:
        if not part:
            continue
        chosen.append(part)
        size += len(part)
        if size >= 180 or len(chosen) >= 2:
            break
    result = " ".join(chosen).strip()
    return result[:220].rstrip()


def extract_repo_key(url: str) -> str | None:
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)", url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    return f"{owner}/{repo.removesuffix('.git')}"


def parse_star_count(repo_html: str) -> int | None:
    patterns = [
        r"([0-9,]+) users starred this repository",
        r"([0-9,]+)\s*stars",
    ]
    for pattern in patterns:
        m = re.search(pattern, repo_html, re.I)
        if m:
            return int(m.group(1).replace(",", ""))
    return None


def extract_readme(session: requests.Session, repo_key: str) -> str:
    owner, repo = repo_key.split("/", 1)
    for branch in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
        resp = session.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            return resp.text
    return ""


def parse_primary_papers(readme_text: str) -> list[dict]:
    papers: OrderedDict[str, dict] = OrderedDict()
    section_stack: list[str] = []
    time_pattern = re.compile(r"^20\d\d\.\d{1,2}$")

    for line in readme_text.splitlines():
        heading = re.match(r"^(#{2,4})\s+(.+?)\s*$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            while len(section_stack) >= level - 1:
                section_stack.pop()
            section_stack.append(title)
            continue

        if not line.startswith("|"):
            continue

        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 2:
            continue

        links = re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", line)
        if not links:
            continue

        title, paper_url = links[0]
        arxiv_match = re.search(r"arxiv\.org/abs/([^?#)]+)", paper_url)
        if not arxiv_match:
            continue

        paper_id = arxiv_match.group(1)
        item = papers.setdefault(
            paper_id,
            {
                "paper_id": paper_id,
                "title": title,
                "paper_url": paper_url,
                "time_column": cols[0],
                "venue_or_role": cols[2] if len(cols) > 2 else "",
                "sections": [],
                "code_urls": [],
            },
        )

        current_time = cols[0]
        if time_pattern.match(current_time) and not time_pattern.match(item["time_column"]):
            item["time_column"] = current_time

        section_path = " > ".join(section_stack)
        if section_path and section_path not in item["sections"]:
            item["sections"].append(section_path)

        for _, url in links[1:]:
            if "github.com/" in url and url not in item["code_urls"]:
                item["code_urls"].append(url)

    return list(papers.values())


def fetch_paper_metadata(session: requests.Session, paper_id: str) -> dict:
    url = f"https://arxiv.org/abs/{paper_id}"
    html_text = request_text(session, url)

    date_match = re.search(r"Submitted\s+on\s+(\d+\s+\w+\s+\d+)", html_text)
    abs_match = re.search(
        r'<blockquote class="abstract mathjax">\s*<span class="descriptor">Abstract:</span>(.*?)</blockquote>',
        html_text,
        re.S,
    )

    abstract = clean_text(abs_match.group(1)) if abs_match else ""
    return {
        "submitted_on": date_match.group(1) if date_match else "",
        "abstract": abstract,
    }


def tag_relevance(text: str) -> list[str]:
    tags = []
    lowered = text.lower()
    for tag, patterns in KEY_RELEVANCE_RULES:
        if any(re.search(pattern, lowered) for pattern in patterns):
            tags.append(tag)
    return tags


def repo_metadata(session: requests.Session, repo_key: str) -> dict:
    html_text = request_text(session, f"https://github.com/{repo_key}")
    stars = parse_star_count(html_text)
    description = ""
    desc_match = re.search(r'<meta name="description" content="([^"]+)"', html_text)
    if desc_match:
        description = html.unescape(desc_match.group(1)).strip()
    readme_text = extract_readme(session, repo_key)
    return {
        "repo": repo_key,
        "repo_url": f"https://github.com/{repo_key}",
        "stars": stars,
        "description": description,
        "readme_excerpt": clean_text(readme_text[:1800]),
    }


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_markdown_table(rows: list[dict]) -> str:
    header = "| Time | Submitted | Title | Highlight | Code | Stars | Tags |\n|---|---|---|---|---|---:|---|\n"
    lines = [header]
    for row in rows:
        code = row["repo_links_md"] if row["repo_links_md"] else "-"
        stars = row["star_snapshot"] if row["star_snapshot"] else "-"
        tags = row["tags"] if row["tags"] else "-"
        lines.append(
            f"| {row['time_column']} | {row['submitted_on']} | [{row['title']}]({row['paper_url']}) | {row['highlight']} | {code} | {stars} | {tags} |"
        )
    return "".join(line + "\n" for line in lines)


def main() -> None:
    session = requests.Session()
    readme_text = request_text(session, README_URL)
    papers = parse_primary_papers(readme_text)

    repo_cache: dict[str, dict] = {}
    enriched = []

    for idx, paper in enumerate(papers, start=1):
        paper_meta = fetch_paper_metadata(session, paper["paper_id"])
        repo_items = []
        for code_url in paper["code_urls"]:
            repo_key = extract_repo_key(code_url)
            if not repo_key:
                continue
            if repo_key not in repo_cache:
                repo_cache[repo_key] = repo_metadata(session, repo_key)
                time.sleep(0.2)
            repo_items.append(repo_cache[repo_key])

        paper_text = " ".join(
            [paper["title"], paper_meta["abstract"], " ".join(paper["sections"]), paper["venue_or_role"]]
        )
        tags = tag_relevance(paper_text)

        main_repo = repo_items[0] if repo_items else None
        enriched.append(
            {
                **paper,
                **paper_meta,
                "highlight": sentence_highlight(paper_meta["abstract"], paper["title"]),
                "tags": tags,
                "focus": paper["paper_id"] in FOCUS_PAPERS,
                "code_repos": repo_items,
                "star_snapshot_date": SNAPSHOT_DATE,
                "star_snapshot": main_repo["stars"] if main_repo else None,
            }
        )
        if idx % 20 == 0:
            print(f"processed {idx}/{len(papers)}")

    write_json(ROOT / "papers_full.json", enriched)
    write_json(ROOT / "repo_cache.json", repo_cache)

    csv_rows = []
    for row in enriched:
        repo_links_md = "; ".join(f"[{repo['repo']}]({repo['repo_url']})" for repo in row["code_repos"])
        csv_rows.append(
            {
                "paper_id": row["paper_id"],
                "time_column": row["time_column"],
                "submitted_on": row["submitted_on"],
                "title": row["title"],
                "paper_url": row["paper_url"],
                "highlight": row["highlight"],
                "tags": ", ".join(row["tags"]),
                "sections": " | ".join(row["sections"]),
                "code_repos": "; ".join(repo["repo"] for repo in row["code_repos"]),
                "star_snapshot": row["star_snapshot"] or "",
                "focus": row["focus"],
            }
        )

    write_csv(
        ROOT / "papers_full.csv",
        csv_rows,
        [
            "paper_id",
            "time_column",
            "submitted_on",
            "title",
            "paper_url",
            "highlight",
            "tags",
            "sections",
            "code_repos",
            "star_snapshot",
            "focus",
        ],
    )

    md_rows = []
    for row in enriched:
        repo_links_md = "; ".join(f"[{repo['repo']}]({repo['repo_url']})" for repo in row["code_repos"])
        md_rows.append(
            {
                "time_column": row["time_column"],
                "submitted_on": row["submitted_on"],
                "title": row["title"],
                "paper_url": row["paper_url"],
                "highlight": row["highlight"].replace("|", "\\|"),
                "repo_links_md": repo_links_md,
                "star_snapshot": row["star_snapshot"],
                "tags": ", ".join(row["tags"]),
            }
        )

    full_md = [
        "# Agentic-Search Paper Ledger\n",
        f"\nSnapshot date: `{SNAPSHOT_DATE}`\n",
        f"\nUnique primary papers parsed from awesome repo: `{len(enriched)}`\n",
        "\nSource: [Awesome-RL-based-Agentic-Search-Papers](https://github.com/ventr1c/Awesome-RL-based-Agentic-Search-Papers)\n\n",
        build_markdown_table(md_rows),
    ]
    (ROOT / "papers_full.md").write_text("".join(full_md), encoding="utf-8")


if __name__ == "__main__":
    main()
