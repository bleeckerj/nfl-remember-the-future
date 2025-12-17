"""
Utility: generate labels for chunks to speed up manual grounding.

Usage (heuristic):
    python -m tools.label_chunks --chunks report_chunks.json --out report_chunk_labels.json

Usage (LLM-assisted summaries/keywords):
    python -m tools.label_chunks --chunks report_chunks.json --out report_chunk_labels.json --use-llm --llm-model gpt-4.1-mini

Heuristic uses first sentence + filtered keywords.
LLM path asks the model for a 1-sentence summary + 3–6 specific keywords.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List

from nfl_remember_the_future.llm import get_client_from_env, resolve_model

STOPWORDS = {
    "https", "http", "www", "com", "org", "net",
    "the", "and", "that", "with", "from", "this", "there", "their", "some",
    "they", "were", "have", "been", "could", "would", "should", "into", "more",
    "still", "over", "after", "before", "about", "these", "those", "than",
    "because", "while", "which", "also", "when", "what", "where", "who",
    "will", "just", "very", "even", "every", "other", "both", "most", "many",
    "through", "without", "within", "between", "among", "under", "upon", "such",
}


def load_chunks(path: Path) -> List[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def first_sentence(text: str, limit: int = 160) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    candidate = parts[0] if parts else text.strip()
    return candidate[:limit].strip()


def keyword_candidates(text: str, k: int = 5) -> List[str]:
    tokens = [
        t for t in re.findall(r"[A-Za-z]{4,}", text.lower())
        if t not in STOPWORDS
    ]
    common = [w for w, _ in Counter(tokens).most_common(k)]
    return common


def label_chunk(text: str) -> dict:
    return {
        "summary": first_sentence(text),
        "keywords": keyword_candidates(text),
    }


def label_chunk_llm(client, model: str, text: str, temperature: float = 0.0) -> dict:
    prompt = (
        "You are labeling a snippet from an AI report. "
        "Return a JSON object with fields: summary (1 sentence) and keywords (3-6 specific nouns or proper nouns). "
        "Avoid stopwords and generic terms; include concrete entities (people, orgs, places, technologies). "
        "Do not include URLs."
    )
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=120,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text[:1200]},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
        summary = data.get("summary") or first_sentence(text)
        keywords = data.get("keywords") or keyword_candidates(text)
    except Exception:
        summary = first_sentence(text)
        keywords = keyword_candidates(text)
    return {"summary": summary.strip(), "keywords": keywords}


def write_labels(chunks: List[dict], out_path: Path, verbose: bool) -> None:
    labeled = []
    start = time.time()
    total = len(chunks)
    print(f"🔎 Heuristic labeling {total} chunks...")
    for idx, ch in enumerate(chunks, start=1):
        label = label_chunk(ch["text"])
        labeled.append({**ch, **label})
        if verbose:
            print(
                f"\033[96m[{idx}/{total}] summary: {label['summary'][:120]} | keywords: {', '.join(label['keywords'])}\033[0m"
            )
            sys.stdout.flush()
        if idx % 100 == 0 or idx == total:
            elapsed = time.time() - start
            print(f"\033[94m• processed {idx}/{total} chunks in {elapsed:.1f}s\033[0m")
            sys.stdout.flush()
    out_path.write_text(json.dumps(labeled, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✅ Wrote labels to {out_path}")


def write_labels_llm(chunks: List[dict], out_path: Path, model: str, temperature: float, verbose: bool) -> None:
    client = get_client_from_env()
    labeled = []
    start = time.time()
    total = len(chunks)
    print(f"🤖 LLM labeling {total} chunks with model={model} (temp={temperature})...")
    for idx, ch in enumerate(chunks, start=1):
        label = label_chunk_llm(client, model, ch["text"], temperature=temperature)
        labeled.append({**ch, **label})
        if verbose:
            print(
                f"\033[92m[{idx}/{total}] summary: {label['summary'][:120]} | keywords: {', '.join(label['keywords'])}\033[0m"
            )
            sys.stdout.flush()
        if idx % 25 == 0 or idx == total:
            elapsed = time.time() - start
            print(f"\033[92m• processed {idx}/{total} chunks in {elapsed:.1f}s\033[0m")
            sys.stdout.flush()
    out_path.write_text(json.dumps(labeled, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✅ Wrote LLM-labeled chunks to {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Label chunk JSON with summaries and keywords.")
    parser.add_argument("--chunks", type=Path, required=True, help="Input chunk JSON from tools.chunk_report")
    parser.add_argument("--out", type=Path, required=True, help="Output labeled JSON")
    parser.add_argument("--use-llm", action="store_true", dest="use_llm", help="Use OpenAI-compatible LLM for summaries/keywords")
    parser.add_argument("--llm-model", type=str, default=None, help="Override model for LLM labeling")
    parser.add_argument("--llm-temperature", type=float, default=0.0, help="Temperature for LLM labeling")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of chunks to label (debug)")
    parser.add_argument("--verbose", action="store_true", help="Print per-chunk summaries/keywords")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = load_chunks(args.chunks)
    if args.limit:
        chunks = chunks[: args.limit]
    if args.use_llm:
        model = resolve_model(args.llm_model)
        write_labels_llm(chunks, args.out, model=model, temperature=args.llm_temperature, verbose=args.verbose)
    else:
        write_labels(chunks, args.out, verbose=args.verbose)


if __name__ == "__main__":
    main()
