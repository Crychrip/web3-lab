from deai.bisection import (
    diverge_at,
    inception_toy,
    model_bisection,
    sequential_mlp,
    chain_bisection,
)
from deai.channel import PaymentChannel


def test_sequential_isolates_fault():
    layers = sequential_mlp(12)
    honest, accused = diverge_at(layers, "L7")
    result = model_bisection(layers, honest, accused)
    assert result.fault == "L7"
    assert result.rounds >= 1
    assert result.rounds <= 12


def test_inception_isolates_branch():
    layers = inception_toy()
    honest, accused = diverge_at(layers, "B")
    assert honest["A"] == accused["A"]
    assert honest["C"] == accused["C"]
    assert honest["B"] != accused["B"]
    assert honest["L2"] != accused["L2"]
    result = model_bisection(layers, honest, accused)
    assert result.fault == "B"


def test_log_rounds_on_long_chain():
    layers = sequential_mlp(16)
    honest, accused = diverge_at(layers, "L12")
    result = model_bisection(layers, honest, accused)
    assert result.fault == "L12"
    assert result.rounds <= 8


def test_chain_bisection_four_rounds():
    result = chain_bisection(12, "L7")
    assert result.fault == "L7"
    assert result.rounds == 4
    assert [s.query for s in result.steps] == ["L6", "L9", "L8", "L7"]


def test_channel_hash_chain_and_dispute():
    ch = PaymentChannel("C1", "miner-A", escrow=100)
    p1 = ch.pay("req-1", 3, "C1")
    p2 = ch.pay("req-2", 3, "C1")
    assert p2.prev_hash == p1.commitment
    verdict = ch.dispute("req-2", server_claims_unpaid=True)
    assert verdict.winner == "supplier"
    assert verdict.payable == 3
    assert len(verdict.used_receipts) == 2
