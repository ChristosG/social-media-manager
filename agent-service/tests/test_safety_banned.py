"""Deterministic banned-topic enforcement — defense-in-depth behind the soft prompt instruction.

The 9B sometimes ignores 'Never mention: X'. This is a ground-truth check that runs on generated
text BEFORE any irreversible side effect (auto-posting a public reply), so a banned topic can't slip
out just because the model didn't obey."""
from app.agent.safety import contains_banned


def test_flags_whole_word_match_case_insensitively():
    assert contains_banned("We support abortion rights.", ["abortion"]) == ["abortion"]
    assert contains_banned("ABORTION services", ["abortion"]) == ["abortion"]


def test_flags_multiword_topic_phrase():
    assert contains_banned("Our stance on gun control is clear.", ["gun control"]) == ["gun control"]


def test_does_not_false_positive_on_substring():
    # "art" must not match inside "start"; "anal" must not match inside "analysis".
    assert contains_banned("Let's start the analysis party.", ["art", "anal"]) == []


def test_clean_text_returns_empty():
    assert contains_banned("Thanks so much for your kind words!", ["politics", "religion"]) == []


def test_handles_empty_inputs():
    assert contains_banned("", ["politics"]) == []
    assert contains_banned("anything", []) == []
    assert contains_banned("anything", [""]) == []


def test_returns_all_distinct_matches():
    got = contains_banned("politics and religion and politics again", ["politics", "religion"])
    assert sorted(got) == ["politics", "religion"]


def test_matches_across_punctuation_and_hashtags():
    # A hashtag is a word boundary (# is non-word), so the topic is still caught.
    assert contains_banned("Vote now! #politics please", ["politics"]) == ["politics"]
    assert contains_banned("re: politics, no thanks", ["politics"]) == ["politics"]
