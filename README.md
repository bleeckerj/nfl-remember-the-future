# nfl-remember-the-future 

## Issue JSON → Drafts

This project ingests an **issue JSON** (e.g. `intelligence_transition_full_issue.json`), validates it against a **JSON Schema**, and drafts articles via an **OpenAI-API-compatible endpoint** (OpenAI, or a compatible gateway like LiteLLM/OpenRouter/self-hosted proxies).

The purpose is an experiment in **data-driven long-form article drafting** guided by structured metadata:
- title, byline, lede
- anchors to cover
- writing directions
- report references for grounding

This project is **not** meant to be an exploration in replacing true journalistic craft with AI. My father was a journalist and writer; I've written books and articles as a professional academic and researcher; I respect the integrity of the craft. With this project I am experimenting with the possibility of near futures where AI just ends up assisting human writers in more structured ways and, not inevitably, where AI helps draft first versions of articles that human writers then refine, edit, and polish. Or maybe even does articles.

One of the Design Fictions that appears in the first issue of [Applied Intelligence](https://nearfuturelaboratory.com/library/2024/12/applied-intelligence-issue-001/) I created late 2026 was the implication that agents of some description reasoned that they should write news articles that they also decided they would print and distribute. There was no explanation of how that happened in the Design Fiction — some wondered if the newspapers were ways for the AIs to communicate with one another in an unexpected backchannel, the theory being that people reading the articles (cyborgs — nothing more than humans wearing active glasses that had cameras in them) were providing the ingestion surface through which the messaging in the printed newspaper could be read. (The undergirding speculation/theory being that the usual internet channels itself were monitored; some thought that the articles' text was embedded with code, others noticed missprints and smudges in the newsprint that could be possibly QR-code like glyphs containing messages, etc.).

In any case, all of that is to say that this is an experiment rather than an application prototype.

By default the issue JSON stays pristine. Drafts are written to Markdown files plus a `drafts/index.json` index (article ID → draft path/metadata). An optional flag lets you emit an annotated copy of the issue JSON without touching the input.

This is designed as the drafting **engine** for a future **non-chat writing assistant** UI (dual-pane: text editor + editorial control surface).

---

## What this does

**Inputs**
- `issue.json` — structured issue spec with article metadata, anchors, and writing directions
- `issue.schema.json` — JSON Schema for validation
- `prompts/` — system instructions + optional format-specific style examples
- `prompts/report_context.md` — optional report excerpts/summary injected into the system prompt
- `.env` — secrets/config (API key, base URL, default model)

**Outputs**
- Markdown drafts in `drafts/{id}_{slug}.md`
- Draft index in `drafts/index.json` (article ID, title, format, model, timestamp, path)
- Optional: annotated copy of the issue JSON if you pass `--write-annotated-json`

---

## Repo Structure

```
nfl_remember_the_future/
  drafter.py
  requirements.txt
  .env.example
  .gitignore
  prompts/
    system_base.md
    examples_longform.md
    examples_oped.md
    examples_ad.md
  drafts/               # generated
  projects/             # optional per-project workspaces
  tests/
    test_drafter.py
```

### Project workspaces (optional but recommended)
If you want to keep each backing project fully isolated, create a workspace under `projects/`:
```
projects/my-project/
  issue.json
  issue.grounded.json
  report.md
  report_chunks.json
  report_chunk_labels.json
  prompts/            # optional overrides
  drafts/             # per-project outputs
```

When you pass `--project-root projects/my-project`, all relative paths are resolved within that folder.
`prompts/` is optional per-project; if missing, the global `prompts/` directory is used.

---

## Setup (Python)

### 1) Create a virtualenv
```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

If you prefer the module form:
```bash
python -m nfl_remember_the_future.cli --help
```

---

## Secrets + config via .env (required)

### 1) Create `.env`
Copy `.env.example` → `.env` and fill in values:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1
```

**Notes**
- `.env` is ignored by git (`.gitignore` includes it).
- If you use a compatible gateway, set `OPENAI_BASE_URL` accordingly.

---

## Prompt system (how you steer quality)

### prompts/system_base.md
This is the “editorial brain.” Put your extensive system instructions here:
- general readership
- high editorial caliber (NYT/Atlantic/New Yorker)
- no hype, no anthropomorphism
- do not invent beyond anchors
- scene-based reporting and restraint
- Markdown-only output, no commentary

### prompts/examples_*.md
Optional style calibration snippets:
- `examples_longform.md` — long-form reporting / explainers
- `examples_oped.md` — opinion voice
- `examples_ad.md` — ads / notices

Prompt example selection:
- Default: inferred from `format` (`op-ed`/`opinion`/`guest` → `examples_oped`, `advert*` → `examples_ad`, else `examples_longform`)
- Override per-article: set `"prompt_example": "examples_oped"` (or other stem) in the issue JSON
- Issue-wide context: put curated report excerpts in `style_anchor.content` (issue JSON) or `prompts/report_context.md`
- Article grounding: add `"report_refs": ["Section 2.1 — Alignment warning", ...]` to each article; these show up in the user prompt
- Anchors field: use `report_anchor` in issue JSON (legacy `ai2027_anchor` is still supported).

---

## Running the drafter

Note that the first example of this I ran was to use a futures report as a basis for drafting a magazine that contained articles based on the report. The report was chunked and indexed, and relevant chunks were attached to each article as grounding references.
If you want the simplest path, prefer the one-command `tools.publish_issue` flow below.

The reason I did this is I wanted the articles to be based on real data from the report rather than hallucinated or made-up data. This is an important step in making AI-assisted writing more factually grounded, or so I am hypothesizing. 

Each article could index directly back to an element in the report, and the relevant chunks of the report were pulled into the prompt to provide context. Then in the output of the draft, those indices (chunk number, and some other context free text) were included in the frontmatter so that the provenance of the article could be traced back to the report, evaluated for its faithfulness to the report, etc.

If you are using project workspaces, add `--project-root projects/<name>` (or `--project <name>` where supported) and keep paths relative to that folder. If `projects/<name>/prompts/` exists, it overrides the global `prompts/`.

### Draft one article by ID
```bash
python drafter.py draft   --issue-json /path/to/intelligence_transition_full_issue.json   --schema-json /path/to/issue.schema.json   --prompt-dir prompts   --article-id 7
```

### Draft all articles
```bash
python drafter.py draft   --issue-json /path/to/intelligence_transition_full_issue.json   --schema-json /path/to/issue.schema.json   --prompt-dir prompts   --article-id all
```

Project-root variant:
```bash
python drafter.py draft   --project-root projects/my-project   --issue-json issue.grounded.json   --schema-json ../issue.schema.json   --article-id all
```
Project shortcut:
```bash
python drafter.py draft   --project my-project   --issue-json issue.grounded.json   --schema-json ../issue.schema.json   --article-id all
```

### Overwrite an existing draft
```bash
python drafter.py draft   --issue-json /path/to/intelligence_transition_full_issue.json   --schema-json /path/to/issue.schema.json   --prompt-dir prompts   --article-id 7   --overwrite-existing
```

### Write an annotated copy of the issue JSON (optional)
```bash
python drafter.py draft \
  --issue-json intelligence_transition_full_issue.json \
  --schema-json issue.schema.json \
  --write-annotated-json \
  --out-json drafts/intelligence_transition_full_issue.annotated.json
```

### Dry run without hitting the API (good for smoke tests)
```bash
python drafter.py draft \
  --issue-json intelligence_transition_full_issue.json \
  --schema-json issue.schema.json \
  --prompt-dir prompts \
  --article-id 1 \
  --dry-run \
  --dry-run-text "[DRY RUN] Placeholder draft content."
```

### Convert HTML context/report to Markdown (helper)
```bash
python -m tools.html_to_md --html "issue.html" --out report.md
# Copy the best 2–4 paragraphs into prompts/report_context.md or style_anchor.content
```

### Chunk the context/report and build an index (helper)
```bash
python -m tools.chunk_report --md report.md --out report_chunks.json --out-md report_chunks.md --max-chars 1200 --overlap 200
# Skim report_chunks.md or report_chunks.json for chunk ids; use them in article `report_refs`
```

### Label chunks (LLM-assisted, default; `--no-llm` for heuristics)
```bash
python -m tools.label_chunks --chunks report_chunks.json --out report_chunk_labels.json --llm-model gpt-4.1-mini --llm-temperature 0
# Open report_chunk_labels.json for summaries/keywords per chunk
```
## End-to-end processing order

1) **Convert HTML → Markdown** (one-time): `python -m tools.html_to_md --html "AI 2027.html" --out report.md`
2) **Chunk the report**: `python -m tools.chunk_report --md report.md --out report_chunks.json --out-md report_chunks.md --max-chars 1200 --overlap 200`
3) **Label chunks** (LLM-assisted summary/keywords are the default):  
   - Default/LLM: `python -m tools.label_chunks --chunks report_chunks.json --out report_chunk_labels.json --llm-model gpt-4.1-mini --llm-temperature 0`  
   - Heuristic fallback: add `--no-llm` to skip the LLM and run the heuristic labeller
