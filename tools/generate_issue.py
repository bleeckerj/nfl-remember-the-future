"""
LLM-assisted generator: create a starter issue.json from a report.

Usage:
  python -m tools.generate_issue --project my-project --input /path/to/report.txt --artifact magazine
"""
from __future__ import annotations

import argparse
import json
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

from nfl_remember_the_future.llm import draft_one, get_client_from_env, resolve_model
from tools.html_to_md import html_to_md

ARTIFACT_DEFAULTS = {
    "magazine": {"count": 10, "voice": "The New Yorker / The Atlantic"},
    "newspaper": {"count": 10, "voice": "The New York Times"},
    "catalog": {"count": 10, "voice": "IKEA / Uline / Amazon"},
}


def resolve_project_root(project: str) -> Path:
    return Path("projects") / project


def resolve_path(path: Path, project_root: Path) -> Path:
    if path.is_absolute():
        return path
    return project_root / path


def load_prompt_fragment(project_root: Path, filename: str) -> str:
    project_prompts = project_root / "prompts"
    candidate = project_prompts / filename
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    fallback = Path("prompts") / filename
    if fallback.exists():
        return fallback.read_text(encoding="utf-8")
    return ""


def load_texts(input_paths: list[Path], project_root: Path, quiet: bool) -> str:
    parts: list[str] = []
    for p in input_paths:
        if p.suffix.lower() in {".html", ".htm"}:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".md",
                dir=project_root,
                delete=False,
            ) as tmp:
                tmp_path = Path(tmp.name)
            html_to_md(p, tmp_path, strip_data=True, gibberish_threshold=200, quiet=quiet)
            text = tmp_path.read_text(encoding="utf-8")
            tmp_path.unlink(missing_ok=True)
        else:
            text = p.read_text(encoding="utf-8")
        if not text.strip():
            raise SystemExit(f"Missing text in input file {p}; provide a non-empty report.")
        parts.append(f"---- SOURCE: {p.name} ----\n{text.strip()}\n")
    return "\n\n".join(parts)


def load_labels_if_present(project_root: Path, labels_path: Path) -> List[Dict[str, Any]]:
    if not labels_path.exists():
        return []
    return json.loads(labels_path.read_text(encoding="utf-8"))


def summarize_labels(labels: List[Dict[str, Any]], limit: int = 40) -> str:
    lines = []
    for ch in labels[:limit]:
        summary = (ch.get("summary") or "").strip().replace("\n", " ")
        keywords = ", ".join(ch.get("keywords", [])[:6])
        line = f"[{ch.get('id', '')}] {summary}"
        if keywords:
            line += f" | keywords: {keywords}"
        lines.append(line.strip())
    return "\n".join(lines).strip()


