from __future__ import annotations

from deai.types import Ledger, Order


def record_order(ledger: Ledger, order: Order) -> None:
    ledger.orders.append(order)


def complete_cycle(ledger: Ledger, order: Order) -> None:
    ledger.task_cycles.append(order)
    if order.rating is not None:
        ledger.latest_rating[(order.client_id, order.miner_id)] = order.rating
    ledger.epoch += 1
