from __future__ import annotations

from collections import Counter

from deai.avrf import avrf_select, roulette, vrf_u01


def test_vrf_deterministic():
    a = vrf_u01(b"seed", 0)
    b = vrf_u01(b"seed", 0)
    c = vrf_u01(b"seed", 1)
    assert a == b
    assert a != c
    assert 0 < a <= 1


def test_roulette_picks_only_positive():
    assert roulette({"A": 1.0, "B": 0.0}, 0.0) == "A"
    assert roulette({"A": 1.0, "B": 0.0}, 0.999) == "A"


def test_avrf_monte_carlo_matches_reputation_weights():
    reps = {"M1": 20.0, "M2": 50.0, "M3": 80.0}
    total = sum(reps.values())
    expected = {k: v / total for k, v in reps.items()}
    n = 100_000
    counts: Counter[str] = Counter()
    for i in range(n):
        counts[avrf_select(reps, b"avrf-mc", i)] += 1
    for k, p in expected.items():
        freq = counts[k] / n
        se = (p * (1 - p) / n) ** 0.5
        assert abs(freq - p) < 4 * se