def summarize_existing_issue(issue_path: Path, limit: int = 6) -> str:
    if not issue_path.exists():
        return ""
    try:
        issue = json.loads(issue_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    articles = issue.get("articles", [])
    if not articles:
        return ""
    lines = []
    for art in articles[:limit]:
        anchors = art.get("report_anchor") or art.get("ai2027_anchor") or []
        anchor_preview = ", ".join(anchors[:4]) if anchors else "no anchors"
        lines.append(
            f"- [{art.get('id')}] {art.get('title', 'untitled')} | {art.get('format', '')} | anchors: {anchor_preview}"
        )
    if len(articles) > limit:
        lines.append(f"- ...and {len(articles) - limit} more articles already proposed")
    lines.append("Avoid repeating the anchors/topics listed above; cover a different dimension of the report.")
    return "Existing proposals:\n" + "\n".join(lines)


def compress_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2].strip()
    tail = text[-max_chars // 2 :].strip()
    return f"{head}\n\n[... truncated ...]\n\n{tail}"


def parse_json_response(content: str) -> Dict[str, Any]:
    raw = content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json\n", "", 1).strip()
    if raw.startswith("{") and raw.endswith("}"):
        return json.loads(raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw[start : end + 1])
    raise ValueError("Model response did not include a JSON object.")


def repair_json_with_llm(client, model: str, content: str, temperature: float) -> str:
    system = (
        "You repair invalid JSON. "
        "Return ONLY valid JSON, no code fences, no commentary."
    )
    user = f"Fix this JSON. Preserve all fields and values where possible.\n\n{content}"
    repaired, _ = draft_one(
        client=client,
        model=model,
        system_prompt=system,
        user_prompt=user,
        temperature=temperature,
        max_completion_tokens=2600,
    )
    return repaired


def build_system_prompt(artifact: str, voice: str, project_base: str | None = None) -> str:
    default = (
        "You are an editorial planner generating a complete issue spec as JSON. "
        "Return ONLY valid JSON that matches this schema:\n"
        "{issue:{title,date,status,source}, style_anchor:{description,content}, articles:["
        "{id:int,title,format,lede,byline,report_anchor:[str],writing_directions:[str],"
        "prompt_example?:str}...]}\n"
        "Include style_anchor with a short description of the publication voice and a brief "
        "content note about the report (2-4 sentences). "
        "Use report_anchor as the list of grounded anchors (3-6 bullets). "
        "writing_directions should be 3-6 concrete editorial instructions. "
        "No time horizon. Avoid specific years unless present in the source. "
        f"Artifact type: {artifact}. Voice reference: {voice}. "
        "Allow extrapolation beyond the report while staying plausible."
    )
    if project_base and project_base.strip():
        return project_base.strip() + "\n\n" + default
    return default


def build_user_prompt(
    artifact: str,
    count: int,
    voice: str,
    report_summary: str,
    report_excerpt: str,
    source_label: str,
    existing_summary: str,
) -> str:
    sections = []
    if artifact == "magazine":
        sections = [
            "features / longform",
            "reported essay",
            "profile or interview",
            "criticism / arts",
            "op-ed or viewpoint",
            "short front-of-book items",
            "ads or classifieds (if fitting)",
        ]
    elif artifact == "newspaper":
        sections = [
            "hard news",
            "analysis",
            "business / economy",
            "policy / governance",
            "science / tech",
            "culture",
            "opinion",
            "briefs / metro",
        ]
    elif artifact == "catalog":
        sections = [
            "featured products",
            "category listings",
            "bundle kits",
            "service plans or warranties",
            "accessories",
        ]

    section_text = ", ".join(sections) if sections else "mixed sections"
    existing_summary_block = ""
    if existing_summary:
        existing_summary_block = (
            "\n\nEXISTING ISSUE PROPOSALS:\n" + existing_summary.strip() + "\n"
        )

    return (
        f"Generate an issue with {count} items. "
        f"Sections to cover: {section_text}. "
        f"Use voice like: {voice}. "
        "For catalog items, set prompt_example to examples_ad and use format values like "
        "'Advertisement' or 'Catalog listing'. For op-eds, set prompt_example to examples_oped. "
        "Set issue.status to 'draft'. Set issue.source to the provided source label. "
        "If date is unknown, use 'YYYY-MM-DD'. "
        "Use sequential integer ids starting at 1. "
        "\n\nREPORT SUMMARY (if available):\n"
        f"{report_summary}\n\n"
        "REPORT EXCERPT:\n"
        f"{report_excerpt}"
        f"{existing_summary_block}"
        "Output JSON only."
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a starter issue.json from a report.")
    p.add_argument("--project", required=True, help="Project name under projects/")
    p.add_argument("--input", required=True, type=Path, nargs="+", help="Source report file(s) (txt/md/html)")
    p.add_argument("--artifact", choices=["magazine", "newspaper", "catalog"], required=True)
    p.add_argument("--issue-out", type=Path, default=Path("issue.json"), help="Output issue JSON in project")
    p.add_argument("--labels", type=Path, default=Path("report_chunk_labels.json"), help="Chunk labels to summarize")
    p.add_argument("--num-items", type=int, default=None, help="Override default number of items")
    p.add_argument("--temperature", type=float, default=0.6, help="Sampling temperature")
    p.add_argument("--max-completion-tokens", type=int, default=2600, help="Max completion tokens")
    p.add_argument("--model", type=str, default=None, help="Override model")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing issue.json")
    p.add_argument("--append", action="store_true", help="Append generated articles to an existing issue.json (auto-increment ids)")
    p.add_argument("--no-repair", action="store_true", help="Disable JSON repair on parse failure")
    p.add_argument("--no-print-prompts", action="store_true", help="Do not print system/user prompts")
    p.add_argument("--no-print-response", action="store_true", help="Do not print model response")
    p.add_argument("--quiet", action="store_true", help="Minimal logging")
    return p.parse_args()


def generate_issue_file(
    project_root: Path,
    input_path: Path,
    artifact: str,
    issue_out_path: Path,
    labels_path: Path,
    num_items: int | None,
    temperature: float,
    max_completion_tokens: int,
    model_override: str | None,
    overwrite: bool,
    append: bool,
    quiet: bool,
    no_repair: bool,
    no_print_prompts: bool,
    no_print_response: bool,
) -> Path:
    project_root.mkdir(parents=True, exist_ok=True)

    input_paths = [p.expanduser().resolve() for p in input_path]
    if issue_out_path.exists() and not (overwrite or append):
        raise SystemExit(f"Refusing to overwrite {issue_out_path}. Use --overwrite or --append.")

    defaults = ARTIFACT_DEFAULTS[artifact]
    count = num_items or defaults["count"]
    voice = defaults["voice"]

    if not quiet:
        print(f"[generate_issue] project={project_root}")
        print(f"[generate_issue] inputs={[str(p) for p in input_paths]}")
        print(f"[generate_issue] artifact={artifact} count={count} voice={voice}")
    labels = load_labels_if_present(project_root, labels_path)
    report_summary = summarize_labels(labels) if labels else ""

    if not quiet:
        if labels:
            print(f"[generate_issue] labels={labels_path} chunks={len(labels)}")
        else:
            print("[generate_issue] labels=none")

    report_text = load_texts(input_paths, project_root, quiet=quiet)
    report_excerpt = compress_text(report_text, max_chars=12000)

    system_base = load_prompt_fragment(project_root, "system_base.md")
    system = build_system_prompt(artifact, voice, system_base)
    source_label = ", ".join(p.name for p in input_paths)
    existing_summary = summarize_existing_issue(issue_out_path)
    user = build_user_prompt(
        artifact,
        count,
        voice,
        report_summary,
        report_excerpt,
        source_label,
        existing_summary,
    )

    client = get_client_from_env()
    model = resolve_model(model_override)
    if not quiet:
        print(f"[generate_issue] model={model} temp={temperature} max_tokens={max_completion_tokens}")
        print(f"[generate_issue] report_chars={len(report_text)} excerpt_chars={len(report_excerpt)}")
        if not no_print_prompts:
            system_path = issue_out_path.with_suffix(".system_prompt.txt")
            user_path = issue_out_path.with_suffix(".user_prompt.txt")
            system_path.write_text(system, encoding="utf-8")
            user_path.write_text(user, encoding="utf-8")
            print(f"[generate_issue] wrote_system_prompt={system_path}")
            print(f"[generate_issue] wrote_user_prompt={user_path}")
        print("[generate_issue] calling model...", flush=True)

    result: dict[str, Any] = {"content": "", "error": None}

    def run_call() -> None:
        try:
            content, _ = draft_one(
                client=client,
                model=model,
                system_prompt=system,
                user_prompt=user,
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
            )
            result["content"] = content
        except Exception as exc:  # pragma: no cover - surface runtime failures
            result["error"] = exc

    worker = threading.Thread(target=run_call, daemon=True)
    worker.start()

    if not quiet:
        start = time.time()
        spinner = ["|", "/", "-", "\\"]
        tick = 0
        while worker.is_alive():
            elapsed = time.time() - start
            print(
                f"[generate_issue] waiting {spinner[tick % len(spinner)]} {elapsed:.1f}s",
                end="\r",
                flush=True,
            )
            tick += 1
            time.sleep(0.8)
        print(f"[generate_issue] waiting ✓ {time.time() - start:.1f}s", flush=True)

    worker.join()
    if result["error"] is not None:
        raise result["error"]
    content = result["content"]

    raw_path = issue_out_path.with_name(f"{issue_out_path.stem}.raw.txt")
    raw_path.write_text(content, encoding="utf-8")
    if not quiet and not no_print_response:
        print(f"[generate_issue] raw_response_chars={len(content)} saved_raw={raw_path}")
        print("[generate_issue] raw_response_begin")
        print(content)
        print("[generate_issue] raw_response_end")
    try:
        issue = parse_json_response(content)
    except Exception as exc:
        if no_repair:
            raise SystemExit(
                f"Model output was not valid JSON. Raw output saved to {raw_path}."
            ) from exc
        if not quiet:
            print(f"[generate_issue] invalid_json saved_raw={raw_path}")
            print("[generate_issue] repairing JSON...", flush=True)
        repaired = repair_json_with_llm(client, model, content, temperature=0.0)
        repaired_path = issue_out_path.with_name(f"{issue_out_path.stem}.repaired.txt")
        repaired_path.write_text(repaired, encoding="utf-8")
        if not quiet and not no_print_response:
            print(f"[generate_issue] repaired_response_chars={len(repaired)} saved_repaired={repaired_path}")
            print("[generate_issue] repaired_response_begin")
            print(repaired)
            print("[generate_issue] repaired_response_end")
        try:
            issue = parse_json_response(repaired)
        except Exception as exc2:
            raise SystemExit(
                "Repaired output was still invalid JSON. "
                f"Raw output saved to {raw_path}, repaired output saved to {repaired_path}."
            ) from exc2
    # Append mode: merge articles into existing issue.json with auto-incremented ids.
    if append and issue_out_path.exists():
        existing = json.loads(issue_out_path.read_text(encoding="utf-8"))
        existing_articles = existing.get("articles", [])
        max_id = max((int(a.get("id", 0)) for a in existing_articles), default=0)
        new_articles = []
        for idx, art in enumerate(issue.get("articles", []), start=1):
            art = dict(art)
            art["id"] = max_id + idx
            new_articles.append(art)
        merged = existing
        merged["articles"] = existing_articles + new_articles
        if not merged.get("style_anchor") and issue.get("style_anchor"):
            merged["style_anchor"] = issue["style_anchor"]
        issue = merged

    issue_out_path.write_text(json.dumps(issue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not quiet:
        print(f"[generate_issue] wrote_issue={issue_out_path}")
    return issue_out_path


def main() -> None:
    args = parse_args()
    project_root = resolve_project_root(args.project)
    issue_out_path = resolve_path(args.issue_out, project_root)
    labels_path = resolve_path(args.labels, project_root)
    generate_issue_file(
        project_root=project_root,
        input_path=args.input,
        artifact=args.artifact,
        issue_out_path=issue_out_path,
        labels_path=labels_path,
        num_items=args.num_items,
        temperature=args.temperature,
        max_completion_tokens=args.max_completion_tokens,
        model_override=args.model,
        overwrite=args.overwrite,
        append=args.append,
        quiet=args.quiet,
        no_repair=args.no_repair,
        no_print_prompts=args.no_print_prompts,
        no_print_response=args.no_print_response,
    )


if __name__ == "__main__":
    main()
