# Project workspaces

Each backing project should live in its own folder under `projects/` so that corpus inputs,
grounding outputs, and drafts remain isolated.

Suggested layout:
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

If `prompts/` is absent, the global `prompts/` folder at the repo root is used.

To generate a starter issue spec with an LLM:
```
python -m tools.generate_issue --project my-project --input /path/to/report.txt --artifact magazine
```

To run the full end-to-end pipeline:
```
python -m tools.publish_issue --project my-project --input /path/to/report.txt --artifact magazine
```
