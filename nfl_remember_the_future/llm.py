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
) -> str:
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()
