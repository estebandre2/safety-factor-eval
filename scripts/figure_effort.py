"""Figure for the Study II write-up: overturning error rate vs effort, base prompt vs set-up-first (exploratory E1/E2/E6).
Reads results/tables/phase1_summary.json and results/tables/explore_summary.json -> writeup/figures/effort_setup.png"""
import json
from pathlib import Path

import matplotlib.pyplot as plt

E = json.loads(Path("results/tables/explore_summary.json").read_text())
EFFORTS = ["low", "medium", "high", "max"]
MODELS = [("claude-haiku-5-5", "Haiku"), ("claude-sonnet-5-5", "Sonnet"), ("claude-opus-5-5", "Opus")]
BASE, SETUP, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1a1a19", "#6b6a63", "#e6e5e0"

fig, axes = plt.subplots(1, 3, figsize=(9, 3.1), sharey=True)
for ax, (key, name) in zip(axes, MODELS):
    base = [E["E1"][key][e]["rate"] * 100 for e in EFFORTS]
    setup = [E["E6"][key]["low"]["rate"] * 100, E["E6"][key]["medium"]["rate"] * 100, E["E2"][key]["rate"] * 100]
    ax.plot(range(4), base, color=BASE, lw=2, marker="o", ms=6, mec="white", mew=1.5, label="Base prompt")
    ax.plot(range(3), setup, color=SETUP, lw=2, marker="s", ms=6, mec="white", mew=1.5, label="Set-up first")
    ax.set_title(name, color=INK, fontsize=11, loc="left")
    ax.set_xticks(range(4), EFFORTS, color=MUTED, fontsize=9)
    ax.set_ylim(-3, 85)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.tick_params(colors=MUTED, length=0, labelsize=9)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.annotate(f"{base[0]:.0f}%", (0, base[0]), textcoords="offset points", xytext=(6, 4), fontsize=8, color=INK)
    ax.annotate(f"{setup[0]:.0f}%", (0, setup[0]), textcoords="offset points", xytext=(7, 5), fontsize=8, color=INK)
axes[0].set_ylabel("Wrong overturning values (%)", color=MUTED, fontsize=9)
axes[0].legend(frameon=False, fontsize=8.5, loc="upper right", labelcolor=INK)
fig.suptitle("Error by reasoning effort, 80 dams (exploratory E1, E2, E6)", x=0.01, ha="left", fontsize=11, color=INK)
fig.tight_layout()
out = Path("writeup/figures/effort_setup.png")
fig.savefig(out, dpi=200, facecolor="white")
print(out)
