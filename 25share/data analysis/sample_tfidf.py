#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import os
import random
from datetime import datetime
from typing import Dict, Iterable, List, Sequence, Tuple


def jieba_tokenize(text: str) -> List[str]:
    import re

    import jieba

    text = (text or "").strip()
    if not text:
        return []
    text = re.sub(r"\s+", " ", text)
    tokens = [t.strip() for t in jieba.lcut(text, cut_all=False)]
    return [t for t in tokens if t and not t.isspace()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从TSV中抽样(upvotes阈值)并基于jieba训练TF-IDF。"
    )
    parser.add_argument("--input", default="zhihu_26k.tsv", help="输入TSV路径")
    parser.add_argument("--delimiter", default="\t", help="输入分隔符(默认TSV)")
    parser.add_argument("--upvotes-col", default="upvotes", help="点赞字段名")
    parser.add_argument("--min-upvotes", type=float, default=200.0, help="点赞阈值(>)")
    parser.add_argument(
        "--text-cols",
        default="RESPONSE",
        help="用于建模的文本字段，逗号分隔(默认仅RESPONSE)",
    )
    parser.add_argument("--sample-size", type=int, default=1000, help="抽样条数")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument(
        "--max-features", type=int, default=50000, help="TF-IDF最大词表大小"
    )
    parser.add_argument(
        "--min-df",
        type=int,
        default=2,
        help="词项最小文档频次(>=)，可抑制极低频噪声",
    )
    parser.add_argument(
        "--topk", type=int, default=50, help="导出TopK关键词(按平均TF-IDF)"
    )
    parser.add_argument("--outdir", default="outputs", help="输出目录")
    return parser.parse_args()


def iter_rows(path: str, delimiter: str) -> Tuple[Sequence[str], Iterable[Dict[str, str]]]:
    f = open(path, "r", encoding="utf-8")
    reader = csv.DictReader(f, delimiter=delimiter)
    if reader.fieldnames is None:
        raise ValueError("未检测到表头(fieldnames)")

    def gen():
        try:
            for row in reader:
                yield row
        finally:
            f.close()

    return reader.fieldnames, gen()


def safe_float(value: str) -> float:
    try:
        return float(value)
    except Exception:
        return float("nan")


def reservoir_sample(
    rows: Iterable[Dict[str, str]],
    *,
    sample_size: int,
    rng: random.Random,
) -> List[Dict[str, str]]:
    sample: List[Dict[str, str]] = []
    seen = 0
    for row in rows:
        seen += 1
        if len(sample) < sample_size:
            sample.append(row)
            continue
        j = rng.randrange(seen)
        if j < sample_size:
            sample[j] = row
    return sample


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_tsv(path: str, fieldnames: Sequence[str], rows: Sequence[Dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def build_corpus(rows: Sequence[Dict[str, str]], text_cols: Sequence[str]) -> List[str]:
    corpus: List[str] = []
    for row in rows:
        parts = [(row.get(c) or "").strip() for c in text_cols]
        corpus.append("\n".join([p for p in parts if p]))
    return corpus


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)

    fieldnames, rows_iter = iter_rows(args.input, args.delimiter)
    if args.upvotes_col not in fieldnames:
        raise ValueError(f"缺少点赞字段: {args.upvotes_col}，当前字段: {list(fieldnames)}")

    text_cols = [c.strip() for c in args.text_cols.split(",") if c.strip()]
    missing_text_cols = [c for c in text_cols if c not in fieldnames]
    if missing_text_cols:
        raise ValueError(f"缺少文本字段: {missing_text_cols}，当前字段: {list(fieldnames)}")

    def eligible():
        for row in rows_iter:
            up = safe_float(row.get(args.upvotes_col, ""))
            if up == up and up > args.min_upvotes:  # NaN自反性为False
                yield row

    sampled = reservoir_sample(
        eligible(),
        sample_size=args.sample_size,
        rng=rng,
    )
    if not sampled:
        raise ValueError(f"未找到满足 upvotes>{args.min_upvotes} 的记录")

    ensure_dir(args.outdir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sample_path = os.path.join(args.outdir, f"sample_upvotes_gt_{int(args.min_upvotes)}_{len(sampled)}_{stamp}.tsv")
    write_tsv(sample_path, fieldnames, sampled)

    corpus = build_corpus(sampled, text_cols)

    import jieba  # noqa: F401
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import Pipeline
    from joblib import dump

    vectorizer = TfidfVectorizer(
        tokenizer=jieba_tokenize,
        token_pattern=None,
        max_features=args.max_features,
        min_df=args.min_df,
        lowercase=False,
        norm="l2",
    )

    pipe = Pipeline([("tfidf", vectorizer)])
    X = pipe.fit_transform(corpus)

    model_path = os.path.join(args.outdir, f"tfidf_model_{len(sampled)}_{stamp}.joblib")
    dump(
        {
            "pipeline": pipe,
            "meta": {
                "input": args.input,
                "min_upvotes": args.min_upvotes,
                "sample_size": args.sample_size,
                "actual_sampled": len(sampled),
                "text_cols": text_cols,
                "seed": args.seed,
                "shape": [int(X.shape[0]), int(X.shape[1])],
            },
        },
        model_path,
    )

    feature_names = vectorizer.get_feature_names_out()
    mean_tfidf = X.mean(axis=0).A1
    topk = min(args.topk, len(feature_names))
    top_idx = mean_tfidf.argsort()[::-1][:topk]

    top_path = os.path.join(args.outdir, f"tfidf_top_{topk}_{stamp}.tsv")
    with open(top_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["term", "mean_tfidf"])
        for i in top_idx:
            w.writerow([feature_names[i], f"{mean_tfidf[i]:.8f}"])

    print("OK")
    print("sample:", sample_path)
    print("model :", model_path)
    print("top   :", top_path)
    print("shape :", X.shape)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
