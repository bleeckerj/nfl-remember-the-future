"""
Utility: suggest report_refs for each article based on chunk labels and anchors, and optionally
materialize an updated issue JSON plus a draft report_context.md excerpt.

Usage:
  python -m tools.auto_ground \
    --issue intelligence_transition_full_issue.json \
    --chunks report_chunk_labels.json \
    --out-issue intelligence_transition_full_issue.grounded.json \
    --report-context-out prompts/report_context.md \
    --refs-per-article 2 \
    --context-chunks 2

Heuristic scoring: overlaps between article signals (title, lede, anchors) and chunk summaries/keywords/text.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[A-Za-z]{4,}", text.lower())]


def score_chunk(signals: List[str], chunk: Dict) -> int:
    haystacks = [
        chunk.get("summary", ""),
        " ".join(chunk.get("keywords", [])),
        chunk.get("text", ""),
    ]
    hay_tokens = set(tokenize(" ".join(haystacks)))
    score = 0
    for token in signals:
        if token in hay_tokens:
            score += 3  # keyword hit
    return score


def suggest_refs(issue: Dict, chunks: List[Dict], refs_per_article: int, include_details: bool, verbose: bool) -> Tuple[Dict, List[str]]:
    updated = json.loads(json.dumps(issue))
    for article in updated.get("articles", []):
        signals = tokenize(" ".join([
            str(article.get("title", "")),
            str(article.get("lede", "")),
            " ".join(article.get("ai2027_anchor", []) or []),
        ]))
        scored = []
        for ch in chunks:
            scored.append((score_chunk(signals, ch), ch["id"]))
        scored.sort(reverse=True, key=lambda x: x[0])
        top = [cid for s, cid in scored if s > 0][:refs_per_article]
        article["report_refs"] = top
        if verbose:
            print(f"Article {article.get('id')}: {article.get('title')} → refs={top or 'none'}")
        if include_details and top:
            details = []
            for cid in top:
                match = next((c for c in chunks if c["id"] == cid), None)
                if match:
                    details.append({
                        "id": cid,
                        "summary": match.get("summary", ""),
                        "keywords": match.get("keywords", []),
                    })
            article["report_ref_details"] = details
    return updated, []


def build_context(chunks: List[Dict], count: int) -> str:
    top = chunks[:count]
    parts = []
    for ch in top:
        parts.append(f"[{ch['id']}]")
        parts.append(ch["text"].strip())
        parts.append("")
    return "\n".join(parts).strip()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Auto-suggest report_refs and context excerpt.")
    p.add_argument("--issue", type=Path, required=True, help="Input issue JSON")
    p.add_argument("--chunks", type=Path, required=True, help="Chunk labels JSON from tools.label_chunks")
    p.add_argument("--out-issue", type=Path, help="Where to write updated issue JSON with report_refs")
    p.add_argument("--report-context-out", type=Path, help="Where to write a concatenated context excerpt")
    p.add_argument("--refs-per-article", type=int, default=2, help="How many chunk ids to attach per article")
    p.add_argument("--context-chunks", type=int, default=2, help="How many top chunks to concatenate for context")
    p.add_argument("--include-ref-details", action="store_true", help="Include summaries/keywords for refs in output issue JSON")
    p.add_argument("--verbose", action="store_true", help="Verbose logging")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    issue = load_json(args.issue)
    chunks = load_json(args.chunks)

    updated_issue, _ = suggest_refs(issue, chunks, args.refs_per_article, args.include_ref_details, args.verbose)

    if args.out_issue:
        write_json(args.out_issue, updated_issue)
        print(f"Wrote updated issue with report_refs to {args.out_issue}")
    else:
        print(json.dumps(updated_issue, indent=2, ensure_ascii=False))

    if args.report_context_out:
        ctx = build_context(chunks, args.context_chunks)
        args.report_context_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_context_out.write_text(ctx + "\n", encoding="utf-8")
        print(f"Wrote report context excerpt to {args.report_context_out}")
    if args.verbose:
        print("Completed auto_ground run.")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
