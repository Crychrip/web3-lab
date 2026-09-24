from __future__ import annotations

import math


def stake_weights(stakes: dict[str, float]) -> dict[str, int]:
    """Eq. 1: w_r = floor(s_r / s_min)."""
    positive = {k: v for k, v in stakes.items() if v > 0}
    if not positive:
        return {k: 0 for k in stakes}
    s_min = min(positive.values())
    return {k: int(math.floor(v / s_min)) if v > 0 else 0 for k, v in stakes.items()}


def interleaved_wrr(stakes: dict[str, float], backlog: dict[str, int]) -> list[str]:
    """Serve one request per eligible client each round, up to weight w_r.

    Returns the client-id schedule. Clients with remaining backlog keep being
    served in later rounds until their weight quota or backlog is exhausted.
    """
    weights = stake_weights(stakes)
    remaining = dict(backlog)
    order: list[str] = []
    w_max = max(weights.values(), default=0)
    clients = list(stakes.keys())
    for round_idx in range(1, w_max + 1):
        for cid in clients:
            if remaining.get(cid, 0) <= 0:
                continue
            if weights[cid] >= round_idx:
                order.append(cid)
                remaining[cid] -= 1
    return order


def wrr_serve_counts(stakes: dict[str, float], slots: int) -> dict[str, int]:
    """Fill `slots` using repeating interleaved WRR (infinite backlog)."""
    weights = stake_weights(stakes)
    cycle = interleaved_wrr(stakes, {cid: weights[cid] for cid in stakes})
    if not cycle:
        return {cid: 0 for cid in stakes}
    counts = {cid: 0 for cid in stakes}
    for i in range(slots):
        counts[cycle[i % len(cycle)]] += 1
    return counts
