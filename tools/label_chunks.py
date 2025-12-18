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
from typing import Dict, List, Optional

from tools.project_paths import normalize_project_root

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
    "Extract structured metadata from the excerpt. Respond with JSON only.\n"
    "Schema: {\"summary\": \"...\", \"keywords\": [\"...\", \"...\"]}\n"
    "Rules for summary:\n"
    "- One sentence (fragment ok) that states the core claim/idea directly, like a headline or abstract.\n"
    "- NO attribution or framing: do not use or imply a narrator/agent such as "
    "\"the speaker\", \"the author\", \"the filmmaker\", \"the director\", \"the panel\", "
    "\"this excerpt\", \"this text\", \"in this conversation\", etc.\n"
    "- Prefer naming the concrete subject (e.g., \"Black cinema…\", \"The roundtable…\"). "
    "If no concrete subject is named, start with a verb phrase (e.g., \"Argues…\", \"Explores…\", \"Emphasizes…\").\n"
    "Rules for keywords:\n"
    "- 3–6 distinct nouns/proper nouns from the excerpt.\n"
    "- Avoid generic people-words (\"person\", \"people\", \"filmmaker\", \"speaker\") unless a proper name is unavailable.\n"
    "“summary” must be a direct declarative claim (subject–verb–object), not a report of someone’s speech. Forbidden verbs/frames: argues, suggests, says, reflects, explores, emphasizes, describes, discusses, notes, proposes. If the excerpt implies a viewpoint without naming a subject, choose a concrete subject from the excerpt (e.g., “the company”, “the group”, “home building”, “Hollywood”) and state the claim directly."
    )


    # prompt = (
    #     "You are labeling a short excerpt from a report. Respond with a JSON object only, "
    #     "for example: {\"summary\": \"…\", \"keywords\": [\"…\", \"…\"]}. "
    #     "Do not include any prose before or after the JSON. "
    #     "Provide a summary that captures the excerpt’s main idea, tension, decision, or observation in a single sentence (fragments are fine if they express the core content). "
    #     "Choose 3-6 distinct keywords that are nouns/proper nouns, highlighting people, organizations, places, technologies, or concrete concepts from the text. "
    #     "Avoid filler, vague adjectives, and direct URL values."
    #     "Never open the summary with framing phrases such as “The speaker”, “The author”, “This excerpt”, “The text”, “In this passage”, “The scholar”, “The person”, “The group”, “The interview”, “The narrator”, “The discussion”, or “In this section”. Begin immediately with the substantive idea—what happens, what question is raised, what tension exists. "
    #     "If those phrases would be needed, instead describe the event/insight directly (e.g., use “Rejecting a script that treats pain as stylistic” rather than “The speaker rejects…”)."
    # )
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


def write_labels(chunks: List[dict], out_path: Path, verbose: bool, quiet: bool = False) -> None:
    labeled = []
    start = time.time()
    total = len(chunks)
    if quiet:
        print(f"Labeling {total} chunks (heuristic)...")
    else:
        print(f"Labeling {total} chunks (heuristic)...")
    for idx, ch in enumerate(chunks, start=1):
        label = label_chunk(ch["text"])
        labeled.append({**ch, **label})
        if not quiet:
            elapsed = time.time() - start
            avg = elapsed / idx
            eta = avg * (total - idx)
            summary = label["summary"].replace("\n", " ").strip()
            keywords = ", ".join(label["keywords"])
            chunk_id = ch.get("id", f"chunk-{idx}")
            line = (
                f"[label {idx:03d}/{total:03d}] id={chunk_id} "
                f"len={len(ch.get('text', ''))} "
                f"{elapsed:.1f}s elapsed | ETA {eta:.1f}s | {summary[:120]}"
            )
            if keywords:
                line += f" | keywords: {keywords}"
            print(line)
            sys.stdout.flush()
        elif verbose and (idx % 100 == 0 or idx == total):
            elapsed = time.time() - start
            print(f"Processed {idx}/{total} chunks in {elapsed:.1f}s")
            sys.stdout.flush()
    out_path.write_text(json.dumps(labeled, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote labels to {out_path}")


def write_labels_llm(chunks: List[dict], out_path: Path, model: str, temperature: float, verbose: bool, quiet: bool = False) -> None:
    client = get_client_from_env()
    labeled = []
    start = time.time()
    total = len(chunks)
    if quiet:
        print(f"Labeling {total} chunks (llm model={model}, temp={temperature})...")
    else:
        print(f"Labeling {total} chunks (llm model={model}, temp={temperature})...")
    for idx, ch in enumerate(chunks, start=1):
        label = label_chunk_llm(client, model, ch["text"], temperature=temperature)
        labeled.append({**ch, **label})
        if not quiet:
            elapsed = time.time() - start
            avg = elapsed / idx
            eta = avg * (total - idx)
            summary = label["summary"].replace("\n", " ").strip()
            keywords = ", ".join(label["keywords"])
            chunk_id = ch.get("id", f"chunk-{idx}")
            line = (
                f"[label {idx:03d}/{total:03d}] id={chunk_id} "
                f"len={len(ch.get('text', ''))} "
                f"{elapsed:.1f}s elapsed | ETA {eta:.1f}s | {summary[:120]}"
            )
            if keywords:
                line += f" | keywords: {keywords}"
            print(line)
            sys.stdout.flush()
        elif verbose and (idx % 25 == 0 or idx == total):
            elapsed = time.time() - start
            print(f"Processed {idx}/{total} chunks in {elapsed:.1f}s")
            sys.stdout.flush()
    out_path.write_text(json.dumps(labeled, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote labeled chunks to {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Label chunk JSON with summaries and keywords.")
    parser.add_argument("--project-root", type=Path, help="Project workspace root for inputs/outputs")
    parser.add_argument("--chunks", type=Path, required=True, help="Input chunk JSON from tools.chunk_report")
    parser.add_argument("--out", type=Path, required=True, help="Output labeled JSON")
    llm_group = parser.add_mutually_exclusive_group()
    llm_group.add_argument("--use-llm", dest="use_llm", action="store_true", help="Use OpenAI-compatible LLM for summaries/keywords (default)")
    llm_group.add_argument("--no-llm", dest="use_llm", action="store_false", help="Do not call an LLM; use heuristic labeling")
    parser.set_defaults(use_llm=True)
    parser.add_argument("--llm-model", type=str, default=None, help="Override model for LLM labeling")
    parser.add_argument("--llm-temperature", type=float, default=0.0, help="Temperature for LLM labeling")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of chunks to label (debug)")
    parser.add_argument("--verbose", action="store_true", help="Print periodic progress (quiet mode)")
    parser.add_argument("--quiet", action="store_true", help="Reduce per-chunk output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks_path = resolve_path(args.chunks, args.project_root)
    out_path = resolve_path(args.out, args.project_root)
    chunks = load_chunks(chunks_path)
    if args.limit:
        chunks = chunks[: args.limit]
    if args.use_llm:
        model = resolve_model(args.llm_model)
        write_labels_llm(
            chunks,
            out_path,
            model=model,
            temperature=args.llm_temperature,
            verbose=args.verbose,
            quiet=args.quiet,
        )
    else:
        write_labels(chunks, out_path, verbose=args.verbose, quiet=args.quiet)


def resolve_path(path: Optional[Path], project_root: Optional[Path]) -> Optional[Path]:
    if path is None:
        return None
    normalized_root = normalize_project_root(project_root)
    if normalized_root and not path.is_absolute():
        return normalized_root / path
    return path


if __name__ == "__main__":
    main()
