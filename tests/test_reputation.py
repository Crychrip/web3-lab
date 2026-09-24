from deai.reputation import logistic_reputation, miner_reputation
from deai.types import Rating


def test_empty_reputation_is_fifty():
    assert miner_reputation({}, "M1") == 50.0


def test_all_good_near_one_hundred():
    r = logistic_reputation([Rating.GOOD] * 6, theta=1.0)
    assert 99.0 < r <= 100.0


def test_all_bad_near_zero():
    r = logistic_reputation([Rating.BAD] * 6, theta=1.0)
    assert 0.0 <= r < 1.0


def test_fraud_strikes_enter_equation_two():
    latest = {("C1", "M1"): Rating.GOOD}
    plain = miner_reputation(latest, "M1")
    punished = miner_reputation(latest, "M1", extra_scores=[Rating.BAD, Rating.BAD])
    assert punished < plain


def test_latest_score_only():
    latest = {("C1", "M1"): Rating.GOOD, ("C2", "M1"): Rating.FAIR}
    r = miner_reputation(latest, "M1", theta=1.0)
    assert abs(r - logistic_reputation([Rating.GOOD, Rating.FAIR])) < 1e-12
