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
from typing import Iterable, Optional

from tools.project_paths import normalize_project_root


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


def resolve_path(path: Optional[Path], project_root: Optional[Path]) -> Optional[Path]:
    if path is None:
        return None
    normalized_root = normalize_project_root(project_root)
    if normalized_root and not path.is_absolute():
        return normalized_root / path
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk a Markdown report into indexed snippets.")
    parser.add_argument("--project-root", type=Path, help="Project workspace root for inputs/outputs")
    parser.add_argument("--md", type=Path, required=True, help="Input Markdown file (converted report)")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON path for chunk index")
    parser.add_argument("--out-md", type=Path, help="Optional Markdown preview of chunks")
    parser.add_argument("--max-chars", type=int, default=1200, help="Max characters per chunk")
    parser.add_argument("--overlap", type=int, default=200, help="Character overlap between chunks")
    parser.add_argument("--verbose", action="store_true", help="Extra verbose logging (longer previews)")
    parser.add_argument("--quiet", action="store_true", help="Minimal logging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    md_path = resolve_path(args.md, args.project_root)
    out_path = resolve_path(args.out, args.project_root)
    out_md_path = resolve_path(args.out_md, args.project_root)

    text = md_path.read_text(encoding="utf-8")
    chunks_for_json = list(chunk_text(text, max_chars=args.max_chars, overlap=args.overlap))
    lengths = [len(c) for c in chunks_for_json]
    avg_len = sum(lengths) / len(lengths) if lengths else 0
    min_len = min(lengths) if lengths else 0
    max_len = max(lengths) if lengths else 0
    if not args.quiet:
        print(
            f"[chunk_report] chunks={len(chunks_for_json)} "
            f"max_chars={args.max_chars} overlap={args.overlap} "
            f"avg_chars={avg_len:.0f} min={min_len} max={max_len}"
        )
        for idx, chunk in enumerate(chunks_for_json, start=1):
            limit = 200 if args.verbose else 80
            preview = chunk[:limit].replace("\n", " ")
            print(f"[chunk {idx:03d}/{len(chunks_for_json):03d}] len={len(chunk)} {preview}...")
        sys.stdout.flush()
    write_json(chunks_for_json, out_path)
    if out_md_path:
        write_md(chunks_for_json, out_md_path)


if __name__ == "__main__":
    main()
