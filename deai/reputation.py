from __future__ import annotations

import math

from deai.types import Rating


def logistic_reputation(scores: list[Rating], theta: float = 1.0) -> float:
    """Eq. 2: R_k = 100 / (1 + exp(-theta * sum c_i)), latest scores only."""
    total = sum(int(s) for s in scores)
    return 100.0 / (1.0 + math.exp(-theta * total))


def miner_reputation(
    latest: dict[tuple[str, str], Rating],
    miner_id: str,
    theta: float = 1.0,
    extra_scores: list[Rating] | None = None,
) -> float:
    scores = [r for (cid, mid), r in latest.items() if mid == miner_id]
    if extra_scores:
        scores.extend(extra_scores)
    if not scores:
        return 50.0
    return logistic_reputation(scores, theta=theta)
