"""
Do-everything command: generate issue.json (if missing), prepare corpus, and draft articles.

Usage:
  python -m tools.publish_issue --project my-project --input /path/to/report.txt --artifact magazine
"""
from __future__ import annotations

import argparse
from pathlib import Path

from nfl_remember_the_future.drafting import draft_articles
from nfl_remember_the_future.llm import get_client_from_env
from nfl_remember_the_future.models import DraftConfig
from tools.generate_issue import generate_issue_file
from tools.prepare_corpus import prepare_project


def resolve_project_root(project: str) -> Path:
    return Path("projects") / project


def resolve_path(path: Path, project_root: Path) -> Path:
    if path.is_absolute():
        return path
    return project_root / path


def resolve_schema(schema_json: Path, project_root: Path) -> Path:
    candidate = resolve_path(schema_json, project_root)
    if candidate.exists():
        return candidate
    fallback = Path.cwd() / schema_json
    if fallback.exists():
        return fallback
    return candidate


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate, ground, and draft an issue end-to-end.")
    p.add_argument("--project", required=True, help="Project name under projects/")
    p.add_argument("--input", required=True, type=Path, nargs="+", help="Source report file(s) (txt/md/html)")
    p.add_argument("--artifact", choices=["magazine", "newspaper", "catalog"], required=True)
    p.add_argument("--schema-json", type=Path, default=Path("ai2027_issue.schema.json"), help="Schema JSON path")
    p.add_argument("--issue", type=Path, default=Path("issue.json"), help="Issue JSON in project")
    p.add_argument("--grounded-issue", type=Path, default=Path("issue.grounded.json"), help="Grounded issue JSON in project")
    p.add_argument("--report", type=Path, default=Path("report.md"), help="Report markdown output")
    p.add_argument("--chunks", type=Path, default=Path("report_chunks.json"), help="Chunk JSON output")
    p.add_argument("--chunks-md", type=Path, default=Path("report_chunks.md"), help="Chunk preview output")
    p.add_argument("--labels", type=Path, default=Path("report_chunk_labels.json"), help="Chunk labels output")
    p.add_argument("--report-context", type=Path, default=Path("prompts/report_context.md"), help="Report context output")
    p.add_argument("--num-items", type=int, default=None, help="Override item count for issue generation")
    llm_group = p.add_mutually_exclusive_group()
    llm_group.add_argument("--use-llm", dest="use_llm", action="store_true", help="Use LLM to label chunks (default)")
    llm_group.add_argument("--no-llm", dest="use_llm", action="store_false", help="Use heuristic labeling instead of an LLM")
    p.set_defaults(use_llm=True)
    p.add_argument("--llm-model", type=str, default=None, help="Override model for chunk labeling")
    p.add_argument("--llm-temperature", type=float, default=0.0, help="Temperature for chunk labeling")
    p.add_argument("--refs-per-article", type=int, default=2, help="Chunk refs per article")
    p.add_argument("--context-chunks", type=int, default=2, help="Context chunks for report_context.md")
    p.add_argument("--include-ref-details", action="store_true", help="Include ref details in grounded issue")
    p.add_argument("--draft", default="all", help="Article id(s) to draft (default: all)")
    p.add_argument("--generate-image-prompt", action="store_true", help="Generate image prompts in frontmatter")
    p.add_argument("--overwrite-issue", action="store_true", help="Overwrite issue.json when generating")
    p.add_argument("--append-issue", action="store_true", help="Append generated articles to existing issue.json")
    p.add_argument("--overwrite-drafts", action="store_true", help="Overwrite existing drafts")
    p.add_argument("--skip-generate", action="store_true", help="Skip issue generation")
    p.add_argument("--skip-prepare", action="store_true", help="Skip grounding/corpus prep")
    p.add_argument("--skip-draft", action="store_true", help="Skip drafting")
    p.add_argument("--skip-chunk", action="store_true", help="Skip chunking if chunks exist")
    p.add_argument("--skip-label", action="store_true", help="Skip labeling if labels exist")
    p.add_argument("--quiet", action="store_true", help="Minimal logging")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    project_root = resolve_project_root(args.project)
    input_paths = args.input

    issue_path = resolve_path(args.issue, project_root)
    grounded_path = resolve_path(args.grounded_issue, project_root)
    report_path = resolve_path(args.report, project_root)
    chunks_path = resolve_path(args.chunks, project_root)
    chunks_md_path = resolve_path(args.chunks_md, project_root)
    labels_path = resolve_path(args.labels, project_root)
    report_context_path = resolve_path(args.report_context, project_root)
    schema_path = resolve_schema(args.schema_json, project_root)

    if not args.quiet:
        print(f"[publish] project={project_root}")
        print(f"[publish] inputs={[str(p) for p in input_paths]}")
        print(f"[publish] artifact={args.artifact}")

    if not args.skip_generate:
        if not issue_path.exists() or args.overwrite_issue or args.append_issue:
            generate_issue_file(
                project_root=project_root,
                input_path=input_paths,
                artifact=args.artifact,
                issue_out_path=issue_path,
                labels_path=labels_path,
                num_items=args.num_items,
                temperature=0.6,
                max_completion_tokens=2600,
                model_override=None,
                overwrite=args.overwrite_issue,
                append=args.append_issue,
                quiet=args.quiet,
                no_repair=False,
                no_print_prompts=False,
                no_print_response=False,
            )
        elif not args.quiet:
            print(f"[publish] issue exists, skipping generate ({issue_path})")
    else:
        if not issue_path.exists():
            raise SystemExit(f"Missing issue.json at {issue_path}. Remove --skip-generate or create one.")

    if not args.skip_prepare:
        prepare_project(
            project_root=project_root,
            input_path=input_paths,
            issue_path=issue_path,
            out_issue_path=grounded_path,
            report_path=report_path,
            chunks_path=chunks_path,
            chunks_md_path=chunks_md_path,
            labels_path=labels_path,
            report_context_path=report_context_path,
            max_chars=1200,
            overlap=200,
            use_llm=args.use_llm,
            llm_model=args.llm_model,
            llm_temperature=args.llm_temperature,
            refs_per_article=args.refs_per_article,
            context_chunks=args.context_chunks,
            include_ref_details=args.include_ref_details,
            quiet=args.quiet,
            init_issue=False,
            skip_label=args.skip_label,
            skip_chunk=args.skip_chunk,
        )
    else:
        if not grounded_path.exists():
            raise SystemExit(f"Missing grounded issue at {grounded_path}. Remove --skip-prepare or generate it.")

    if not args.skip_draft:
        prompt_dir = project_root / "prompts"
        if not prompt_dir.exists():
            prompt_dir = Path("prompts")
        config = DraftConfig(
            project_root=project_root,
            issue_json=grounded_path,
            schema_json=schema_path,
            prompt_dir=prompt_dir,
            out_md_dir=project_root / "drafts",
            index_json=project_root / "drafts/index.json",
            article_id=args.draft,
            model=None,
            temperature=0.6,
            max_completion_tokens=1800,
            overwrite_existing=args.overwrite_drafts,
            write_annotated_json=False,
            out_json=None,
            dry_run=False,
            dry_run_text=None,
            verbose=not args.quiet,
            frontmatter_only=False,
            generate_image_prompt=args.generate_image_prompt,
            draft_prefix=None,
        )
        client = get_client_from_env()
        draft_articles(config=config, client=client)
    elif not args.quiet:
        print("[publish] skip_draft=true")

    if not args.quiet:
        print("[publish] done")


if __name__ == "__main__":
    main()
