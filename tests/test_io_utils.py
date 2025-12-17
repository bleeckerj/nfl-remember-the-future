from nfl_remember_the_future.io_utils import slugify


def test_slugify_collapses_punctuation_and_runs():
    assert slugify("Hello---World!!!") == "hello-world"
    assert slugify("   Multiple   Spaces   ") == "multiple-spaces"
    assert slugify("###") == "article"
