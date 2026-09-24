from __future__ import annotations

from pathlib import Path

from deai.chain_client import ChainClient
from deai.engine import ProtocolEngine
from deai.types import Rating
from deai.wrr import stake_weights

ROOT = Path(__file__).resolve().parents[1]


def run_glue() -> dict:
    chain = ChainClient()
    c1, c2, c3 = chain.accounts[1], chain.accounts[2], chain.accounts[3]
    m1, m2, m3 = chain.accounts[4], chain.accounts[5], chain.accounts[6]

    for acct, amount in ((c1, 100), (c2, 300), (c3, 600)):
        chain.faucet(acct, amount)
        chain.lock(acct, amount, native=True)

    onchain = {"C1": chain.weight_of(c1), "C2": chain.weight_of(c2), "C3": chain.weight_of(c3)}
    weights = stake_weights({k: float(v) for k, v in onchain.items()})

    eng = ProtocolEngine(seed=b"chain-glue", epoch_reward=100.0)
    for cid, acct, amount in (("C1", c1, 100), ("C2", c2, 300), ("C3", c3, 600)):
        eng.add_client(cid, balance=0)
        eng.clients[cid].stake_native = float(amount)
        eng.clients[cid].locked = True
        eng.clients[cid].has_pass = chain.valid_pass(acct)
    for mid, rep in (("M1", 20.0), ("M2", 50.0), ("M3", 80.0)):
        eng.add_miner(mid, reputation=rep)

    miner_addr = {"M1": m1, "M2": m2, "M3": m3}
    for cid in ("C3", "C3", "C2", "C3", "C1", "C2", "C3", "C3", "C2", "C3"):
        order = eng.put(cid)
        eng.force_rate(order.order_id, Rating.GOOD)

    rewards = eng.settle_epoch(100.0)
    onchain_rewards = {}
    for mid, amount in rewards.items():
        wei_like = int(round(amount))
        if wei_like > 0:
            chain.credit_reward(miner_addr[mid], wei_like)
        onchain_rewards[mid] = chain.miner_rewards(miner_addr[mid])

    table = ROOT / "tables"
    table.mkdir(exist_ok=True)
    lines = ["client,onchain_weight,wrr_weight,has_pass"]
    alias = {"C1": c1, "C2": c2, "C3": c3}
    for cid in ("C1", "C2", "C3"):
        lines.append(
            f"{cid},{onchain[cid]},{weights[cid]},{str(chain.valid_pass(alias[cid])).lower()}"
        )
    (table / "onchain_weights.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    reward_lines = ["miner,engine_reward,onchain_reward"]
    for mid in ("M1", "M2", "M3"):
        reward_lines.append(f"{mid},{rewards[mid]:.6f},{onchain_rewards[mid]}")
    (table / "onchain_rewards.csv").write_text("\n".join(reward_lines) + "\n", encoding="utf-8")

    return {
        "onchain_weights": onchain,
        "wrr_weights": weights,
        "engine_rewards": rewards,
        "onchain_rewards": onchain_rewards,
        "total_locked": chain.total_locked(),
        "events": chain.locked_event_weights(),
    }


if __name__ == "__main__":
    result = run_glue()
    print(result)