4) **Auto-ground articles** (attach chunk ids/details + build context):  
   `python -m tools.auto_ground --issue intelligence_transition_full_issue.json --chunks report_chunk_labels.json --out-issue intelligence_transition_full_issue.grounded.json --report-context-out prompts/report_context.md --refs-per-article 2 --context-chunks 2 --include-ref-details`
5) **Draft** (reads grounded issue, writes MD with frontmatter):  
   `python -m nfl_remember_the_future.cli --issue-json intelligence_transition_full_issue.grounded.json --prompt-dir prompts --article-id all --overwrite-existing`  
   The drafter now assumes `issue.schema.json` lives in the project root; pass `--schema-json` only if you need a different schema location.

### One-command corpus prep (project workflow)
This wrapper runs steps 2–4, and will also run step 1 if the input file is HTML. Outputs are always written to `projects/<project>/`.
You still need an `issue.json` (your editorial plan) in that project folder; use `--init-issue` to scaffold one.
```bash
python -m tools.prepare_corpus \
  --project my-project \
  --input /path/to/report.html \
  --refs-per-article 2 \
  --context-chunks 2 \
  --include-ref-details
```
# LLM labeling is enabled by default; pass `--no-llm` if you want the heuristic instead.
This writes:
- `projects/my-project/report.md`
- `projects/my-project/report_chunks.json`
- `projects/my-project/report_chunk_labels.json`
- `projects/my-project/issue.grounded.json`
- `projects/my-project/prompts/report_context.md`

