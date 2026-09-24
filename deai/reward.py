from __future__ import annotations


def contribution(processed_by_service: dict[str, int], service_weights: dict[str, float]) -> float:
    """Eq. 3: C_k = sum_j N_processed,j * W_service,j."""
    return sum(n * service_weights.get(svc, 1.0) for svc, n in processed_by_service.items())


def split_rewards(contributions: dict[str, float], total_reward: float) -> dict[str, float]:
    """Eq. 4: R_k = C_k / C_total * R."""
    c_total = sum(contributions.values())
    if c_total <= 0:
        return {k: 0.0 for k in contributions}
    return {k: (c / c_total) * total_reward for k, c in contributions.items()}
