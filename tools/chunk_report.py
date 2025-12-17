"""
Utility: chunk a Markdown version of the AI 2027 report into digestible pieces and emit an index JSON.

Usage:
    python -m tools.chunk_report --md report.md --out report_chunks.json --max-chars 1200 --overlap 200

The output is a JSON array with chunk ids, offsets, and text. You can skim the JSON or a companion
Markdown summary to find chunk ids to reference in `report_refs` per article.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


def chunk_text(text: str, max_chars: int, overlap: int) -> Iterable[str]:
    """
    Yield roughly fixed-size chunks with character overlap to reduce boundary loss.
    Streamed to avoid holding everything in memory.
    """
    max_chars = max(1, max_chars)
    overlap = max(0, min(overlap, max_chars - 1))
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        if end == n:
            break
        start = max(0, end - overlap)


def write_json(chunks: Iterable[str], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("[\n")
        first = True
        for idx, chunk in enumerate(chunks, start=1):
            if not first:
                f.write(",\n")
            json.dump(
                {"id": f"chunk-{idx}", "offset": idx - 1, "text": chunk},
                f,
                ensure_ascii=False,
            )
            first = False
        f.write("\n]\n")
    print(f"Wrote chunk index to {out_path}")


def write_md(chunks: Iterable[str], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for idx, chunk in enumerate(chunks, start=1):
            f.write(f"## chunk-{idx}\n\n{chunk}\n\n")
    print(f"Wrote chunk preview to {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk a Markdown report into indexed snippets.")
    parser.add_argument("--md", type=Path, required=True, help="Input Markdown file (converted report)")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON path for chunk index")
    parser.add_argument("--out-md", type=Path, help="Optional Markdown preview of chunks")
    parser.add_argument("--max-chars", type=int, default=1200, help="Max characters per chunk")
    parser.add_argument("--overlap", type=int, default=200, help="Character overlap between chunks")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    text = args.md.read_text(encoding="utf-8")
    chunks_for_json = list(chunk_text(text, max_chars=args.max_chars, overlap=args.overlap))
    if args.verbose:
        print(f"✂️  Generated {len(chunks_for_json)} chunks (max_chars={args.max_chars}, overlap={args.overlap})")
        for idx, chunk in enumerate(chunks_for_json[:10], start=1):
            preview = chunk[:80].replace("\n", " ")
            print(f"\033[94mchunk-{idx}: {preview}...\033[0m")
        if len(chunks_for_json) > 10:
            print(f"... (+{len(chunks_for_json)-10} more)")
        sys.stdout.flush()
    write_json(chunks_for_json, args.out)
    if args.out_md:
        write_md(chunks_for_json, args.out_md)


if __name__ == "__main__":
    main()
