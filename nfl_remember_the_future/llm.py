from __future__ import annotations

import os

import typer
from dotenv import load_dotenv
from openai import OpenAI


def get_client_from_env() -> OpenAI:
    """
    Uses .env (via python-dotenv) and environment variables.

    Required:
      OPENAI_API_KEY

    Optional:
      OPENAI_BASE_URL (e.g. https://api.openai.com/v1 or a compatible gateway URL)
    """
    load_dotenv()
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise typer.BadParameter("Missing OPENAI_API_KEY. Put it in .env or export it.")

    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or None
    return OpenAI(api_key=api_key, base_url=base_url)


def resolve_model(model: str | None) -> str:
    if model:
        return model
    return (os.getenv("OPENAI_MODEL") or "").strip() or "gpt-4.1"


def draft_one(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_completion_tokens: int,
) -> tuple[str, Optional[int]]:
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = (resp.choices[0].message.content or "").strip()
    usage_tokens = None
    try:
        usage_tokens = getattr(resp, "usage", None).completion_tokens  # type: ignore[attr-defined]
    except Exception:
        usage_tokens = None
    return content, usage_tokens


def generate_image_prompt(
    client: OpenAI,
    model: str,
    article_title: str,
    article_format: str,
    anchors: list[str],
    writing_directions: list[str],
    style_context: str,
    temperature: float = 0.3,
    max_completion_tokens: int = 120,
) -> tuple[str, Optional[int]]:
    system = (
        "You generate concise text-to-image prompts for editorial illustration. "
        "The prompt should characterize a specific visual that complements the article title, format, anchors. If the article is technical or data-driven, consider suggesting an infographic, diagram, or data visualization."
        "The images are meant to complement the article in a journalistic fashion, so less cinematic and more editorial in visual style and tone. Consider things like portrait photographs if the article is highlighting an individual or team; consider production-style photos if the article is about an event or activity; consider infographics or diagrams if the article is technical or data-driven."
        "The photograph should avoid cues that the image is staged or artificially generated overly dramatic, too stylized or cinematic. Instead, aim for a natural, candid, journalistic style that feels authentic and real."
        "Return one short prompt (2-4 sentences) describing a compelling, specific visual. "
        "Match the tone and format; avoid generic 'photo of X' phrasing; suggest illustration/diagram/infographic/scene if fitting. "
        "No line breaks, no markdown."
    )
    user = f"""ARTICLE
Title: {article_title}
Format: {article_format}
Anchors: {anchors}
Directions: {writing_directions}
Style context: {style_context[:500]}
Output: one text-to-image prompt."""
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = (resp.choices[0].message.content or "").strip()
    usage_tokens = None
    try:
        usage_tokens = getattr(resp, "usage", None).completion_tokens  # type: ignore[attr-defined]
    except Exception:
        usage_tokens = None
    return content, usage_tokens
