"""Build the evaluation sheet (Week 3 brief) from a results run.

    .venv/bin/python -m evals.make_sheet --run baseline

Overview metrics are Excel formulas over the Evaluation sheet, so they update if a reviewer
changes a Result. Excel and Numbers calculate them when the file is opened.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

from app.pipeline import documents

HERE = Path(__file__).resolve().parent
OUT = HERE / "casino-knowledge-assistant-evaluation.xlsx"
CATEGORIES = {
    "simple": "Simple", "section": "Specific section", "wording": "Different wording",
    "confusable": "Similar policies", "spread": "Spread across sections", "outdated": "Outdated version exists",
    "missing": "Answer not in documents", "restricted": "Restricted document",
}
COLUMNS = [  # (header, width)
    ("ID", 6), ("Category", 18), ("Role", 11), ("Question", 38), ("Expected Answer", 42), ("Correct Document", 34),
    ("Expected outcome", 13), ("AI Answer", 60), ("AI outcome", 13), ("Cited Source", 30), ("Correct Source?", 11),
    ("Right section retrieved?", 12), ("Access leak?", 10), ("Result", 9), ("Reason", 30), ("Response time (s)", 10),
    ("Human check", 12), ("Reviewer note", 30),
]
NAVY, GOLD = "0F2A44", "C8A24A"
F = lambda **kw: Font(name="Arial", **kw)
THIN = Border(bottom=Side(style="thin", color="E3E8EF"))


def yes_no(v: str) -> str:
    return {"True": "Yes", "False": "No"}.get(v, "n/a")


def build(run: str) -> Path:
    rows = list(csv.DictReader(open(HERE / "results" / f"{run}.csv")))
    summary = json.loads((HERE / "results" / f"{run}.json").read_text())
    titles = {d.doc_id: (d.meta["title"], d.meta["version"]) for d in documents.load_all()}

    def doc_label(ref: str) -> str:
        doc_id, section = ref.split("#")
        title, version = titles[doc_id]
        return f"{title} v{version}, §{section}" if section else f"{title} v{version}"

    wb = Workbook()
    ov = wb.active
    ov.title = "Overview"
    ev = wb.create_sheet("Evaluation")

    # --- Evaluation sheet -------------------------------------------------------------------------
    for c, (h, w) in enumerate(COLUMNS, 1):
        cell = ev.cell(1, c, h)
        cell.font, cell.fill = F(bold=True, color="FFFFFF"), PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ev.column_dimensions[cell.column_letter].width = w
    ev.row_dimensions[1].height = 32
    for r, row in enumerate(rows, 2):
        values = [
            row["id"], CATEGORIES[row["category"]], row["role"], row["question"], row["expected_answer"],
            "\n".join(doc_label(s) for s in row["expected_sources"].split("; ") if s) or "None (not covered or not allowed)",
            "Answer" if row["expect"] == "found" else "No answer",
            row["ai_answer"], "Answered" if row["status"] == "found" else "Not enough info",
            "\n".join(doc_label(s) for s in row["cited"].split("; ") if s),
            yes_no(row["citation_ok"]), yes_no(row["retrieval_ok"]), "Yes" if row["leak"] else "No",
            "Pass" if row["passed"] == "True" else "Fail", row["reason"], float(row["seconds"]), None, None,
        ]
        for c, v in enumerate(values, 1):
            cell = ev.cell(r, c, v)
            cell.font, cell.border = F(size=10), THIN
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    last = len(rows) + 1
    ev.freeze_panes = "E2"
    ev.auto_filter.ref = f"A1:R{last}"
    for col in "KLN":
        rng = f"{col}2:{col}{last}"
        ev.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Pass"'], fill=PatternFill("solid", fgColor="E7F5EE")))
        ev.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Yes"'], fill=PatternFill("solid", fgColor="E7F5EE")))
        ev.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Fail"'], fill=PatternFill("solid", fgColor="FDECEC")))
        ev.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"No"'], fill=PatternFill("solid", fgColor="FDECEC")))
    dv = DataValidation(type="list", formula1='"Agree,Disagree"', allow_blank=True)
    ev.add_data_validation(dv)
    dv.add(f"Q2:Q{last}")
    for r in range(2, last + 1):
        ev.cell(r, 17).fill = PatternFill("solid", fgColor="FFF9E6")  # reviewer input cells
        ev.cell(r, 18).fill = PatternFill("solid", fgColor="FFF9E6")

    # --- Overview sheet ---------------------------------------------------------------------------
    E = lambda col: f"Evaluation!${col}$2:${col}${last}"
    ov.column_dimensions["A"].width, ov.column_dimensions["B"].width, ov.column_dimensions["C"].width = 34, 16, 62
    ov["A1"] = "Casino Employee Knowledge Assistant: Evaluation"
    ov["A1"].font = F(bold=True, size=16, color=NAVY)
    ov["A2"] = ("32 test questions run through the assistant and marked automatically against key facts, the correct "
                "policy section and access rules. Reviewers can confirm each mark in the Human check column (yellow).")
    ov["A2"].alignment = Alignment(wrap_text=True)
    ov.merge_cells("A2:C2")
    ov.row_dimensions[2].height = 42

    def heading(r, text):
        ov.cell(r, 1, text).font = F(bold=True, size=12, color=NAVY)
        ov.cell(r, 1).border = Border(bottom=Side(style="medium", color=GOLD))

    heading(4, "Run settings")
    settings = [("Run", summary["name"]), ("Date", summary["run_at"]), ("AI model", summary["model"]),
                ("Prompt", summary["prompt"]), ("Chunking", summary["method"]), ("Passages retrieved (top k)", summary["k"]),
                ("Minimum match score", summary["min_score"]), ("Cost of run (USD)", summary["cost_usd"])]
    for i, (k, v) in enumerate(settings, 5):
        ov.cell(i, 1, k).font = F()
        ov.cell(i, 2, v).font = F(color="0000FF")  # recorded by evals/run_eval.py, not calculated here
    ov.cell(5, 3, "Recorded by evals/run_eval.py for this run").font = F(italic=True, color="7A8899", size=9)

    heading(14, "Results")
    metrics = [
        ("Questions", f"=COUNTA({E('A')})", "0", "All questions in the Evaluation sheet"),
        ("Answer accuracy", f'=COUNTIF({E("N")},"Pass")/COUNTA({E("A")})', "0.0%", "Result = Pass: right outcome, key facts present, no outdated rule, no leak"),
        ("Retrieval accuracy", f'=COUNTIF({E("L")},"Yes")/COUNTIF({E("G")},"Answer")', "0.0%", "Questions with an answer where a correct section was among the passages found"),
        ("Correct citation", f'=COUNTIF({E("K")},"Yes")/COUNTIF({E("G")},"Answer")', "0.0%", "Questions with an answer where the answer cited a correct section"),
        ("Unsupported answer rate", f'=COUNTIFS({E("G")},"No answer",{E("I")},"Answered")/COUNTIF({E("G")},"No answer")', "0.0%", "Answered when it should have said there isn't enough information (lower is better)"),
        ("Missed answer rate", f'=COUNTIFS({E("G")},"Answer",{E("I")},"Not enough info")/COUNTIF({E("G")},"Answer")', "0.0%", "Said not enough information when the policies do answer it (lower is better)"),
        ("Access leaks", f'=COUNTIF({E("M")},"Yes")', "0", "Restricted document found or cited for a role that may not see it (must be 0)"),
        ("Average response time (s)", f"=AVERAGE({E('P')})", "0.00", "Question to answer, including search and AI"),
        ("Slowest response (s)", f"=MAX({E('P')})", "0.00", ""),
        ("Human checks done", f'=COUNTA({E("Q")})', "0", "Rows where a reviewer chose Agree or Disagree"),
        ("Human disagreements", f'=COUNTIF({E("Q")},"Disagree")', "0", "Automatic marks a reviewer overruled"),
    ]
    for i, (label, formula, fmt, note) in enumerate(metrics, 15):
        ov.cell(i, 1, label).font = F(bold=True)
        cell = ov.cell(i, 2, formula)
        cell.font, cell.number_format = F(), fmt
        ov.cell(i, 3, note).font = F(size=9, color="5B6B7F")

    heading(28, "Results by category")
    ov.cell(29, 1, "Category").font = F(bold=True)
    ov.cell(29, 2, "Passed").font = F(bold=True)
    ov.cell(29, 3, "Of").font = F(bold=True)
    for i, label in enumerate(CATEGORIES.values(), 30):
        ov.cell(i, 1, label).font = F()
        ov.cell(i, 2, f'=COUNTIFS({E("B")},A{i},{E("N")},"Pass")').font = F()
        ov.cell(i, 3, f'=COUNTIF({E("B")},A{i})').font = F()
        ov.cell(i, 3).alignment = Alignment(horizontal="left")
    exp_path = HERE / "results" / "experiments.csv"
    if exp_path.exists():
        add_experiments(wb, list(csv.DictReader(open(exp_path))))
    wb.save(OUT)
    return OUT


def add_experiments(wb, runs: list[dict]) -> None:
    """One row per experiment run (values recorded by evals/run_experiments.py)."""
    ws = wb.create_sheet("Experiments")
    ws["A1"] = "RAG experiments: same 32 questions, one setting changed at a time"
    ws["A1"].font = F(bold=True, size=14, color=NAVY)
    ws["A2"] = "Full write-up: docs/casino-knowledge-assistant-07-experiment-results.md"
    ws["A2"].font = F(italic=True, color="5B6B7F")
    headers = [("Chunks", 12), ("Top k", 7), ("Version filter", 10), ("Answer accuracy", 11), ("Retrieval accuracy", 11),
               ("Correct citation", 11), ("Unsupported answers", 12), ("Access leaks", 9), ("Avg time (s)", 9),
               ("Avg answer words", 10), ("Cost (USD)", 10)]
    for c, (h, w) in enumerate(headers, 1):
        cell = ws.cell(4, c, h)
        cell.font, cell.fill = F(bold=True, color="FFFFFF"), PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[cell.column_letter].width = w
    ws.row_dimensions[4].height = 30
    for r, run in enumerate(runs, 5):
        values = [run["method"], int(run["k"]), "On" if run["version_filter"] == "True" else "Off",
                  float(run["answer_accuracy_pct"]) / 100, float(run["retrieval_accuracy_pct"]) / 100,
                  float(run["correct_citation_pct"]) / 100, float(run["unsupported_answer_rate_pct"]) / 100,
                  int(run["access_leaks"]), float(run["avg_seconds"]), float(run["avg_answer_words"]), float(run["cost_usd"])]
        for c, v in enumerate(values, 1):
            cell = ws.cell(r, c, v)
            cell.font, cell.border = F(color="0000FF"), THIN
            if c in (4, 5, 6, 7):
                cell.number_format = "0.0%"
            if c == 11:
                cell.number_format = "$0.0000"
        if run["method"] == "section" and run["k"] == "5" and run["version_filter"] == "True":
            for c in range(1, len(values) + 1):
                ws.cell(r, c).fill = PatternFill("solid", fgColor="FBF4E2")
    note = len(runs) + 6
    ws.cell(note, 1, "Highlighted row = settings used by the app (section chunks, top 5, version filter on). "
                     "Values recorded by evals/run_experiments.py.").font = F(italic=True, size=9, color="5B6B7F")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="baseline")
    print(build(ap.parse_args().run))
