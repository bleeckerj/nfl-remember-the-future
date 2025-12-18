from __future__ import annotations

from pathlib import Path
from typing import Optional

PROJECTS_DIR = Path("projects")


def normalize_project_root(project_root: Optional[Path]) -> Optional[Path]:
    """
    Interpret a user-specified --project-root value by defaulting simple names to projects/<name>.
    """
    if project_root is None:
        return None
    if project_root.is_absolute():
        return project_root
    if project_root.name in (".", ".."):
        return project_root
    parts = project_root.parts
    if parts and parts[0] == PROJECTS_DIR.name:
        return project_root
    if len(parts) == 1:
        return PROJECTS_DIR / project_root
    return project_root