### LLM-assisted issue.json generator
Generates a starter `issue.json` from a report. Defaults: magazine=20 items, newspaper=20 items, catalog=30 items.
```bash
python -m tools.generate_issue \
  --project my-project \
  --input /path/to/report.txt /path/to/panel.txt \
  --artifact magazine
```
You can override the count with `--num-items` and the model with `--model`. Use `--append` to add new articles (auto-increment ids) to an existing issue.json.

### One-command end-to-end publish
Generates `issue.json` if missing, prepares the corpus, grounds the issue, and drafts articles. This is the recommended default path.
```bash
python -m tools.publish_issue \
  --project my-project \
  --input /path/to/report.txt /path/to/panel.txt \
  --artifact magazine \
  --draft all
```
Optional flags:
- `--no-llm` (opt out of the default LLM labeling flow)
- `--draft-prefix` (prefix to use for draft filenames and the drafts folder when using the default location)
- `--include-ref-details` (enriched grounding)
- `--generate-image-prompt` (image prompts in frontmatter)
- `--skip-chunk` / `--skip-label` (reuse existing chunks/labels)
- `--skip-generate` / `--skip-prepare` / `--skip-draft` (skip stages)
- `--overwrite-issue` / `--append-issue` (for issue generation) / `--overwrite-drafts` (force draft regeneration)

