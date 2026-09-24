"""Four-round bisection on a 12-layer chain."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from deai.bisection import chain_bisection

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "fig3_4_bisection.png"

GREEN = "#2F9E44"
RED = "#E03131"
PURPLE = "#7048E8"
GREY = "#DEE2E6"
PRUNED = "#E9ECEF"
EDGE = "#343A40"
TEXT = "#212529"


def colors_at(walk, step_i: int) -> dict[str, str]:
    step = walk.steps[step_i]
    remaining = set(step.remaining)
    colors = {}
    for i in range(1, 13):
        node = f"L{i}"
        if node in step.consistent:
            colors[node] = GREEN
        elif node in step.inconsistent and node != walk.fault:
            colors[node] = RED
        elif node in remaining:
            colors[node] = GREY
        else:
            colors[node] = PRUNED
    if step_i == len(walk.steps) - 1:
        colors[walk.fault] = PURPLE
    else:
        colors[step.query] = GREEN if step.equal else RED
    return colors


def draw_chain(ax, colors: dict[str, str], title: str) -> None:
    ax.set_xlim(0.15, 12.85)
    ax.set_ylim(-0.55, 1.15)
    ax.axis("off")
    ax.set_title(title, fontsize=8, color=TEXT, pad=2, loc="left")
    for i in range(1, 13):
        node = f"L{i}"
        fc = colors[node]
        ax.add_patch(
            FancyBboxPatch(
                (i - 0.42, -0.28),
                0.84,
                0.56,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=fc,
                edgecolor=EDGE,
                linewidth=0.4,
            )
        )
        fg = "white" if fc in {GREEN, RED, PURPLE} else TEXT
        ax.text(i, 0.0, node, ha="center", va="center", fontsize=6.5, color=fg, fontweight="bold")
        if i < 12:
            ax.annotate(
                "",
                xy=(i + 0.48, 0),
                xytext=(i + 0.44, 0),
                arrowprops=dict(arrowstyle="-|>", color="#ADB5BD", lw=0.6, mutation_scale=6),
            )


def main() -> None:
    walk = chain_bisection(12, "L7")
    titles = [
        "Round 1: query L6, outputs match",
        "Round 2: query L9, outputs differ",
        "Round 3: query L8, outputs differ",
        "Round 4: L7 isolated (replay this layer only)",
    ]
    fig, axes = plt.subplots(4, 1, figsize=(6.6, 2.55))
    for ax, title, i in zip(axes, titles, range(4)):
        draw_chain(ax, colors_at(walk, i), title)
    fig.legend(
        handles=[
            plt.Rectangle((0, 0), 1, 1, fc=GREEN, ec=EDGE, lw=0.4),
            plt.Rectangle((0, 0), 1, 1, fc=RED, ec=EDGE, lw=0.4),
            plt.Rectangle((0, 0), 1, 1, fc=PURPLE, ec=EDGE, lw=0.4),
            plt.Rectangle((0, 0), 1, 1, fc=GREY, ec=EDGE, lw=0.4),
        ],
        labels=["match", "differ", "fault", "unchecked"],
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=7,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, facecolor="white")
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()
