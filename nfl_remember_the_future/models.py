from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ArticleSpec:
    id: int
    title: str
    format: str
    lede: str
    byline: str
    report_anchor: List[str]
    writing_directions: List[str]
    prompt_example: Optional[str] = None
    report_refs: List[str] = field(default_factory=list)
    report_ref_details: List[Dict[str, Any]] = field(default_factory=list)
    image_prompt: Optional[str] = None
    draft_tokens: Optional[int] = None
    image_prompt_tokens: Optional[int] = None
    draft: str = ""
    design_fiction: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DraftRecord:
    article_id: int
    title: str
    format: str
    md_path: str
    model: str
    temperature: float
    timestamp: str


@dataclass
class DraftIndex:
    issue: Dict[str, Any] = field(default_factory=dict)
    drafts: List[DraftRecord] = field(default_factory=list)


@dataclass
class DraftConfig:
    project_root: Optional[Path]
    issue_json: Path
    schema_json: Path
    prompt_dir: Path
    out_md_dir: Path
    index_json: Path
    article_id: str
    model: Optional[str]
    temperature: float
    max_completion_tokens: int
    overwrite_existing: bool
    write_annotated_json: bool
    out_json: Optional[Path]
    dry_run: bool = False
    dry_run_text: Optional[str] = None
    verbose: bool = False
    frontmatter_only: bool = False
    generate_image_prompt: bool = False
    draft_prefix: Optional[str] = None


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
