import json
from pathlib import Path

from nfl_remember_the_future.drafting import draft_articles, select_articles
from nfl_remember_the_future.models import DraftConfig


class FakeCompletions:
    def __init__(self, content: str):
        self.content = content

    def create(self, **kwargs):
        return type(
            "Resp",
            (),
            {"choices": [type("Choice", (), {"message": type("Msg", (), {"content": self.content})()})]},
        )()


class FakeChat:
    def __init__(self, content: str):
        self.completions = FakeCompletions(content)


class FakeClient:
    def __init__(self, content: str):
        self.chat = FakeChat(content)


def build_schema(tmp_path: Path) -> Path:
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["issue", "articles"],
        "properties": {
            "issue": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "date": {"type": "string"}, "status": {"type": "string"}, "source": {"type": "string"}},
                "required": ["title", "date", "status", "source"],
            },
            "articles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "title": {"type": "string"},
                        "format": {"type": "string"},
                        "lede": {"type": "string"},
                        "byline": {"type": "string"},
                        "ai2027_anchor": {"type": "array", "items": {"type": "string"}},
                        "writing_directions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "title", "format", "lede", "byline", "ai2027_anchor", "writing_directions"],
                },
            },
        },
    }
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    return schema_path


def build_issue(tmp_path: Path) -> Path:
    issue = {
        "issue": {"title": "Issue Title", "date": "2027", "status": "frozen", "source": "AI 2027"},
        "articles": [
            {
                "id": 1,
                "title": "Test Article",
                "format": "Feature",
                "lede": "Lede here",
                "byline": "Byline",
                "ai2027_anchor": ["Anchor"],
                "writing_directions": ["Direction"],
            }
        ],
    }
    issue_path = tmp_path / "issue.json"
    issue_path.write_text(json.dumps(issue), encoding="utf-8")
    return issue_path


def build_prompts(tmp_path: Path) -> Path:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "system_base.md").write_text("SYSTEM", encoding="utf-8")
    (prompt_dir / "examples_longform.md").write_text("Example", encoding="utf-8")
    return prompt_dir


def test_draft_articles_writes_md_and_index(tmp_path):
    issue_path = build_issue(tmp_path)
    schema_path = build_schema(tmp_path)
    prompt_dir = build_prompts(tmp_path)
    drafts_dir = tmp_path / "drafts"
    annotated_path = tmp_path / "annotated.json"
    client = FakeClient("DRAFT CONTENT")

    config = DraftConfig(
        issue_json=issue_path,
        schema_json=schema_path,
        prompt_dir=prompt_dir,
        out_md_dir=drafts_dir,
        index_json=drafts_dir / "index.json",
        article_id="1",
        model="test-model",
        temperature=0.1,
        max_completion_tokens=100,
        overwrite_existing=True,
        write_annotated_json=True,
        out_json=annotated_path,
    )

    draft_articles(config=config, client=client, now_fn=lambda: "2024-01-01T00:00:00Z")

    md_files = list(drafts_dir.glob("*.md"))
    assert len(md_files) == 1
    md_text = md_files[0].read_text(encoding="utf-8")
    assert md_text.startswith("---")
    assert "anchors:" in md_text
    assert "writing_directions:" in md_text
    assert "DRAFT CONTENT" in md_text

    index_data = json.loads((drafts_dir / "index.json").read_text(encoding="utf-8"))
    assert index_data["drafts"][0]["article_id"] == 1
    assert index_data["drafts"][0]["md_path"].endswith(".md")

    annotated = json.loads(annotated_path.read_text(encoding="utf-8"))
    assert annotated["articles"][0]["draft_path"].endswith(".md")


def test_draft_articles_dry_run(tmp_path):
    issue_path = build_issue(tmp_path)
    schema_path = build_schema(tmp_path)
    prompt_dir = build_prompts(tmp_path)
    drafts_dir = tmp_path / "drafts"
    index_path = drafts_dir / "index.json"

    config = DraftConfig(
        issue_json=issue_path,
        schema_json=schema_path,
        prompt_dir=prompt_dir,
        out_md_dir=drafts_dir,
        index_json=index_path,
        article_id="1",
        model=None,
        temperature=0.6,
        max_completion_tokens=100,
        overwrite_existing=True,
        write_annotated_json=False,
        out_json=None,
        dry_run=True,
        dry_run_text="[DRY RUN CONTENT]",
    )

    draft_articles(config=config, client=None, now_fn=lambda: "2024-01-01T00:00:00Z")

    md_files = list(drafts_dir.glob("*.md"))
    assert md_files and "[DRY RUN CONTENT]" in md_files[0].read_text(encoding="utf-8")
    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    assert index_data["drafts"][0]["model"] == "dry-run"


def test_select_articles_allows_list_and_range():
    articles = [
        {"id": 1, "title": "A"},
        {"id": 2, "title": "B"},
        {"id": 3, "title": "C"},
        {"id": 4, "title": "D"},
    ]
    selected = select_articles(articles, "2,4")
    assert [a["id"] for a in selected] == [2, 4]

    selected_range = select_articles(articles, "2-3")
    assert [a["id"] for a in selected_range] == [2, 3]
