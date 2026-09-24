from __future__ import annotations

from dataclasses import dataclass, field

from deai.avrf import avrf_select
from deai.bisection import diverge_at, model_bisection, sequential_mlp
from deai.economy import charged_pay, effective_stake, lock, unlock
from deai.ledger import complete_cycle, record_order
from deai.penalty import is_deviant, next_ban_until
from deai.reputation import miner_reputation
from deai.reward import contribution, split_rewards
from deai.types import AssetKind, Client, Ledger, Miner, Order, Rating
from deai.wrr import interleaved_wrr, stake_weights


DEFAULT_SERVICES = {"text": 1.0, "image": 2.0}


@dataclass
class ProtocolEngine:
    seed: bytes = b"deai-2310.19099"
    theta: float = 1.0
    epoch_reward: float = 100.0
    service_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SERVICES))
    charge_price: float = 1.0
    coordinator_fee_rate: float = 0.05

    clients: dict[str, Client] = field(default_factory=dict)
    miners: dict[str, Miner] = field(default_factory=dict)
    ledger: Ledger = field(default_factory=Ledger)
    coordinator_fees: float = 0.0
    next_order_id: int = 1
    request_index: int = 0
    now: int = 0
    pending: dict[str, list[int]] = field(default_factory=dict)
    proof_feedback: bool = True
    faulty_miners: set[str] = field(default_factory=set)
    fault_layer: str = "L7"
    bisection_depth: int = 12
    disputes: list[dict] = field(default_factory=list)

    def add_client(self, client_id: str, balance: float = 0.0) -> Client:
        client = Client(id=client_id, balance=balance)
        self.clients[client_id] = client
        return client

    def add_miner(self, miner_id: str, reputation: float = 50.0) -> Miner:
        miner = Miner(id=miner_id, reputation=reputation)
        self.miners[miner_id] = miner
        return miner

    def lock_tokens(self, client_id: str, amount: float, kind: AssetKind = "native") -> None:
        lock(self.clients[client_id], amount, kind)

    def unlock_tokens(self, client_id: str) -> None:
        unlock(self.clients[client_id])

    def _refresh_reputations(self) -> None:
        for miner in self.miners.values():
            extras = [Rating.BAD] * miner.fraud_strike
            miner.reputation = miner_reputation(
                self.ledger.latest_rating,
                miner.id,
                theta=self.theta,
                extra_scores=extras,
            )

    def _eligible_reputations(self) -> dict[str, float]:
        reps = {
            m.id: m.reputation
            for m in self.miners.values()
            if self.now >= m.schedule_banned_until
        }
        if reps:
            return reps
        return {m.id: 1.0 for m in self.miners.values()}

    def select_miner(self, requested: str | None = None) -> str:
        del requested  # clients cannot designate a provider
        reps = self._eligible_reputations()
        chosen = avrf_select(reps, self.seed, self.request_index)
        self.request_index += 1
        self.miners[chosen].selected += 1
        return chosen

    def put(
        self,
        client_id: str,
        service: str = "text",
        charged: bool = False,
        requested_miner: str | None = None,
    ) -> Order:
        client = self.clients[client_id]
        self.now += 1
        order_id = self.next_order_id
        self.next_order_id += 1

        if not charged and not client.has_pass:
            order = Order(
                order_id=order_id,
                client_id=client_id,
                miner_id="",
                service=service,
                weight=self.service_weights.get(service, 1.0),
                charged=charged,
                accepted=False,
                reason="no_pass",
            )
            record_order(self.ledger, order)
            return order

        if charged:
            miner_share, fee = charged_pay(client, self.charge_price, self.coordinator_fee_rate)
            self.coordinator_fees += fee
        else:
            miner_share = 0.0

        miner_id = self.select_miner(requested_miner)
        miner = self.miners[miner_id]
        order = Order(
            order_id=order_id,
            client_id=client_id,
            miner_id=miner_id,
            service=service,
            weight=self.service_weights.get(service, 1.0),
            charged=charged,
        )
        record_order(self.ledger, order)

        if miner.ready:
            self._serve(order, miner_share)
        else:
            self.pending.setdefault(miner_id, []).append(order_id)
        return order

    def set_ready(self, miner_id: str, ready: bool) -> None:
        miner = self.miners[miner_id]
        miner.ready = ready
        if ready:
            self._drain_queue(miner_id)

    def _drain_queue(self, miner_id: str) -> None:
        queued_ids = self.pending.get(miner_id, [])
        if not queued_ids:
            return
        queued = [o for o in self.ledger.orders if o.order_id in queued_ids]
        stakes = {cid: effective_stake(self.clients[cid]) for cid in {o.client_id for o in queued}}
        backlog = {}
        for order in queued:
            backlog[order.client_id] = backlog.get(order.client_id, 0) + 1
        schedule = interleaved_wrr(stakes, backlog)
        by_client: dict[str, list[Order]] = {}
        for order in queued:
            by_client.setdefault(order.client_id, []).append(order)
        served: list[Order] = []
        for cid in schedule:
            if by_client.get(cid):
                order = by_client[cid].pop(0)
                order.wait_rounds = 1
                served.append(order)
        leftover_ids = [o.order_id for orders in by_client.values() for o in orders]
        self.pending[miner_id] = leftover_ids
        miner = self.miners[miner_id]
        for order in served:
            self._serve(order, miner_share=0.0)
        miner.ready = True

    def _serve(self, order: Order, miner_share: float) -> None:
        miner = self.miners[order.miner_id]
        miner.processed += 1
        miner.reward += miner_share

    def rate(self, order_id: int, rating: Rating) -> bool:
        order = next(o for o in self.ledger.orders if o.order_id == order_id)
        if not order.accepted or not order.miner_id:
            return False
        if order.fraud_proven:
            return False
        client = self.clients[order.client_id]
        if self.now < client.review_banned_until:
            return False

        others = [
            r
            for (cid, mid), r in self.ledger.latest_rating.items()
            if mid == order.miner_id and cid != client.id
        ]
        deviant = is_deviant(rating, others)
        if deviant:
            client.strike += 1
            client.review_banned_until = next_ban_until(self.now, client.strike)
            return False

        order.rating = rating
        complete_cycle(self.ledger, order)
        self._refresh_reputations()
        return True

    def force_rate(self, order_id: int, rating: Rating) -> None:
        """Apply a rating without majority checks (for constructing a majority)."""
        order = next(o for o in self.ledger.orders if o.order_id == order_id)
        if order.fraud_proven:
            return
        order.rating = rating
        complete_cycle(self.ledger, order)
        self._refresh_reputations()

    def challenge(self, order_id: int) -> dict:
        """Run Model Bisection on an accepted order.

        If the miner is in ``faulty_miners``, outputs diverge at ``fault_layer``.
        A proven fault writes an objective BAD into eq. 2, bans the miner from
        AVRF for an exponential window, and excludes the cycle from rewards.
        """
        order = next(o for o in self.ledger.orders if o.order_id == order_id)
        if not order.accepted or not order.miner_id:
            return {"ok": False, "fraud": False, "reason": "not_accepted"}

        layers = sequential_mlp(self.bisection_depth)
        honest, accused_faulty = diverge_at(layers, self.fault_layer)
        accused = accused_faulty if order.miner_id in self.faulty_miners else dict(honest)
        fraud = any(honest[n] != accused[n] for n in layers)
        if not fraud:
            rec = {
                "ok": True,
                "fraud": False,
                "order_id": order.order_id,
                "miner_id": order.miner_id,
                "fault": "",
                "rounds": 0,
            }
            self.disputes.append(rec)
            return rec

        result = model_bisection(layers, honest, accused)
        order.fault_layer = result.fault
        order.bisection_rounds = result.rounds
        if self.proof_feedback:
            self._penalize_fraud(order, result.fault, result.rounds)
        rec = {
            "ok": True,
            "fraud": True,
            "order_id": order.order_id,
            "miner_id": order.miner_id,
            "fault": result.fault,
            "rounds": result.rounds,
            "applied": self.proof_feedback,
        }
        self.disputes.append(rec)
        return rec

    def _penalize_fraud(self, order: Order, fault: str, rounds: int) -> None:
        miner = self.miners[order.miner_id]
        order.fraud_proven = True
        order.fault_layer = fault
        order.bisection_rounds = rounds
        order.rating = Rating.BAD
        self.ledger.latest_rating[(order.client_id, order.miner_id)] = Rating.BAD
        miner.fraud_strike += 1
        miner.schedule_banned_until = next_ban_until(self.now, miner.fraud_strike)
        self._refresh_reputations()

    def settle_epoch(self, total_reward: float | None = None) -> dict[str, float]:
        r = self.epoch_reward if total_reward is None else total_reward
        processed: dict[str, dict[str, int]] = {m: {} for m in self.miners}
        for order in self.ledger.task_cycles:
            if not order.accepted or not order.miner_id or order.fraud_proven:
                continue
            bucket = processed[order.miner_id]
            bucket[order.service] = bucket.get(order.service, 0) + 1
        contrib = {
            mid: contribution(svc, self.service_weights) for mid, svc in processed.items()
        }
        rewards = split_rewards(contrib, r)
        for mid, miner in self.miners.items():
            miner.contribution = contrib.get(mid, 0.0)
            miner.reward += rewards.get(mid, 0.0)
        return rewards

    def stake_map(self) -> dict[str, float]:
        return {cid: effective_stake(c) for cid, c in self.clients.items()}

    def weights(self) -> dict[str, int]:
        return stake_weights(self.stake_map())
