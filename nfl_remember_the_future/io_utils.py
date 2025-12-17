from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from .models import DraftIndex, DraftRecord


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_prompt_dir(prompt_dir: Path) -> Dict[str, str]:
    prompts: Dict[str, str] = {}
    for p in prompt_dir.glob("*.md"):
        prompts[p.stem] = read_text(p).strip()
    return prompts


def slugify(s: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or "article"


def load_index(path: Path, issue_meta: Dict[str, Any]) -> DraftIndex:
    if not path.exists():
        return DraftIndex(issue=issue_meta, drafts=[])

    raw = read_json(path)
    drafts = [
        DraftRecord(
            article_id=int(d["article_id"]),
            title=d["title"],
            format=d["format"],
            md_path=d["md_path"],
            model=d["model"],
            temperature=float(d["temperature"]),
            timestamp=d["timestamp"],
        )
        for d in raw.get("drafts", [])
    ]
    return DraftIndex(issue=raw.get("issue", issue_meta), drafts=drafts)


def save_index(path: Path, index: DraftIndex) -> None:
    data = {
        "issue": index.issue,
        "drafts": [
            {
                "article_id": d.article_id,
                "title": d.title,
                "format": d.format,
                "md_path": d.md_path,
                "model": d.model,
                "temperature": d.temperature,
                "timestamp": d.timestamp,
            }
            for d in index.drafts
        ],
    }
    ensure_dir(path.parent)
    write_json(path, data)


def upsert_record(index: DraftIndex, record: DraftRecord) -> DraftIndex:
    existing = {d.article_id: d for d in index.drafts}
    existing[record.article_id] = record
    index.drafts = list(existing.values())
    return index
