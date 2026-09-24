from __future__ import annotations

from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from deai.avrf import avrf_select
from deai.engine import ProtocolEngine
from deai.types import Rating
from deai.wrr import wrr_serve_counts

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
TAB = ROOT / "tables"


def _save(fig: plt.Figure, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=160)
    plt.close(fig)


def plot_wrr_convergence() -> None:
    stakes = {"C1": 100.0, "C2": 300.0, "C3": 600.0}
    expected = {"C1": 0.1, "C2": 0.3, "C3": 0.6}
    checkpoints = np.unique(np.logspace(2, 5, 40).astype(int))
    series = {k: [] for k in stakes}
    for n in checkpoints:
        counts = wrr_serve_counts(stakes, int(n))
        for k in stakes:
            series[k].append(counts[k] / n)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    colors = {"C1": "#4C6EF5", "C2": "#F08C00", "C3": "#2F9E44"}
    for k, label in (("C1", "C1 stake=100, share=0.1"), ("C2", "C2 stake=300, share=0.3"), ("C3", "C3 stake=600, share=0.6")):
        ax.plot(checkpoints, series[k], color=colors[k], label=label)
        ax.axhline(expected[k], color=colors[k], linestyle="--", linewidth=1, alpha=0.7)
    ax.set_xscale("log")
    ax.set_xlabel("Served slots")
    ax.set_ylabel("Service share")
    ax.set_title("WRR service share vs stake ratio (eq. 1)")
    ax.set_ylim(0, 0.75)
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)
    _save(fig, "fig1_wrr_convergence.png")


def plot_avrf_hist() -> None:
    reps = {"M1": 20.0, "M2": 50.0, "M3": 80.0}
    n = 100_000
    counts = Counter(avrf_select(reps, b"fig2", i) for i in range(n))
    labels = ["M1\nrep=20", "M2\nrep=50", "M3\nrep=80"]
    keys = ["M1", "M2", "M3"]
    freq = [counts[k] / n for k in keys]
    expected = [reps[k] / sum(reps.values()) for k in keys]

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    x = np.arange(3)
    ax.bar(x - 0.18, freq, width=0.36, color="#4C6EF5", label="AVRF frequency (N=1e5)")
    ax.bar(x + 0.18, expected, width=0.36, color="#ADB5BD", label="Expected = rep / sum(rep)")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Selection probability")
    ax.set_title("Reputation-weighted miner selection (eq. 5)")
    ax.set_ylim(0, 0.7)
    ax.legend(frameon=False)
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, "fig2_avrf_hist.png")


def plot_attacks() -> None:
    # Panel A: no-pass rejection
    rejected = ProtocolEngine()
    rejected.add_client("Sybil", balance=0)
    rejected.add_miner("M1")
    reject_n = sum(1 for _ in range(50) if not rejected.put("Sybil").accepted)

    # Panel B: designate-miner leakage
    des = ProtocolEngine(seed=b"fig3-des")
    des.add_client("C1", balance=500)
    des.lock_tokens("C1", 500)
    for mid, rep in (("M1", 20.0), ("M2", 50.0), ("M3", 80.0)):
        des.add_miner(mid, reputation=rep)
    picks = Counter()
    for _ in range(400):
        order = des.put("C1", requested_miner="M1")
        picks[order.miner_id] += 1

    # Panel C: malicious rating vs honest majority
    ban = ProtocolEngine(seed=b"fig3-ban")
    for cid in ("H1", "H2", "Attacker"):
        ban.add_client(cid, balance=200)
        ban.lock_tokens(cid, 200)
    ban.add_miner("Target", reputation=50.0)
    reps = [ban.miners["Target"].reputation]
    for cid in ("H1", "H2"):
        order = ban.put(cid)
        ban.rate(order.order_id, Rating.GOOD)
        reps.append(ban.miners["Target"].reputation)
    att = ban.put("Attacker")
    banned = not ban.rate(att.order_id, Rating.BAD)
    reps.append(ban.miners["Target"].reputation)

    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.8))

    axes[0].bar(["Accepted", "Rejected"], [50 - reject_n, reject_n], color=["#2F9E44", "#E03131"])
    axes[0].set_title("No lock / no pass")
    axes[0].set_ylabel("Requests (50)")
    axes[0].set_ylim(0, 55)

    axes[1].bar(["M1 (requested)", "M2", "M3"], [picks["M1"], picks["M2"], picks["M3"]], color="#4C6EF5")
    axes[1].set_title("Designate-miner ignored by AVRF")
    axes[1].set_ylabel("Assignments (400)")

    axes[2].plot(range(len(reps)), reps, marker="o", color="#F08C00")
    axes[2].set_title("Malicious BAD dropped; reputation stays high")
    axes[2].set_xlabel("After honest GOOD, GOOD, attacker BAD")
    axes[2].set_ylabel("Target reputation")
    axes[2].set_ylim(40, 100)
    axes[2].text(len(reps) - 1.2, reps[-1] - 8, "banned" if banned else "applied", color="#E03131")

    for ax in axes:
        ax.grid(True, axis="y", alpha=0.3)

    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / "fig3_attacks.png", dpi=160)
    plt.close(fig)


def write_tables() -> None:
    TAB.mkdir(parents=True, exist_ok=True)
    from deai.reward import split_rewards

    contrib = {"M1": 7.0, "M2": 7.0, "M3": 6.0}
    rewards = split_rewards(contrib, 100.0)
    lines = ["miner,contribution,reward"]
    for k in contrib:
        lines.append(f"{k},{contrib[k]},{rewards[k]:.6f}")
    (TAB / "reward_conservation.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    plot_wrr_convergence()
    plot_avrf_hist()
    plot_attacks()
    write_tables()
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "plot_proof_feedback", ROOT / "scripts" / "plot_proof_feedback.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    mod.plot()
    print(f"wrote figures to {FIG}")
    print(f"wrote tables to {TAB}")
