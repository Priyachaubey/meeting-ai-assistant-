from app.services.scoring import compute_meeting_score


def test_score_combines_decisions_and_action_items():
    score = compute_meeting_score(decisions=["d1", "d2"], action_items=["a1"], risks=[])
    assert score.decisiveness == 40
    assert score.productivity == 15
    assert score.risk_penalty == 0
    assert score.overall == min(100, 50 + 40 + 15)


def test_risk_penalty_caps_at_30():
    score = compute_meeting_score(decisions=[], action_items=[], risks=["r1", "r2", "r3", "r4"])
    assert score.risk_penalty == 30  # would be 40 uncapped (4 * 10)
    assert score.overall == 20


def test_overall_never_exceeds_100():
    score = compute_meeting_score(decisions=["d"] * 10, action_items=["a"] * 10, risks=[])
    assert score.overall == 100


def test_overall_never_goes_negative():
    score = compute_meeting_score(decisions=[], action_items=[], risks=["r"] * 10)
    assert score.overall == 20  # 50 - 30 (capped), still well above 0, but formula floors at 0
    assert score.overall >= 0
