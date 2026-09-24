from collections import Counter

from deai.engine import ProtocolEngine
from deai.types import Rating


def _free_engine() -> ProtocolEngine:
    eng = ProtocolEngine(seed=b"attack-seed", epoch_reward=100.0)
    for cid, stake in (("C1", 100), ("C2", 300), ("C3", 600)):
        eng.add_client(cid, balance=stake)
        eng.lock_tokens(cid, stake)
    for mid, rep in (("M1", 20.0), ("M2", 50.0), ("M3", 80.0)):
        eng.add_miner(mid, reputation=rep)
    return eng


def test_no_lock_is_rejected():
    eng = ProtocolEngine()
    eng.add_client("C0", balance=0)
    eng.add_miner("M1")
    order = eng.put("C0")
    assert order.accepted is False
    assert order.reason == "no_pass"
    assert eng.miners["M1"].processed == 0


def test_client_cannot_designate_miner():
    eng = _free_engine()
    picks = []
    for _ in range(300):
        order = eng.put("C1", requested_miner="M1")
        picks.append(order.miner_id)
    counts = Counter(picks)
    assert set(counts) == {"M1", "M2", "M3"}
    # M1 has the lowest reputation; requesting it must not monopolize assignment
    assert counts["M1"] < counts["M3"]


def test_malicious_reviews_get_exponential_ban():
    eng = ProtocolEngine(seed=b"ban-seed")
    for cid in ("Honest1", "Honest2", "Attacker"):
        eng.add_client(cid, balance=200)
        eng.lock_tokens(cid, 200)
    eng.add_miner("M1", reputation=50.0)

    for cid in ("Honest1", "Honest2"):
        order = eng.put(cid)
        assert eng.rate(order.order_id, Rating.GOOD) is True

    attacker = eng.clients["Attacker"]
    first = eng.put("Attacker")
    assert eng.rate(first.order_id, Rating.BAD) is False
    first_ban = attacker.review_banned_until
    assert first_ban > eng.now
    assert attacker.strike == 1

    eng.now = first_ban
    second = eng.put("Attacker")
    assert eng.rate(second.order_id, Rating.BAD) is False
    assert attacker.review_banned_until == eng.now + 16
    assert attacker.strike == 2
    assert eng.miners["M1"].reputation > 80.0
