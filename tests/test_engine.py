from deai.economy import Q_RATIO, effective_stake
from deai.engine import ProtocolEngine
from deai.types import Rating


def test_lock_grants_pass_and_q_ratio():
    eng = ProtocolEngine()
    c = eng.add_client("C1", balance=110)
    eng.lock_tokens("C1", 100, "native")
    eng.lock_tokens("C1", 10, "other")
    assert c.has_pass
    assert abs(effective_stake(c) - (100 + Q_RATIO * 10)) < 1e-12


def test_charged_vs_free_balance():
    eng = ProtocolEngine(charge_price=10.0, coordinator_fee_rate=0.1)
    eng.add_client("Free", balance=100)
    eng.add_client("Paid", balance=100)
    eng.lock_tokens("Free", 50)
    eng.add_miner("M1", reputation=80)
    free_order = eng.put("Free", charged=False)
    paid_order = eng.put("Paid", charged=True)
    assert eng.clients["Free"].balance == 50
    assert abs(eng.clients["Paid"].balance - 90) < 1e-12
    assert abs(eng.coordinator_fees - 1.0) < 1e-12
    assert abs(eng.miners["M1"].reward - 9.0) < 1e-12
    eng.force_rate(free_order.order_id, Rating.GOOD)
    eng.force_rate(paid_order.order_id, Rating.GOOD)


def test_wrr_queue_prefers_higher_stake():
    eng = ProtocolEngine()
    for cid, stake in (("C1", 100), ("C2", 300), ("C3", 600)):
        eng.add_client(cid, balance=stake)
        eng.lock_tokens(cid, stake)
    eng.add_miner("M1", reputation=50)
    eng.set_ready("M1", False)
    for cid in ("C1", "C2", "C3", "C3", "C3"):
        eng.put(cid)
    eng.set_ready("M1", True)
    served = [o.client_id for o in eng.ledger.orders if o.accepted and o.miner_id == "M1"]
    # C3 appears more often in the drained WRR schedule than C1
    assert served.count("C3") > served.count("C1")


def test_epoch_reward_splits_by_contribution():
    eng = ProtocolEngine(seed=b"reward", epoch_reward=100.0)
    eng.add_client("C1", balance=500)
    eng.lock_tokens("C1", 500)
    for mid in ("M1", "M2"):
        eng.add_miner(mid, reputation=50)
    orders = [eng.put("C1") for _ in range(10)]
    for order in orders:
        eng.force_rate(order.order_id, Rating.GOOD)
    rewards = eng.settle_epoch(100.0)
    assert abs(sum(rewards.values()) - 100.0) < 1e-9
    processed = sum(m.processed for m in eng.miners.values())
    assert processed == 10
