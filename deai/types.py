from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Literal


class Rating(IntEnum):
    BAD = -1
    FAIR = 0
    GOOD = 1


AssetKind = Literal["native", "other"]


@dataclass
class Client:
    id: str
    stake_native: float = 0.0
    stake_other: float = 0.0
    balance: float = 0.0
    locked: bool = False
    has_pass: bool = False
    review_banned_until: int = 0
    strike: int = 0


@dataclass
class Miner:
    id: str
    ready: bool = True
    reputation: float = 50.0
    processed: int = 0
    contribution: float = 0.0
    reward: float = 0.0
    selected: int = 0
    fraud_strike: int = 0
    schedule_banned_until: int = 0


@dataclass
class Order:
    order_id: int
    client_id: str
    miner_id: str
    service: str
    weight: float
    rating: Rating | None = None
    charged: bool = False
    wait_rounds: int = 0
    accepted: bool = True
    reason: str = ""
    fraud_proven: bool = False
    fault_layer: str = ""
    bisection_rounds: int = 0


@dataclass
class Ledger:
    orders: list[Order] = field(default_factory=list)
    task_cycles: list[Order] = field(default_factory=list)
    latest_rating: dict[tuple[str, str], Rating] = field(default_factory=dict)
    epoch: int = 0
