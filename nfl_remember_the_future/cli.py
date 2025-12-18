from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .drafting import draft_articles
from .llm import get_client_from_env
from .models import DraftConfig

app = typer.Typer(add_completion=False)

def resolve_path(path: Path, project_root: Optional[Path]) -> Path:
    if project_root and not path.is_absolute():
        return project_root / path
    return path


def resolve_prompt_dir(prompt_dir: Path, project_root: Optional[Path]) -> Path:
    if not project_root:
        return prompt_dir
    if prompt_dir == Path("prompts"):
        candidate = project_root / "prompts"
        if candidate.exists():
            return candidate
        return prompt_dir
    if not prompt_dir.is_absolute():
        return project_root / prompt_dir
    return prompt_dir


def main() -> None:
    app()


@app.command()
def draft(
    project: Optional[str] = typer.Option(None, help="Project name under projects/ (shortcut)"),
    project_root: Optional[Path] = typer.Option(None, help="Project workspace root for inputs/outputs"),
    issue_json: Path = typer.Option(..., help="Path to issue JSON"),
    schema_json: Optional[Path] = typer.Option(None, help="Path to JSON Schema (defaults to project/issue.schema.json)"),
    prompt_dir: Path = typer.Option(Path("prompts"), help="Directory with prompt files"),
    out_md_dir: Path = typer.Option(Path("drafts"), help="Directory to write per-article Markdown backups"),
    draft_prefix: Optional[str] = typer.Option(None, help="Optional prefix for file names; also prefixes the drafts folder when using the default location"),
    index_json: Path = typer.Option(Path("drafts/index.json"), help="Where to write draft index JSON"),
    article_id: str = typer.Option("all", help="Article id number, or 'all'"),
    model: Optional[str] = typer.Option(None, help="Model name (default: OPENAI_MODEL from .env, else gpt-4.1)"),
    temperature: float = typer.Option(0.6, help="Sampling temperature"),
    max_completion_tokens: int = typer.Option(1800, help="Max completion tokens for the response"),
    overwrite_existing: bool = typer.Option(False, help="Overwrite drafts already present in Markdown"),
    write_annotated_json: bool = typer.Option(False, help="Write an annotated issue JSON"),
    out_json: Optional[Path] = typer.Option(None, help="Annotated JSON path (default overwrites input if flag is set)"),
    dry_run: bool = typer.Option(False, help="Skip API calls and write placeholder drafts"),
    dry_run_text: Optional[str] = typer.Option(None, help="Custom placeholder text for --dry-run"),
    verbose: bool = typer.Option(True, help="Verbose logging"),
    frontmatter_only: bool = typer.Option(False, help="Only refresh frontmatter; leave body untouched"),
    generate_image_prompt: bool = typer.Option(False, help="Generate an image prompt and store in frontmatter"),
    overwrite_frontmatter_only: bool = typer.Option(False, help="Force frontmatter refresh while preserving body (alias: implies --frontmatter-only and --overwrite-existing)"),
):
    """
    Draft one article or all articles, writing results to Markdown and a draft index.
    Issue JSON remains read-only unless --write-annotated-json is provided.
    """
    if project and project_root:
        raise typer.BadParameter("Use either --project or --project-root, not both.")
    if project:
        project_root = Path("projects") / project
    client = get_client_from_env()
    resolved_issue_json = resolve_path(issue_json, project_root)
    if schema_json:
        resolved_schema_json = resolve_path(schema_json, project_root)
        if project_root and not resolved_schema_json.exists() and not schema_json.is_absolute():
            fallback = Path.cwd() / schema_json
            if fallback.exists():
                resolved_schema_json = fallback
    else:
        default_schema = project_root / "issue.schema.json" if project_root else Path("issue.schema.json")
        if not default_schema.exists():
            raise typer.BadParameter(
                f"No schema found at {default_schema}. Place an issue.schema.json in the project root "
                "or pass --schema-json explicitly."
            )
        resolved_schema_json = default_schema
    resolved_prompt_dir = resolve_prompt_dir(prompt_dir, project_root)
    default_drafts_dir = Path(f"{draft_prefix}_drafts") if draft_prefix else out_md_dir
    if draft_prefix and out_md_dir == Path("drafts"):
        effective_out_dir = default_drafts_dir
    else:
        effective_out_dir = out_md_dir
    resolved_out_md_dir = resolve_path(effective_out_dir, project_root)
    index_candidate = index_json
    if draft_prefix and index_json == Path("drafts/index.json"):
        index_candidate = default_drafts_dir / "index.json"
    resolved_index_json = resolve_path(index_candidate, project_root)
    resolved_out_json = resolve_path(out_json, project_root) if out_json else None
    config = DraftConfig(
        project_root=project_root,
        issue_json=resolved_issue_json,
        schema_json=resolved_schema_json,
        prompt_dir=resolved_prompt_dir,
        out_md_dir=resolved_out_md_dir,
        index_json=resolved_index_json,
        article_id=article_id,
        model=model,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        overwrite_existing=overwrite_existing or overwrite_frontmatter_only,
        write_annotated_json=write_annotated_json,
        out_json=resolved_out_json,
        dry_run=dry_run,
        dry_run_text=dry_run_text,
        verbose=verbose,
        frontmatter_only=frontmatter_only or overwrite_frontmatter_only,
        generate_image_prompt=generate_image_prompt,
        draft_prefix=draft_prefix,
    )
    draft_articles(config=config, client=client)


if __name__ == "__main__":
    main()
