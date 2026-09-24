from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
TAB = ROOT / "tables"


def main() -> None:
    rows = []
    for line in (TAB / "onchain_weights.csv").read_text(encoding="utf-8").strip().splitlines()[1:]:
        client, weight, wrr, _ = line.split(",")
        rows.append((client, int(weight), int(wrr)))

    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6))
    clients = [r[0] for r in rows]
    weights = [r[1] for r in rows]
    wrr = [r[2] for r in rows]
    axes[0].bar(clients, weights, color="#4C6EF5")
    axes[0].set_title("On-chain effective stake (weightOf)")
    axes[0].set_ylabel("Token units")
    axes[1].bar(clients, wrr, color="#2F9E44")
    axes[1].set_title("WRR weights from chain (eq. 1)")
    axes[1].set_ylabel("w = floor(s / s_min)")
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.3)
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_stake_events.png", dpi=160)
    plt.close(fig)
    print(f"wrote {FIG / 'fig4_stake_events.png'}")


if __name__ == "__main__":
    main()
