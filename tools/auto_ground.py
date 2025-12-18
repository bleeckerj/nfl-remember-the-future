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
from typing import Dict, List, Optional, Tuple

from tools.project_paths import normalize_project_root


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[A-Za-z]{4,}", text.lower())]


def resolve_path(path: Optional[Path], project_root: Optional[Path]) -> Optional[Path]:
    if path is None:
        return None
    normalized_root = normalize_project_root(project_root)
    if normalized_root and not path.is_absolute():
        return normalized_root / path
    return path


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
            " ".join(article.get("report_anchor", []) or article.get("ai2027_anchor", []) or []),
        ]))
        scored = []
        for ch in chunks:
            scored.append((score_chunk(signals, ch), ch["id"]))
        scored.sort(reverse=True, key=lambda x: x[0])
        top = [cid for s, cid in scored if s > 0][:refs_per_article]
        article["report_refs"] = top
        if verbose:
            print(
                f"[auto_ground] article={article.get('id')} "
                f"title={article.get('title')} refs={top or 'none'}"
            )
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
    p.add_argument("--project-root", type=Path, help="Project workspace root for inputs/outputs")
    p.add_argument("--issue", type=Path, required=True, help="Input issue JSON")
    p.add_argument("--chunks", type=Path, required=True, help="Chunk labels JSON from tools.label_chunks")
    p.add_argument("--out-issue", type=Path, help="Where to write updated issue JSON with report_refs")
    p.add_argument("--report-context-out", type=Path, help="Where to write a concatenated context excerpt")
    p.add_argument("--refs-per-article", type=int, default=2, help="How many chunk ids to attach per article")
    p.add_argument("--context-chunks", type=int, default=2, help="How many top chunks to concatenate for context")
    p.add_argument("--include-ref-details", action="store_true", help="Include summaries/keywords for refs in output issue JSON")
    p.add_argument("--verbose", action="store_true", help="Extra verbose logging")
    p.add_argument("--quiet", action="store_true", help="Minimal logging")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    issue_path = resolve_path(args.issue, args.project_root)
    chunks_path = resolve_path(args.chunks, args.project_root)
    out_issue_path = resolve_path(args.out_issue, args.project_root)
    report_context_out_path = resolve_path(args.report_context_out, args.project_root)

    issue = load_json(issue_path)
    chunks = load_json(chunks_path)

    updated_issue, _ = suggest_refs(
        issue,
        chunks,
        args.refs_per_article,
        args.include_ref_details,
        verbose=not args.quiet,
    )
    total_articles = len(updated_issue.get("articles", []))
    with_refs = len([a for a in updated_issue.get("articles", []) if a.get("report_refs")])
    if not args.quiet:
        print(
            f"[auto_ground] articles={total_articles} "
            f"refs_attached={with_refs} refs_per_article={args.refs_per_article} "
            f"include_details={args.include_ref_details}"
        )

    if out_issue_path:
        write_json(out_issue_path, updated_issue)
        if not args.quiet:
            print(f"[auto_ground] wrote_issue={out_issue_path}")
    else:
        print(json.dumps(updated_issue, indent=2, ensure_ascii=False))

    if report_context_out_path:
        ctx = build_context(chunks, args.context_chunks)
        report_context_out_path.parent.mkdir(parents=True, exist_ok=True)
        report_context_out_path.write_text(ctx + "\n", encoding="utf-8")
        if not args.quiet:
            print(f"[auto_ground] wrote_context={report_context_out_path} chunks={args.context_chunks}")
    if args.verbose and not args.quiet:
        print("[auto_ground] completed")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
