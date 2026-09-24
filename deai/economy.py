from __future__ import annotations

from deai.types import AssetKind, Client

Q_RATIO = 0.1


def effective_stake(client: Client, q: float = Q_RATIO) -> float:
    """Native stake counts 1.0; other assets count as q (paper default 0.1)."""
    return client.stake_native + q * client.stake_other


def lock(client: Client, amount: float, kind: AssetKind = "native") -> None:
    if amount <= 0:
        raise ValueError("lock amount must be positive")
    if client.balance < amount:
        raise ValueError("insufficient balance")
    client.balance -= amount
    if kind == "native":
        client.stake_native += amount
    else:
        client.stake_other += amount
    client.locked = True
    client.has_pass = True


def unlock(client: Client) -> None:
    client.balance += client.stake_native + client.stake_other
    client.stake_native = 0.0
    client.stake_other = 0.0
    client.locked = False
    client.has_pass = False


def charged_pay(client: Client, price: float, coordinator_fee_rate: float = 0.05) -> tuple[float, float]:
    """Returns (miner_share, coordinator_fee)."""
    if client.balance < price:
        raise ValueError("insufficient balance")
    fee = price * coordinator_fee_rate
    miner_share = price - fee
    client.balance -= price
    return miner_share, fee
