from app.agent.router import classify


def test_corrections_route_to_thinking():
    for m in ["Too corporate — redo it.", "make it warmer", "that's not quite right",
              "this feels generic, try again", "less stiff please"]:
        assert classify(m).reasoning, m


def test_identity_voice_feedback_routes_to_thinking():
    # "be the voice of my org" / "this is vague, doesn't represent us" must get the deliberate pass AND be
    # recognized as a correction (so the assistant persists + reworks) — previously these slipped through.
    for m in ["is this really the face of my organisation?", "be the voice of my organization",
              "this feels vague, it doesn't represent us", "it's ambiguous, not who we are"]:
        assert classify(m).reasoning, m


def test_analytical_and_planning_route_to_thinking():
    for m in ["Why did engagement drop last month?", "Compare LinkedIn vs Instagram for us",
              "What's our content strategy for the quarter?", "Brainstorm ideas for the year"]:
        assert classify(m).reasoning, m


def test_multi_constraint_and_long_route_to_thinking():
    assert classify("Write a LinkedIn post about the gala and also an Instagram caption").reasoning
    assert classify(" ".join(["word"] * 50)).reasoning


def test_simple_turns_stay_fast():
    for m in ["Suggest some posts for us.", "What programs do we run?",
              "Write it for LinkedIn.", "Give me an Instagram version.", ""]:
        assert not classify(m).reasoning, m


def test_decision_carries_a_reason():
    d = classify("too corporate, redo")
    assert d.reasoning and isinstance(d.reason, str) and d.reason
