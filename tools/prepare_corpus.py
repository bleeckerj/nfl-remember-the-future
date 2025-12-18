"""
Wrapper: prepare a project workspace by chunking, labeling, and auto-grounding a report.

Usage:
  python -m tools.prepare_corpus --project my-project --input /path/to/report.html
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.auto_ground import build_context, load_json, suggest_refs, write_json
from tools.chunk_report import chunk_text, write_json as write_chunks_json, write_md as write_chunks_md
from tools.html_to_md import html_to_md
from tools.label_chunks import load_chunks, resolve_model, write_labels, write_labels_llm


def resolve_project_root(project: str) -> Path:
    return Path("projects") / project


def resolve_path(path: Path, project_root: Path) -> Path:
    if path.is_absolute():
        return path
    return project_root / path


def load_or_copy_report(input_paths: list[Path], report_path: Path, quiet: bool) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    for p in input_paths:
        if p.suffix.lower() in {".html", ".htm"}:
            html_to_md(p, report_path, strip_data=True, gibberish_threshold=200, quiet=quiet)
            text = report_path.read_text(encoding="utf-8")
        else:
            text = p.read_text(encoding="utf-8")
        parts.append(f"---- SOURCE: {p.name} ----\n{text.strip()}\n")
    report_path.write_text("\n\n".join(parts), encoding="utf-8")
    if not quiet:
        print(f"[prepare] wrote_report={report_path} from {len(input_paths)} source(s)")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prepare a project corpus (chunk → label → auto-ground).")
    p.add_argument("--project", required=True, help="Project name under projects/")
    p.add_argument("--input", required=True, type=Path, nargs="+", help="Source report file(s) (txt/md/html)")
    p.add_argument("--issue", type=Path, default=Path("issue.json"), help="Issue JSON in the project")
    p.add_argument("--out-issue", type=Path, default=Path("issue.grounded.json"), help="Output grounded issue JSON")
    p.add_argument("--report", type=Path, default=Path("report.md"), help="Where to write the normalized report text")
    p.add_argument("--chunks", type=Path, default=Path("report_chunks.json"), help="Output chunk JSON")
    p.add_argument("--chunks-md", type=Path, default=Path("report_chunks.md"), help="Output chunk preview Markdown")
    p.add_argument("--labels", type=Path, default=Path("report_chunk_labels.json"), help="Output labeled chunk JSON")
    p.add_argument("--report-context", type=Path, default=Path("prompts/report_context.md"), help="Output report context excerpt")
    p.add_argument("--max-chars", type=int, default=1200, help="Max characters per chunk")
    p.add_argument("--overlap", type=int, default=200, help="Character overlap between chunks")
    llm_group = p.add_mutually_exclusive_group()
    llm_group.add_argument("--use-llm", dest="use_llm", action="store_true", help="Use LLM to label chunks (default)")
    llm_group.add_argument("--no-llm", dest="use_llm", action="store_false", help="Use heuristic labeling instead of an LLM")
    p.set_defaults(use_llm=True)
    p.add_argument("--llm-model", type=str, default=None, help="Override model for LLM labeling")
    p.add_argument("--llm-temperature", type=float, default=0.0, help="Temperature for LLM labeling")
    p.add_argument("--refs-per-article", type=int, default=2, help="How many chunk ids to attach per article")
    p.add_argument("--context-chunks", type=int, default=2, help="How many top chunks to concatenate for context")
    p.add_argument("--include-ref-details", action="store_true", help="Include summaries/keywords for refs in output issue JSON")
    p.add_argument("--quiet", action="store_true", help="Reduce per-chunk output")
    p.add_argument("--init-issue", action="store_true", help="Create a starter issue.json if missing")
    p.add_argument("--skip-label", action="store_true", help="Skip labeling if labels already exist")
    p.add_argument("--skip-chunk", action="store_true", help="Skip chunking if chunk files already exist")
    return p.parse_args()


def write_issue_template(issue_path: Path, project: str) -> None:
    issue_path.parent.mkdir(parents=True, exist_ok=True)
    template = {
        "issue": {
            "title": f"{project} (draft)",
            "date": "YYYY-MM-DD",
            "status": "draft",
            "source": "Report",
        },
        "articles": [],
    }
    issue_path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote starter issue JSON to {issue_path}")


def prepare_project(
    project_root: Path,
    input_path: list[Path],
    issue_path: Path,
    out_issue_path: Path,
    report_path: Path,
    chunks_path: Path,
    chunks_md_path: Path | None,
    labels_path: Path,
    report_context_path: Path,
    max_chars: int,
    overlap: int,
    use_llm: bool,
    llm_model: str | None,
    llm_temperature: float,
    refs_per_article: int,
    context_chunks: int,
    include_ref_details: bool,
    quiet: bool,
    init_issue: bool,
    skip_label: bool,
    skip_chunk: bool,
) -> Path:
    project_root.mkdir(parents=True, exist_ok=True)

    input_paths = [p.expanduser().resolve() for p in input_path]
    if not issue_path.exists():
        if init_issue:
            write_issue_template(issue_path, project_root.name)
        else:
            raise SystemExit(
                "Missing issue JSON. Create it first or rerun with --init-issue to scaffold "
                f"{issue_path}."
            )

    if not quiet:
        print(f"[prepare] project={project_root}")
        print(f"[prepare] inputs={[str(p) for p in input_paths]}")
        print(f"[prepare] issue={issue_path}")
    load_or_copy_report(input_paths, report_path, quiet=quiet)

    chunks: list[str] = []
    if skip_chunk:
        if not chunks_path.exists():
            raise SystemExit(f"Missing chunk file at {chunks_path}. Remove --skip-chunk or generate chunks first.")
        if not quiet:
            print(f"[prepare] skipping chunk step (using {chunks_path})")
    else:
        text = report_path.read_text(encoding="utf-8")
        chunks = list(chunk_text(text, max_chars=max_chars, overlap=overlap))
        if not quiet:
            print(f"[prepare] chunking report chars={len(text)}")
            for idx, chunk in enumerate(chunks, start=1):
                preview = chunk[:80].replace("\n", " ")
                print(f"[prepare] chunk {idx:03d}/{len(chunks):03d} len={len(chunk)} {preview}...")
        write_chunks_json(chunks, chunks_path)
        if chunks_md_path:
            write_chunks_md(chunks, chunks_md_path)

    if skip_label:
        if not labels_path.exists():
            raise SystemExit(f"Missing labels file at {labels_path}. Remove --skip-label or generate labels first.")
        if not quiet:
            print(f"[prepare] skipping label step (using {labels_path})")
    else:
        if not quiet:
            print(f"[prepare] labeling chunks count={len(chunks) if chunks else 'from file'}")
        if use_llm:
            model = resolve_model(llm_model)
            if not quiet:
                print(f"[prepare] label_mode=llm model={model} temp={llm_temperature}")
            write_labels_llm(
                load_chunks(chunks_path),
                labels_path,
                model=model,
                temperature=llm_temperature,
                verbose=not quiet,
                quiet=quiet,
            )
        else:
            if not quiet:
                print("[prepare] label_mode=heuristic")
            write_labels(load_chunks(chunks_path), labels_path, verbose=not quiet, quiet=quiet)

    if not quiet:
        print(f"[prepare] auto_ground refs_per_article={refs_per_article} include_details={include_ref_details}")
    issue = load_json(issue_path)
    labeled_chunks = load_json(labels_path)
    updated_issue, _ = suggest_refs(
        issue,
        labeled_chunks,
        refs_per_article=refs_per_article,
        include_details=include_ref_details,
        verbose=not quiet,
    )
    write_json(out_issue_path, updated_issue)
    if not quiet:
        print(f"[prepare] wrote_issue={out_issue_path}")

    ctx = build_context(labeled_chunks, context_chunks)
    report_context_path.parent.mkdir(parents=True, exist_ok=True)
    report_context_path.write_text(ctx + "\n", encoding="utf-8")
    if not quiet:
        print(f"[prepare] wrote_context={report_context_path} chunks={context_chunks}")
        print("[prepare] done")
    return out_issue_path


def main() -> None:
    args = parse_args()
    project_root = resolve_project_root(args.project)
    prepare_project(
        project_root=project_root,
        input_path=args.input,  # type: ignore[arg-type]
        issue_path=resolve_path(args.issue, project_root),
        out_issue_path=resolve_path(args.out_issue, project_root),
        report_path=resolve_path(args.report, project_root),
        chunks_path=resolve_path(args.chunks, project_root),
        chunks_md_path=resolve_path(args.chunks_md, project_root) if args.chunks_md else None,
        labels_path=resolve_path(args.labels, project_root),
        report_context_path=resolve_path(args.report_context, project_root),
        max_chars=args.max_chars,
        overlap=args.overlap,
        use_llm=args.use_llm,
        llm_model=args.llm_model,
        llm_temperature=args.llm_temperature,
        refs_per_article=args.refs_per_article,
        context_chunks=args.context_chunks,
        include_ref_details=args.include_ref_details,
        quiet=args.quiet,
        init_issue=args.init_issue,
        skip_label=args.skip_label,
        skip_chunk=args.skip_chunk,
    )


if __name__ == "__main__":
    main()
