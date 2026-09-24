from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import csv

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
TAB = ROOT / "tables"
CSV = TAB / "pbft_results.csv"
PAPER_TPS = 1000.0


def load() -> list[dict]:
    rows = []
    with CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def num(row: dict, key: str) -> float:
    return float(row[key])


def plot(rows: list[dict]) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    zero = [r for r in rows if r["loss"] == "0.00" and r["byzantine"] == "0"]
    loss50 = [r for r in rows if r["n"] == "50" and r["byzantine"] == "0"]

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    xs = [int(r["n"]) for r in zero]
    ys = [num(r, "tps") for r in zero]
    ax.plot(xs, ys, marker="o", color="#4C6EF5", label="Measured task cycle/s (0% loss)")
    ax.set_xlabel("Coordinator nodes")
    ax.set_ylabel("Committed task cycles / s")
    ax.set_title("PBFT ledger throughput vs coordinator count")
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig5_tps_vs_nodes.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    xs = [num(r, "loss") * 100 for r in loss50]
    tps = [num(r, "tps") for r in loss50]
    p99 = [num(r, "p99_ms") for r in loss50]
    ax.plot(xs, tps, marker="o", color="#4C6EF5", label="Throughput (cycle/s)")
    ax.set_xlabel("Packet loss (%)")
    ax.set_ylabel("Committed task cycles / s")
    ax.set_title("50 coordinators: throughput vs packet loss")
    ax.grid(True, alpha=0.3)
    ax2 = ax.twinx()
    ax2.plot(xs, p99, marker="s", color="#F08C00", label="p99 latency (ms)")
    ax2.set_ylabel("p99 latency (ms)")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig6_tps_vs_loss.png", dpi=160)
    plt.close(fig)

    n50 = next(r for r in rows if r["n"] == "50" and r["loss"] == "0.00" and r["byzantine"] == "0")
    measured = num(n50, "tps")
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.bar(["This run (50 nodes, 0% loss)", "Li (2023) cited ~1000"], [measured, PAPER_TPS], color=["#4C6EF5", "#ADB5BD"])
    ax.set_ylabel("Task cycles / s")
    ax.set_title("Measured PBFT throughput vs paper citation")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "fig7_tps_vs_paper.png", dpi=160)
    plt.close(fig)

    lines = ["n,loss,byzantine,honest_agree,honest_len,hash,committed"]
    for r in rows:
        lines.append(
            f"{r['n']},{r['loss']},{r['byzantine']},{r['honest_agree']},{r['honest_len']},{r['hash']},{r['committed']}"
        )
    (TAB / "pbft_safety.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote fig5-7 and pbft_safety.csv")


if __name__ == "__main__":
    plot(load())
