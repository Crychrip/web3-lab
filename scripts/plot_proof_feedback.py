from __future__ import annotations

"""Rating-only vs bisection-feedback: does a cheating miner keep getting scheduled?"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from deai.engine import ProtocolEngine
from deai.types import Rating

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
TAB = ROOT / "tables"
CLIENTS = ("C1", "C2", "C3")
N_REQUESTS = 400


def _engine(seed: bytes, proof_feedback: bool) -> ProtocolEngine:
    eng = ProtocolEngine(seed=seed, proof_feedback=proof_feedback, epoch_reward=100.0)
    for cid, stake in (("C1", 100.0), ("C2", 300.0), ("C3", 600.0)):
        eng.add_client(cid, balance=10_000)
        eng.lock_tokens(cid, stake)
    for mid in ("M1", "M2", "M3"):
        eng.add_miner(mid, reputation=50.0)
    eng.faulty_miners.add("M3")
    return eng


def run_mode(proof_feedback: bool, n: int = N_REQUESTS) -> dict:
    eng = _engine(b"proof-vs-rating", proof_feedback)
    share = []
    m3_selected = 0
    challenged = 0
    for i in range(n):
        cid = CLIENTS[i % 3]
        order = eng.put(cid)
        if order.accepted:
            eng.force_rate(order.order_id, Rating.GOOD)
            rec = eng.challenge(order.order_id)
            if rec.get("fraud"):
                challenged += 1
        if order.miner_id == "M3":
            m3_selected += 1
        share.append(m3_selected / (i + 1))
    rewards = eng.settle_epoch(100.0)
    return {
        "share": share,
        "selected": {m.id: m.selected for m in eng.miners.values()},
        "reputation": {m.id: m.reputation for m in eng.miners.values()},
        "fraud_strike": {m.id: m.fraud_strike for m in eng.miners.values()},
        "rewards": rewards,
        "challenged": challenged,
        "banned_until": {m.id: m.schedule_banned_until for m in eng.miners.values()},
    }


def plot() -> dict:
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    rating_only = run_mode(False)
    with_proof = run_mode(True)

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.2))
    xs = list(range(1, N_REQUESTS + 1))
    axes[0].plot(xs, rating_only["share"], color="#ADB5BD", label="Rating only")
    axes[0].plot(xs, with_proof["share"], color="#E03131", label="Rating + bisection")
    axes[0].axhline(1 / 3, color="#4C6EF5", linestyle="--", linewidth=1, alpha=0.8, label="Equal share 1/3")
    axes[0].set_xlabel("Requests")
    axes[0].set_ylabel("M3 (cheater) selection share")
    axes[0].set_title("Cheater stays in AVRF unless fraud proof feeds back")
    axes[0].set_ylim(0, 0.55)
    axes[0].legend(frameon=False)
    axes[0].grid(True, alpha=0.3)

    labels = ["M1", "M2", "M3"]
    x = range(len(labels))
    axes[1].bar(
        [i - 0.18 for i in x],
        [rating_only["reputation"][k] for k in labels],
        width=0.36,
        color="#ADB5BD",
        label="Rating only",
    )
    axes[1].bar(
        [i + 0.18 for i in x],
        [with_proof["reputation"][k] for k in labels],
        width=0.36,
        color="#E03131",
        label="Rating + bisection",
    )
    axes[1].set_xticks(list(x), labels)
    axes[1].set_ylabel("Reputation (eq. 2)")
    axes[1].set_title("Final reputation after 400 GOOD ratings")
    axes[1].set_ylim(0, 100)
    axes[1].legend(frameon=False)
    axes[1].grid(True, axis="y", alpha=0.3)

    fig.suptitle("Clients always rate GOOD; only M3 serves a faulty model", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "fig13_proof_feedback.png", dpi=160)
    plt.close(fig)

    lines = ["mode,miner,selected,reputation,fraud_strike,reward"]
    for mode, blob in (("rating_only", rating_only), ("bisection_feedback", with_proof)):
        for mid in labels:
            lines.append(
                f"{mode},{mid},{blob['selected'][mid]},{blob['reputation'][mid]:.6f},"
                f"{blob['fraud_strike'][mid]},{blob['rewards'][mid]:.6f}"
            )
    (TAB / "proof_feedback.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {
        "rating_only_m3_share": rating_only["share"][-1],
        "proof_m3_share": with_proof["share"][-1],
        "rating_only_rep": rating_only["reputation"],
        "proof_rep": with_proof["reputation"],
        "rating_only_selected": rating_only["selected"],
        "proof_selected": with_proof["selected"],
        "proof_challenged": with_proof["challenged"],
        "rating_only_rewards": rating_only["rewards"],
        "proof_rewards": with_proof["rewards"],
    }
    return summary


if __name__ == "__main__":
    import json

    print(json.dumps(plot(), indent=2))
