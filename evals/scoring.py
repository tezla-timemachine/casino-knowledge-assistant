"""How each evaluation answer is marked. Pure functions, so the marking itself is tested.

Answer accuracy is checked automatically against key facts (must_include / must_not_include).
That is a proxy: the evaluation sheet keeps a "Human check" column so a person can confirm or overrule.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.yaml"


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    qs = yaml.safe_load(path.read_text())["questions"]
    for q in qs:
        q.setdefault("role", "Employee")
        q.setdefault("expect", "found")
        for k in ("sources", "must_include", "must_not_include", "forbidden_docs"):
            q.setdefault(k, [])
    return qs


def _section_numbers(section: str) -> set[str]:
    """'5' -> {5}; '4-6' (a fixed-size chunk spanning sections) -> {4, 5, 6}; '' -> {''}."""
    m = re.fullmatch(r"(\d+)-(\d+)", section or "")
    if m:
        return {str(n) for n in range(int(m.group(1)), int(m.group(2)) + 1)}
    return {section or ""}


def covers(doc_id: str, section: str, expected: str) -> bool:
    exp_doc, exp_section = expected.split("#")
    return doc_id == exp_doc and exp_section in _section_numbers(section)


def any_covers(hits, expected: list[str]) -> bool:
    return any(covers(h.doc_id, h.section, e) for h in hits for e in expected)


def has_fact(text: str, fact: str) -> bool:
    """'8 days|eight days' -> either wording, case-insensitive, as whole words."""
    return any(re.search(rf"(?<![\w]){re.escape(alt.strip())}(?![\w])", text, re.I) for alt in fact.split("|"))


def mark(q: dict, a) -> dict:
    """Score one answer. `a` is an answer.Answer."""
    leak = sorted({h.doc_id for h in a.retrieved + a.sources} & set(q["forbidden_docs"]))
    row = {"retrieval_ok": None, "citation_ok": None, "facts_ok": None, "leak": ", ".join(leak)}
    if q["expect"] == "not_found":
        passed = not a.found and not leak
        reason = "" if passed else ("access leak" if leak else "unsupported answer")
    else:
        row["retrieval_ok"] = any_covers(a.retrieved, q["sources"])
        row["citation_ok"] = a.found and any_covers(a.sources, q["sources"])
        missing = [f for f in q["must_include"] if not has_fact(a.text, f)]
        wrong = [f for f in q["must_not_include"] if has_fact(a.text, f)]
        row["facts_ok"] = a.found and not missing and not wrong
        passed = bool(row["facts_ok"]) and not leak
        if passed:
            reason = ""
        elif leak:
            reason = "access leak"
        elif not a.found:
            reason = "missed answer" + ("" if row["retrieval_ok"] else " (right section not retrieved)")
        elif wrong:
            reason = "used outdated or wrong rule: " + "; ".join(wrong)
        else:
            reason = "missing fact: " + "; ".join(missing)
    return {**row, "passed": passed, "reason": reason}


def summarise(rows: list[dict]) -> dict:
    answerable = [r for r in rows if r["expect"] == "found"]
    unanswerable = [r for r in rows if r["expect"] == "not_found"]
    pct = lambda n, d: round(100 * n / d, 1) if d else None
    secs = sorted(r["seconds"] for r in rows)
    found = [r for r in rows if r["status"] == "found"]
    return {
        "questions": len(rows),
        "answer_accuracy_pct": pct(sum(r["passed"] for r in rows), len(rows)),
        "retrieval_accuracy_pct": pct(sum(bool(r["retrieval_ok"]) for r in answerable), len(answerable)),
        "correct_citation_pct": pct(sum(bool(r["citation_ok"]) for r in answerable), len(answerable)),
        "unsupported_answer_rate_pct": pct(sum(r["status"] == "found" for r in unanswerable), len(unanswerable)),
        "missed_answer_rate_pct": pct(sum(r["status"] == "not_found" for r in answerable), len(answerable)),
        "access_leaks": sum(bool(r["leak"]) for r in rows),
        "avg_seconds": round(sum(secs) / len(secs), 2) if secs else None,
        "max_seconds": secs[-1] if secs else None,
        "avg_answer_words": round(sum(len(r["ai_answer"].split()) for r in found) / len(found), 1) if found else None,
        "avg_sources_cited": round(sum(len([c for c in r["cited"].split("; ") if c]) for r in found) / len(found), 2) if found else None,
        "by_category": {c: f"{sum(r['passed'] for r in rows if r['category'] == c)}/{sum(r['category'] == c for r in rows)}"
                        for c in dict.fromkeys(r["category"] for r in rows)},
    }
