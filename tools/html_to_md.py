"""
Utility: Convert an HTML report to Markdown for prompt/context curation.

Usage:
    python -m tools.html_to_md --html AI_2027.html --out report.md

This is intended as a pre-processing helper; do NOT dump the full report into prompts.
Curate a short excerpt from the Markdown output and paste it into prompts/report_context.md
or style_anchor.content in the issue JSON.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

from tools.project_paths import normalize_project_root

try:
    from markdownify import markdownify as md
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install markdownify: pip install markdownify") from exc


def clean_html(html: str, strip_data: bool, gibberish_threshold: int) -> str:
    cleaned = html
    if strip_data:
        # Drop <img ... src="data:..."> and inline data: URIs.
        cleaned = re.sub(r'<img[^>]+src="data:[^"]+"[^>]*>', "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'data:[^"\'\\s>]+', "", cleaned, flags=re.IGNORECASE)
    if gibberish_threshold > 0:
        # Remove very long base64-like runs.
        cleaned = re.sub(rf"[A-Za-z0-9+/=]{{{gibberish_threshold},}}", "", cleaned)
    return cleaned


def html_to_md(html_path: Path, out_path: Path, strip_data: bool, gibberish_threshold: int, quiet: bool = False) -> None:
    in_size = html_path.stat().st_size if html_path.exists() else 0
    if not quiet:
        print(f"[html_to_md] input={html_path} bytes={in_size}")
    html = html_path.read_text(encoding="utf-8")
    html = clean_html(html, strip_data=strip_data, gibberish_threshold=gibberish_threshold)
    markdown = md(html, heading_style="ATX")
    out_path.write_text(markdown, encoding="utf-8")
    out_size = out_path.stat().st_size if out_path.exists() else 0
    if not quiet:
        print(f"[html_to_md] strip_data={strip_data} gibberish_threshold={gibberish_threshold}")
        print(f"[html_to_md] output={out_path} bytes={out_size}")
    sys.stdout.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert HTML to Markdown for prompt context.")
    parser.add_argument("--project-root", type=Path, help="Project workspace root for inputs/outputs")
    parser.add_argument("--html", type=Path, required=True, help="Input HTML file")
    parser.add_argument("--out", type=Path, required=True, help="Output Markdown file")
    parser.add_argument(
        "--strip-data",
        action="store_true",
        default=True,
        help="Remove data: URIs and embedded <img> data before converting (default: on)",
    )
    parser.add_argument(
        "--gibberish-threshold",
        type=int,
        default=200,
        help="Remove contiguous base64-like runs longer than this (0 to disable)",
    )
    parser.add_argument("--quiet", action="store_true", help="Minimal logging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    html_path = resolve_path(args.html, args.project_root)
    out_path = resolve_path(args.out, args.project_root)
    html_to_md(
        html_path,
        out_path,
        strip_data=args.strip_data,
        gibberish_threshold=args.gibberish_threshold,
        quiet=args.quiet,
    )


def resolve_path(path: Optional[Path], project_root: Optional[Path]) -> Optional[Path]:
    if path is None:
        return None
    normalized_root = normalize_project_root(project_root)
    if normalized_root and not path.is_absolute():
        return normalized_root / path
    return path


if __name__ == "__main__":
    main()
