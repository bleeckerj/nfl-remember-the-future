from nfl_remember_the_future.models import ArticleSpec
from nfl_remember_the_future.prompts import build_system_prompt, build_user_prompt, pick_examples


def test_pick_examples_by_format():
    prompts = {"examples_oped": "oped", "examples_ad": "ad", "examples_longform": "long"}
    assert pick_examples(prompts, "Op-Ed column") == "oped"
    assert pick_examples(prompts, "Advertisement") == "ad"
    assert pick_examples(prompts, "Feature") == "long"


def test_pick_examples_override_prompt_example():
    prompts = {"examples_oped": "oped"}
    assert pick_examples(prompts, "Feature", prompt_example="examples_oped") == "oped"


def test_build_prompts_include_metadata():
    article = ArticleSpec(
        id=7,
        title="Test Title",
        format="Explainer",
        lede="Lede goes here",
        byline="Byline",
        report_anchor=["Anchor A", "Anchor B"],
        writing_directions=["Direction 1"],
        report_refs=["Section 2.1 — Alignment warnings"],
    )
    prompts = {"system_base": "SYSTEM", "examples_longform": "Example", "report_context": "Report context block"}
    system_prompt = build_system_prompt(prompts, article, "Style anchor text", "Report context block")
    user_prompt = build_user_prompt(article, {"title": "Issue Title", "date": "2027"})

    assert "SYSTEM" in system_prompt
    assert "Style anchor text" in system_prompt
    assert "Report context block" in system_prompt
    assert "Anchor A" in user_prompt
    assert "Direction 1" in user_prompt
    assert "Section 2.1" in user_prompt
