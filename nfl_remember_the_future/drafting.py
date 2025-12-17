from __future__ import annotations

import copy
from typing import Any, Dict, List, Sequence

import typer
from jsonschema import validate

from .io_utils import (
    ensure_dir,
    load_index,
    load_prompt_dir,
    read_json,
    save_index,
    slugify,
    upsert_record,
    write_json,
)
from .llm import draft_one, resolve_model
from .models import ArticleSpec, DraftConfig, DraftRecord, now_iso
from .prompts import build_system_prompt, build_user_prompt


def render_metadata_block(spec: ArticleSpec, issue_meta: Dict[str, Any]) -> str:
    """Render metadata as YAML frontmatter for MD/MDX consumers."""
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()

    def list_block(name: str, items: List[str]) -> List[str]:
        block = [f"{name}:"]
        for it in items:
            block.append(f'  - "{esc(it)}"')
        return block

    lines: List[str] = ["---"]
    lines.append(f'issue: "{esc(str(issue_meta.get("title", "")))}"')
    lines.append(f'date: "{esc(str(issue_meta.get("date", "")))}"')
    lines.append(f"id: {spec.id}")
    lines.append(f'title: "{esc(spec.title)}"')
    lines.append(f'format: "{esc(spec.format)}"')
    lines.append(f'byline: "{esc(spec.byline)}"')

    lines.extend(list_block("anchors", spec.ai2027_anchor))
    lines.extend(list_block("writing_directions", spec.writing_directions))

    if spec.report_refs:
        lines.extend(list_block("report_refs", spec.report_refs))

    if spec.report_ref_details:
        lines.append("report_ref_details:")
        for d in spec.report_ref_details:
            lines.append("  -")
            lines.append(f'    id: "{esc(d.get("id", ""))}"')
            lines.append(f'    summary: "{esc(d.get("summary", ""))}"')
            kws = d.get("keywords", [])
            lines.append("    keywords:")
            for kw in kws:
                lines.append(f'      - "{esc(kw)}"')

    lines.append("---\n")
    return "\n".join(lines)


def load_issue_and_schema(issue_json, schema_json) -> Dict[str, Any]:
    issue = read_json(issue_json)
    schema = read_json(schema_json)
    validate(instance=issue, schema=schema)
    return issue


def select_articles(articles: Sequence[Dict[str, Any]], article_id: str) -> List[Dict[str, Any]]:
    if not isinstance(articles, list) or not articles:
        raise typer.BadParameter("No articles found in issue JSON.")

    if article_id.lower() == "all":
        return list(articles)

    try:
        wanted = int(article_id)
    except ValueError as exc:
        raise typer.BadParameter("article_id must be an integer or 'all'.") from exc

    selected = [a for a in articles if int(a.get("id")) == wanted]
    if not selected:
        raise typer.BadParameter(f"No article with id={wanted} found.")
    return selected


def hydrate_article(raw: Dict[str, Any]) -> ArticleSpec:
    return ArticleSpec(
        id=int(raw["id"]),
        title=raw["title"],
        format=raw["format"],
        lede=raw["lede"],
        byline=raw["byline"],
        ai2027_anchor=list(raw["ai2027_anchor"]),
        writing_directions=list(raw["writing_directions"]),
        prompt_example=raw.get("prompt_example"),
        report_refs=list(raw.get("report_refs", []) or []),
        report_ref_details=list(raw.get("report_ref_details", []) or []),
        draft=raw.get("draft", "") or "",
    )


def annotate_issue(issue: Dict[str, Any], record: DraftRecord) -> Dict[str, Any]:
    annotated = copy.deepcopy(issue)
    for art in annotated.get("articles", []):
        if int(art.get("id")) == record.article_id:
            art["draft_path"] = record.md_path
            art["draft_timestamp"] = record.timestamp
    return annotated


def draft_articles(config: DraftConfig, client, now_fn=now_iso) -> None:
    issue = load_issue_and_schema(config.issue_json, config.schema_json)
    issue_meta = issue.get("issue", {})
    style_anchor_text = (issue.get("style_anchor", {}) or {}).get("content", "") or ""
    prompts = load_prompt_dir(config.prompt_dir)
    report_context = prompts.get("report_context", "")
    articles = select_articles(issue.get("articles", []), config.article_id)

    ensure_dir(config.out_md_dir)
    index = load_index(config.index_json, issue_meta)
    resolved_model = resolve_model(config.model)

    for raw in articles:
        spec = hydrate_article(raw)
        md_name = f"{spec.id:02d}_{slugify(spec.title)}.md"
        md_path = config.out_md_dir / md_name

        if md_path.exists() and not config.overwrite_existing:
            typer.echo(f"Skipping id={spec.id} (draft exists; use --overwrite-existing).")
            continue

        system_prompt = build_system_prompt(prompts, spec, style_anchor_text, report_context)
        user_prompt = build_user_prompt(spec, issue_meta)

        typer.echo(f"Drafting id={spec.id}: {spec.title}")
        if config.verbose:
            typer.echo(f"  → Writing to: {md_path}")
            typer.echo(f"  → Model: {resolved_model} | Temp: {config.temperature} | Max completion tokens: {config.max_completion_tokens}")
            if spec.report_refs or spec.report_ref_details:
                typer.echo(f"  → Report refs: {', '.join(spec.report_refs) if spec.report_refs else 'none'}")
            typer.echo(f"  → Anchors: {len(spec.ai2027_anchor)} | Directions: {len(spec.writing_directions)}")
        if config.dry_run:
            draft_text = config.dry_run_text or "[DRY RUN] Draft placeholder."
        else:
            draft_text = draft_one(
                client=client,
                model=resolved_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=config.temperature,
                max_completion_tokens=config.max_completion_tokens,
            )
            if not draft_text.strip():
                warning = "[WARNING] Draft was empty from the model; please re-run or adjust parameters."
                if config.verbose:
                    typer.echo(f"  ! Empty draft received from model; writing warning placeholder.")
                draft_text = warning

        metadata_block = render_metadata_block(spec, issue_meta)
        md_path.write_text(metadata_block + draft_text + "\n", encoding="utf-8")

        record = DraftRecord(
            article_id=spec.id,
            title=spec.title,
            format=spec.format,
            md_path=str(md_path),
            model=resolved_model if not config.dry_run else "dry-run",
            temperature=config.temperature,
            timestamp=now_fn(),
        )

        index = upsert_record(index, record)

        if config.write_annotated_json:
            annotated = annotate_issue(issue, record)
            target_json = config.out_json or config.issue_json
            write_json(target_json, annotated)

    save_index(config.index_json, index)
    typer.echo(f"Markdown backups written to: {config.out_md_dir.resolve()}")
    typer.echo(f"Index written to: {config.index_json.resolve()}")
