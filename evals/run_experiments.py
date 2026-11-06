"""RAG experiments (Week 3 brief): chunk size, top 3 vs top 5, and what happens without the version filter.

    .venv/bin/python -m evals.run_experiments

Runs the 32 evaluation questions 7 times (about 1p in total with Claude Haiku 5.5) and writes
evals/results/experiments.csv. Each run's details are in evals/results/exp-*.csv.
"""
import csv

from app.pipeline import documents, store
from evals import run_eval

GRID = [(method, k) for method in ("small", "section", "large") for k in (3, 5)]

if __name__ == "__main__":
    docs = documents.load_all()
    for method in ("small", "section", "large"):
        store.ensure_index(docs, method)
    summaries = []
    for method, k in GRID:
        print(f"\n=== {method} chunks, top {k} ===")
        summaries.append(run_eval.run(method, k, name=f"exp-{method}-k{k}"))
    print("\n=== section chunks, top 5, NO version filter ===")
    summaries.append(run_eval.run("section", 5, name="exp-no-version-filter", apply_version_filter=False))
    cols = ["name", "method", "k", "version_filter", "answer_accuracy_pct", "retrieval_accuracy_pct", "correct_citation_pct",
            "unsupported_answer_rate_pct", "missed_answer_rate_pct", "access_leaks", "avg_seconds", "avg_answer_words",
            "avg_sources_cited", "input_tokens", "cost_usd", "by_category"]
    with open(run_eval.RESULTS_DIR / "experiments.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(summaries)
    for s in summaries:
        print(f"{s['name']:24} acc {s['answer_accuracy_pct']:5}  retr {s['retrieval_accuracy_pct']:5}  "
              f"cite {s['correct_citation_pct']:5}  words {s['avg_answer_words']}  {s['avg_seconds']}s  ${s['cost_usd']}")
