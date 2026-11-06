"""Draws the architecture diagram (PNG) for the product document.

    python docs/casino-knowledge-assistant-04-make-architecture-diagram.py   # needs matplotlib
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).with_name("casino-knowledge-assistant-04-architecture-diagram.png")
NAVY, GOLD, TEAL, GREEN, AMBER, GREY = "#0F2A44", "#C8A24A", "#1F7A8C", "#146C43", "#B26B00", "#5B6B7F"
FILL = {NAVY: "#E8EEF5", GOLD: "#FBF4E2", TEAL: "#E3F2F5", GREEN: "#E7F5EE", AMBER: "#FFF4E0"}
TITLE = {GOLD: "#7A5B12"}  # darker gold so titles are readable on the light fill
X = [1.7, 5.0, 8.3, 11.6, 14.9, 18.2]   # column centres
W, H = 2.9, 1.55
ROW_A, ROW_B, ROW_C = 7.4, 4.3, 1.5

fig, ax = plt.subplots(figsize=(20, 10.5), dpi=110)
ax.set_xlim(0, 19.9)
ax.set_ylim(0, 10.5)
ax.axis("off")


def box(x, y, title, body, color):
    ax.add_patch(FancyBboxPatch((x - W / 2, y - H / 2), W, H, boxstyle="round,pad=0.02,rounding_size=0.18",
                                linewidth=2, edgecolor=color, facecolor=FILL[color]))
    ax.text(x, y + 0.42, title, ha="center", va="center", fontsize=11.5, fontweight="bold", color=TITLE.get(color, color))
    ax.text(x, y - 0.18, body, ha="center", va="center", fontsize=9.2, color="#1B2430", linespacing=1.35)


def arrow(p, q, label="", color=GREY, dy=0.18):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=16, linewidth=1.6, color=color))
    if label:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + dy, label, ha="center", fontsize=9, color=color, style="italic")


ax.text(0.2, 10.05, "Harbourlight Policy Assistant: architecture", fontsize=18, fontweight="bold", color=NAVY)
ax.text(0.2, 9.6, "Documents → Processing → Chunking → Embeddings → Vector database → Retrieval → LLM → Answer + source",
        fontsize=11, color=GREY)
ax.text(0.2, ROW_A + 1.12, "PREPARING DOCUMENTS  (when a policy is added, replaced or changed)", fontsize=10, fontweight="bold", color=GREY)
ax.text(0.2, ROW_B + 1.12, "ANSWERING A QUESTION", fontsize=10, fontweight="bold", color=GREY)

# Row A: preparing documents
box(X[0], ROW_A, "Policy documents", "Markdown, PDF, Word\nheader: version, status, effective\ndate, department, access level", NAVY)
box(X[1], ROW_A, "Load and check", "Header required, or the\ndocument is rejected;\nnew versions supersede old", GOLD)
box(X[2], ROW_A, "Chunk by section", "One passage per numbered\nsection, labelled with policy\ntitle and section heading", NAVY)
box(X[3], ROW_A, "Embeddings", "all-MiniLM-L6-v2\nruns on our machine\n(free, no text sent out)", NAVY)
box(X[4], ROW_A, "Vector database", "Chroma (local)\npassages + numbers +\nheader for filtering", NAVY)
for i in range(4):
    arrow((X[i] + W / 2, ROW_A), (X[i + 1] - W / 2, ROW_A))

# Row B: answering
box(X[0], ROW_B, "Employee question", "in their own words\n+ role (Employee, HR,\nCompliance)", NAVY)
box(X[1], ROW_B, "Filter before search", "only current versions,\nalready in effect, and\nallowed for this role", GOLD)
box(X[2], ROW_B, "Retrieve", "top 5 passages\nclosest in meaning\nto the question", NAVY)
box(X[3], ROW_B, "Close enough?", "best match ≥ 0.30\n(safety net 1)", GOLD)
box(X[4], ROW_B, "Claude Haiku 5.5", "answers only from the\npassages; replies found /\nnot found + passage IDs", TEAL)
box(X[5], ROW_B, "Check citations", "cited passages must have\nbeen retrieved\n(safety net 2)", GOLD)
for i in range(5):
    arrow((X[i] + W / 2, ROW_B), (X[i + 1] - W / 2, ROW_B), "Yes" if i == 3 else "")

# Vector database feeds retrieval (elbow)
mid = (ROW_A + ROW_B) / 2 + 0.05
ax.plot([X[4], X[4], X[2]], [ROW_A - H / 2, mid, mid], color=GREY, linewidth=1.6)
arrow((X[2], mid), (X[2], ROW_B + H / 2))

# Row C: outcomes
box(X[3], ROW_C, "Not enough information", "clear reply, points to HR;\nalso used if Claude says not\nfound or cites nothing real", AMBER)
box(X[5], ROW_C, "Answer + source", "answer, policy, version,\neffective date, section and\nthe exact policy text", GREEN)
arrow((X[3], ROW_B - H / 2), (X[3], ROW_C + H / 2), color=AMBER)
ax.text(X[3] + 0.25, (ROW_B + ROW_C) / 2, "No", fontsize=9, color=AMBER, style="italic")
arrow((X[5], ROW_B - H / 2), (X[5], ROW_C + H / 2))

# Legend and data note
lx, ly = 0.3, 1.9
for i, (c, label) in enumerate([(NAVY, "Code on our machine"), (GOLD, "Safety control"),
                                (TEAL, "AI call (Anthropic API)"), (GREEN, "Answer shown"), (AMBER, "No answer shown")]):
    ax.add_patch(FancyBboxPatch((lx, ly - i * 0.42), 0.32, 0.26, boxstyle="round,pad=0.01", facecolor=FILL[c], edgecolor=c, linewidth=1.5))
    ax.text(lx + 0.5, ly - i * 0.42 + 0.13, label, va="center", fontsize=9.5, color="#1B2430")
ax.text(3.3, 1.2, "Only the question and the 5 retrieved passages\nare sent to the AI. Superseded and restricted\n"
                  "text is removed before the search, so it never\nreaches the AI or the screen.",
        fontsize=9.5, color=GREY, linespacing=1.5)

fig.savefig(OUT, bbox_inches="tight", facecolor="white")
print(OUT)
