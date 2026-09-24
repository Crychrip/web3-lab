from __future__ import annotations

import math

from deai.wrr import interleaved_wrr, stake_weights, wrr_serve_counts


def test_eq1_weights():
    w = stake_weights({"C1": 100, "C2": 300, "C3": 600})
    assert w == {"C1": 1, "C2": 3, "C3": 6}


def test_interleaved_cycle_is_1_3_6():
    stakes = {"C1": 100.0, "C2": 300.0, "C3": 600.0}
    cycle = interleaved_wrr(stakes, {k: 10 for k in stakes})
    counts = {k: cycle.count(k) for k in stakes}
    assert counts == {"C1": 1, "C2": 3, "C3": 6}


def test_wrr_monte_carlo_converges():
    stakes = {"C1": 100.0, "C2": 300.0, "C3": 600.0}
    n = 100_000
    counts = wrr_serve_counts(stakes, n)
    expected = {"C1": n * 0.1, "C2": n * 0.3, "C3": n * 0.6}
    for k in stakes:
        se = math.sqrt(n * (expected[k] / n) * (1 - expected[k] / n))
        # WRR is deterministic given infinite backlog; still check 95% CI style bound
        assert abs(counts[k] - expected[k]) <= max(1.96 * se, 1)


def test_zero_stake_gets_zero_weight():
    w = stake_weights({"A": 0.0, "B": 50.0})
    assert w["A"] == 0
    assert w["B"] == 1
