from __future__ import annotations

from typing import Any, Dict, List

from .models import ArticleSpec


def pick_examples(prompts: Dict[str, str], format_name: str, prompt_example: str | None = None) -> str:
    if prompt_example:
        return prompts.get(prompt_example, "")

    f = (format_name or "").lower()
    if "op-ed" in f or "opinion" in f or "guest" in f:
        return prompts.get("examples_oped", "")
    if "advert" in f or f.strip() == "advertisement":
        return prompts.get("examples_ad", "")
    return prompts.get("examples_longform", "")


def build_system_prompt(
    prompts: Dict[str, str],
    article: ArticleSpec,
    style_anchor_text: str,
    report_context: str,
) -> str:
    base = prompts.get("system_base", "").strip()

    anchor_block = ""
    if style_anchor_text.strip():
        anchor_block = (
            "\n\nGOLD-STANDARD STYLE ANCHOR (calibration reference):\n"
            + style_anchor_text.strip()
        )

    report_block = ""
    if report_context.strip():
        report_block = "\n\nREPORT CONTEXT (foundation for this issue):\n" + report_context.strip()

    examples = pick_examples(prompts, article.format, article.prompt_example)
    examples_block = f"\n\n{examples.strip()}" if examples.strip() else ""

    return base + anchor_block + report_block + examples_block


def build_user_prompt(article: ArticleSpec, issue_meta: Dict[str, Any]) -> str:
    anchors = "\n".join([f"- {a}" for a in article.report_anchor])
    directions = "\n".join([f"- {d}" for d in article.writing_directions])
    references_block = ""
    if article.report_refs:
        references = "\n".join([f"- {r}" for r in article.report_refs])
        references_block = f"\n\nREPORT REFERENCES (grounding)\n{references}"
    ref_details_block = ""
    if getattr(article, "report_ref_details", []):
        details = "\n".join(
            [f"- {d.get('id')}: {d.get('summary', '')} (keywords: {', '.join(d.get('keywords', []))})" for d in article.report_ref_details]
        )
        ref_details_block = f"\n\nREPORT REFERENCES DETAILS\n{details}"

    return f"""ASSIGNMENT
You are drafting a piece for a newspaper/magazine issue titled: "{issue_meta.get('title')}" dated {issue_meta.get('date')}.
The world and implications are derived from the source report. You must stay within the constraints implied by the anchors.

ARTICLE METADATA
- ID: {article.id}
- Format: {article.format}
- Title: {article.title}
- Byline: {article.byline}
- Provided lede (keep angle, you may tighten): {article.lede}

REPORT ANCHORS (must be directly reflected)
{anchors}

WRITING DIRECTIONS (follow as structure)
{directions}
{references_block}
{ref_details_block}

OUTPUT REQUIREMENTS
- Write the complete piece in Markdown.
- Do not include commentary, outlines, or explanations.
"""
