from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .drafting import draft_articles
from .llm import get_client_from_env
from .models import DraftConfig

app = typer.Typer(add_completion=False)


def main() -> None:
    app()


@app.command()
def draft(
    issue_json: Path = typer.Option(..., help="Path to issue JSON"),
    schema_json: Path = typer.Option(..., help="Path to JSON Schema"),
    prompt_dir: Path = typer.Option(Path("prompts"), help="Directory with prompt files"),
    out_md_dir: Path = typer.Option(Path("drafts"), help="Directory to write per-article Markdown backups"),
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
    verbose: bool = typer.Option(False, help="Verbose logging"),
):
    """
    Draft one article or all articles, writing results to Markdown and a draft index.
    Issue JSON remains read-only unless --write-annotated-json is provided.
    """
    client = get_client_from_env()
    config = DraftConfig(
        issue_json=issue_json,
        schema_json=schema_json,
        prompt_dir=prompt_dir,
        out_md_dir=out_md_dir,
        index_json=index_json,
        article_id=article_id,
        model=model,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        overwrite_existing=overwrite_existing,
        write_annotated_json=write_annotated_json,
        out_json=out_json,
        dry_run=dry_run,
        dry_run_text=dry_run_text,
        verbose=verbose,
    )
    draft_articles(config=config, client=client)


if __name__ == "__main__":
    main()
