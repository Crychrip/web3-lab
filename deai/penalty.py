from __future__ import annotations

from collections import Counter

from deai.types import Rating

BASE_BAN = 8


def majority_rating(ratings: list[Rating]) -> Rating | None:
    if not ratings:
        return None
    counts = Counter(ratings)
    top = counts.most_common()
    if len(top) >= 2 and top[0][1] == top[1][1]:
        return None
    return top[0][0]


def is_deviant(client_rating: Rating, others: list[Rating]) -> bool:
    maj = majority_rating(others)
    if maj is None:
        return False
    return client_rating != maj


def next_ban_until(now: int, strike: int, base: int = BASE_BAN) -> int:
    """Exponential lockout: t, 2t, 4t, ..."""
    return now + base * (2 ** max(0, strike - 1))
