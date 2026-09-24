from __future__ import annotations

import hashlib
import struct


def vrf_u01(seed: bytes, index: int) -> float:
    """Deterministic VRF stand-in: SHA-256(seed || index) -> (0, 1]."""
    digest = hashlib.sha256(seed + index.to_bytes(8, "little")).digest()
    (word,) = struct.unpack("<Q", digest[:8])
    return (word + 1) / 2**64


def roulette(weights: dict[str, float], u: float) -> str:
    """Weighted random selection (roulette wheel). Zero/negative weights skipped."""
    items = [(k, max(0.0, v)) for k, v in weights.items()]
    total = sum(w for _, w in items)
    if total <= 0:
        raise ValueError("no positive weights")
    target = u * total
    acc = 0.0
    last = items[-1][0]
    for key, w in items:
        acc += w
        if target <= acc:
            return key
    return last


def avrf_select(reputations: dict[str, float], seed: bytes, request_index: int) -> str:
    """Eq. 5: I_request = psi(VRF, R)."""
    return roulette(reputations, vrf_u01(seed, request_index))