### Project-root workflow (isolated per backing project)
```bash
project_root=projects/my-project

python -m tools.html_to_md --project-root "$project_root" --html "report.html" --out report.md
python -m tools.chunk_report --project-root "$project_root" --md report.md --out report_chunks.json --out-md report_chunks.md --max-chars 1200 --overlap 200
python -m tools.label_chunks --project-root "$project_root" --chunks report_chunks.json --out report_chunk_labels.json
python -m tools.auto_ground --project-root "$project_root" --issue issue.json --chunks report_chunk_labels.json --out-issue issue.grounded.json --report-context-out prompts/report_context.md --refs-per-article 2 --context-chunks 2 --include-ref-details
python -m nfl_remember_the_future.cli --project-root "$project_root" --issue-json issue.grounded.json --schema-json ../issue.schema.json --article-id all --overwrite-existing
```
Notes:
- If `projects/my-project/prompts/` exists, it overrides the global `prompts/`.
- Use a relative `--schema-json` that points back to the repo root if you keep a single schema there.

Notes:
- `report_context.md` and `report_ref_details` are pulled into prompts and draft frontmatter to keep drafts anchored.
- Adjust chunking (`--max-chars/--overlap`), refs per article (`--refs-per-article`), and context breadth (`--context-chunks`) to taste.

### Output locations
- Markdown backups: `drafts/` unless you pass `--out-md-dir`
- Index: `drafts/index.json` unless you pass `--index-json`
- JSON: only written if you pass `--write-annotated-json` (default is read-only input)
- Markdown backups: `drafts/` unless you pass `--out-md-dir`

---

## Implementation notes (for Copilot)

### Core flow
1. Load `.env` via `python-dotenv`
2. Load issue JSON + schema JSON
3. Validate issue JSON against schema (fail fast)
4. For each selected article:
   - assemble `system_prompt`:
     - `system_base.md`
     - plus optional `style_anchor` content from issue JSON
     - plus format-specific examples (`examples_longform/op ed/ad`), or override via `prompt_example`
   - assemble `user_prompt`:
     - title/lede/byline
     - scenario anchors (must be reflected)
     - writing directions (structure)
   - call `client.chat.completions.create(...)`
   - write the returned Markdown into:
     - `drafts/{id}_{slug}.md`
     - `drafts/index.json` (append/refresh record)
5. Optionally write an annotated copy of the issue JSON if `--write-annotated-json` is set

### Key code fragments used in this repo

**Env + client**
```python
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL") or None)
```

**Schema validation**
```python
validate(instance=issue, schema=schema)
```

**Chat completion**
```python
resp = client.chat.completions.create(
  model=model,
  temperature=temperature,
  max_tokens=max_tokens,
  messages=[
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt},
  ],
)
draft = resp.choices[0].message.content
```

**Write Markdown backup + index**
```python
md_path = out_md_dir / f"{id:02d}_{slugify(title)}.md"
md_path.write_text(draft + "\n", encoding="utf-8")
save_index(index_path, draft_records)
```

---

## Project plan: from CLI engine → non-chat writing assistant UI

Your intended UX (per sketch) is:
- **Left pane:** text editor (Context A — the draft)
- **Right pane:** editorial control surface (Context B — anchors, directions, ops)

The LLM should be invoked as **operations** (transformations), not conversation.

### Phase 1 — Drafting engine (this repo)
- [x] JSON Schema validation
- [x] Draft by article ID or all
- [x] Markdown backups per article
- [x] Prompt templates + format-specific examples
- [x] Draft index JSON
- [ ] Add retry/backoff and partial saves
- [ ] Add span-level edits (rewrite selection only)
- [ ] Add a lint pass (anthropomorphism/hype/anchor-coverage heuristics)

### Phase 2 — Minimal UI
- Load issue JSON, select article
- Render anchors + directions in right pane
- Buttons:
  - Draft
  - Tighten lede
  - Rewrite selected paragraph
  - Insert scene opener
- Show diffs before applying changes
- Persist to JSON + backups

### Phase 3 — Editorial QA
- Revision history and “accept/reject” diffs
- Constraint checks: confirm each anchor is referenced
- Style calibration: compare against gold-standard anchor

---

## Security defaults
- Keep secrets in `.env` and out of git.
- Avoid putting personal data into prompts by default.
- Consider a gateway (LiteLLM) if you need multiple providers behind a single compatible API.

---

## Next improvement I recommend
Add a second command: `revise` to operate on existing drafts:
- `--instruction "tighten paragraph 3"`
- optional selection span (`--start-line`, `--end-line`)
- writes a diff + patch back into JSON/MD

That gives you the exact “editor + operations” workflow your UI wants.
