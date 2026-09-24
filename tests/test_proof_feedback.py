from deai.engine import ProtocolEngine
from deai.types import Rating


def _market() -> ProtocolEngine:
    eng = ProtocolEngine(seed=b"proof-seed", proof_feedback=True)
    for cid, stake in (("C1", 100), ("C2", 300), ("C3", 600)):
        eng.add_client(cid, balance=stake)
        eng.lock_tokens(cid, stake)
    for mid in ("M1", "M2", "M3"):
        eng.add_miner(mid, reputation=50.0)
    eng.faulty_miners.add("M3")
    return eng


def test_honest_challenge_does_not_ban():
    eng = _market()
    eng.faulty_miners.clear()
    order = eng.put("C1")
    eng.force_rate(order.order_id, Rating.GOOD)
    rec = eng.challenge(order.order_id)
    assert rec["fraud"] is False
    assert eng.miners[order.miner_id].fraud_strike == 0
    assert eng.miners[order.miner_id].schedule_banned_until == 0
    assert eng.miners[order.miner_id].reputation > 50.0


def test_fraud_challenge_writes_bad_and_bans_miner():
    eng = _market()
    target = None
    for cid in ("C1", "C2", "C3") * 10:
        order = eng.put(cid)
        eng.force_rate(order.order_id, Rating.GOOD)
        if order.miner_id == "M3":
            target = order
            break
    assert target is not None
    rec = eng.challenge(target.order_id)
    assert rec["fraud"] is True
    assert rec["fault"] == "L7"
    assert rec["rounds"] >= 1
    miner = eng.miners["M3"]
    assert miner.fraud_strike == 1
    assert miner.schedule_banned_until > eng.now
    assert target.fraud_proven
    assert target.rating == Rating.BAD
    assert miner.reputation < 50.0


def test_banned_miner_is_not_scheduled():
    eng = _market()
    target = None
    while target is None:
        order = eng.put("C3")
        eng.force_rate(order.order_id, Rating.GOOD)
        if order.miner_id == "M3":
            target = order
    eng.challenge(target.order_id)
    ban_until = eng.miners["M3"].schedule_banned_until
    picks = []
    while eng.now < ban_until:
        order = eng.put("C3")
        eng.force_rate(order.order_id, Rating.GOOD)
        picks.append(order.miner_id)
    assert "M3" not in picks
    assert set(picks) <= {"M1", "M2"}


def test_fraud_cycle_excluded_from_rewards():
    eng = ProtocolEngine(seed=b"reward-fraud", epoch_reward=100.0, proof_feedback=True)
    eng.add_client("C1", balance=500)
    eng.lock_tokens("C1", 500)
    eng.add_miner("M1", reputation=50.0)
    eng.add_miner("M3", reputation=50.0)
    eng.faulty_miners.add("M3")
    fraud_order = None
    honest_n = 0
    for _ in range(20):
        order = eng.put("C1")
        eng.force_rate(order.order_id, Rating.GOOD)
        if order.miner_id == "M3":
            eng.challenge(order.order_id)
            if fraud_order is None:
                fraud_order = order
        else:
            honest_n += 1
    assert fraud_order is not None
    rewards = eng.settle_epoch(100.0)
    assert rewards["M3"] == 0.0
    assert rewards["M1"] == 100.0
    assert honest_n > 0


def test_proof_feedback_off_records_but_does_not_penalize():
    eng = _market()
    eng.proof_feedback = False
    target = None
    for _ in range(12):
        order = eng.put("C3")
        eng.force_rate(order.order_id, Rating.GOOD)
        if order.miner_id == "M3":
            target = order
            break
    assert target is not None
    rec = eng.challenge(target.order_id)
    assert rec["fraud"] is True
    assert rec["applied"] is False
    assert eng.miners["M3"].fraud_strike == 0
    assert target.fraud_proven is False
    assert target.rating == Rating.GOOD


def test_client_cannot_overwrite_proven_fraud_with_good():
    eng = _market()
    target = None
    for _ in range(12):
        order = eng.put("C1")
        if order.miner_id == "M3":
            target = order
            break
    assert target is not None
    rec = eng.challenge(target.order_id)
    assert rec["fraud"] is True
    assert eng.rate(target.order_id, Rating.GOOD) is False
    assert target.rating == Rating.BAD
