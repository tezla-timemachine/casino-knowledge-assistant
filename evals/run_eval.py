"""Run the evaluation questions through the assistant and score them.

    .venv/bin/python -m evals.run_eval --name baseline              # section chunks, top 5
    .venv/bin/python -m evals.run_eval --method small --k 3 --name small-top3

Each run calls the AI once per question (except clear misses). With Claude Haiku 5.5, 32 questions
cost well under 1p. Results go to evals/results/<name>.csv and <name>.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import date
from pathlib import Path

from app.pipeline import answer, documents, llm, store
from evals import scoring

RESULTS_DIR = Path(__file__).resolve().parent / "results"
PRICES = {"claude-haiku-5-5": (0.10, 0.50)}  # $ per million input / output tokens


def run(method: str = "section", k: int = store.TOP_K, name: str = "baseline", min_score: float = answer.MIN_SCORE,
        today: date | None = None, apply_version_filter: bool = True) -> dict:
    store.ensure_index(documents.load_all(), method)
    rows, tokens_in, tokens_out = [], 0, 0
    for q in scoring.load_questions():
        a = answer.ask(q["question"], role=q["role"], k=k, method=method, today=today, min_score=min_score,
                       apply_version_filter=apply_version_filter)
        tokens_in += a.input_tokens
        tokens_out += a.output_tokens
        marks = scoring.mark(q, a)
        rows.append({
            "id": q["id"], "category": q["category"], "role": q["role"], "question": q["question"],
            "expected_answer": q["expected_answer"], "expected_sources": "; ".join(q["sources"]), "expect": q["expect"],
            "status": a.status, "reason_code": a.reason, "ai_answer": a.text,
            "cited": "; ".join(f"{h.doc_id}#{h.section}" for h in a.sources),
            "retrieved": "; ".join(f"{h.doc_id}#{h.section} ({h.score:.2f})" for h in a.retrieved),
            "seconds": a.seconds, **marks,
        })
        print(f"{q['id']} {'PASS' if marks['passed'] else 'FAIL'} {a.seconds:>5.2f}s  {marks['reason']}")
    price = PRICES.get(llm.model_name(), (0, 0))
    summary = {"name": name, "method": method, "k": k, "min_score": min_score, "version_filter": apply_version_filter,
               "model": llm.model_name(),
               "prompt": answer.PROMPT_VERSION, "run_at": time.strftime("%Y-%m-%d %H:%M"),
               **scoring.summarise(rows), "input_tokens": tokens_in, "output_tokens": tokens_out,
               "cost_usd": round(tokens_in / 1e6 * price[0] + tokens_out / 1e6 * price[1], 4)}
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(RESULTS_DIR / f"{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (RESULTS_DIR / f"{name}.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="section", choices=["section", "small", "large"])
    ap.add_argument("--k", type=int, default=store.TOP_K)
    ap.add_argument("--name", default="baseline")
    ap.add_argument("--min-score", type=float, default=answer.MIN_SCORE)
    args = ap.parse_args()
    if llm.provider() != "anthropic":
        print("Warning: LLM_PROVIDER is not anthropic, so these results are NOT AI results.")
    s = run(args.method, args.k, args.name, args.min_score)
    print(json.dumps({k: v for k, v in s.items() if k != "by_category"}, indent=2))
    print("By category:", s["by_category"])
