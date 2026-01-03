# Issue workflow instructions

Use this page as a quick reference for the generators, stubs, and CLI helpers that keep `nfl-remember-the-future` running.

## Stubs and boilerplate (before you run a generator)

- **Issue JSON** – `python -m tools.prepare_corpus --project <name> --input report.md --init-issue` writes `projects/<name>/issue.json` with placeholder metadata and an empty `articles` list so later tooling has somewhere to attach grounded content.
- **Prompts** – When you do run `python -m tools.generate_issue` (or `tools.publish_issue`) the system and user prompts are emitted next to the issue file as `<issue>.system_prompt.txt` and `<issue>.user_prompt.txt` (see `tools/generate_issue.py:255-277`). Inspect or edit those drafts before you fire the LLM to record the voice, anchors, and narrative instructions.
- **Style anchor** – Update `style_anchor.description`/`content` inside the issue JSON so the magazine is framed the way you want (e.g., “produced within the AI 2027 future”). Once written, the generator reuses that anchor every time it appends articles.
- **Design-fiction metadata** – Draft frontmatter now includes a `design_fiction` block (titles, artifacts, publish flags, and image metadata) so those drafts can slot into the blog/fiction site more easily.

## Common flows

1. **Prepare (always ground)**
   ```bash
   python -m tools.prepare_corpus \
     --project ai-2027 \
     --input path/to/report.html \
     --issue issue.json \
     --out-issue issue.grounded.json \
     --init-issue
   ```
   This chunks/labels the report, writes `report_context`, and auto-grounds refs (producing `issue.grounded.json`). It also creates a starter `issue.json` when `--init-issue` is passed.
   If you later add a new report, rerun this command with **all** reports you want in the grounding corpus and add `--chunk-context --relabel` so the new source is included.

2. **Generate or update issue metadata**
   ```bash
   python -m tools.generate_issue \
     --project ai-2027 \
     --input report.md \
     --artifact magazine \
     --issue-out issue.json \
     --num-items 5 \
     --append
   ```
   This calls the LLM to write the issue JSON plus the adjacent `.system_prompt.txt`/`.user_prompt.txt`. Use `--append` to add articles without wiping the existing issue and `--num-items` to limit batch size.
   When you append, the generator now summarizes the existing proposals and injects that list into the prompt so the next item knows what coverage already exists.

3. **End-to-end publish (prepare + draft)**
   ```bash
   python -m tools.publish_issue \
     --project ai-2027 \
     --input report.md \
     --artifact magazine \
     --num-items 3 \
     --draft all
   ```
   This wraps `generate_issue`, `prepare_corpus`, and `nfl_remember_the_future.cli` drafting, so you get grounded issue JSON plus Markdown drafts in one invocation.
4. **Draft using the project shortcut**
   ```bash
   python -m nfl_remember_the_future.cli \
     --project ai-2027 \
     --article-id all \
     --overwrite-existing
   ```
   When you provide `--project`, the drafter looks for `issue.grounded.json` (falling back to `issue.json`) plus the project’s prompts and schema, so you don’t need to pass those individually.
   If the project lacks `issue.schema.json`, the CLI now checks the repo root copy and warns if neither path is available.

## Variations and useful flags

- `--overwrite` / `--overwrite-issue` – force a fresh issue.json even if one already exists.
- `--append` / `--append-issue` – keep older articles and auto-increment IDs when adding new ones.
- `--no-print-prompts` – skip writing the `.system_prompt.txt`/`.user_prompt.txt` files during generation.
- `--relabel` – force `tools.prepare_corpus` (and `publish_issue`) to rerun chunk labeling even when `report_chunk_labels.json` already exists.
- `--chunk-context` – force `tools.prepare_corpus` to rebuild `report.md` and `report_chunks.json` even when they already exist (use this when adding a new report to the corpus).

## Chunking and labeling behavior

- `tools.prepare_corpus` now looks for `report_chunks.json` before re-running the chunk step. If the file exists it skips chunking by default; use `--chunk-context` to force a fresh chunk pass even when the JSON is present (needed when you add a new report).
- `tools.prepare_corpus` also checks `report_chunk_labels.json` before labeling and skips relabeling unless you pass `--relabel` (or call with `--skip-label`, which still raises if the file is missing). This keeps the pipeline from relabeling already-annotated chunk data.
- `tools.publish_issue` forwards both `--chunk-context` and `--relabel` along with `--skip-chunk`/`--skip-label`, so the publish flow honors whichever chunk/label shortcuts you choose.

## Next steps

1. Adjust the `style_anchor` to frame the magazine as coming from the speculative world you are building.
2. Run `tools.generate_issue` with the `--append`/`--num-items` combo that fits your editing cadence.
3. Reuse `--skip-chunk`/`--skip-label` once you have good chunk files so the generator doesn’t redo them every time.
