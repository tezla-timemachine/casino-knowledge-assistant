"""The evaluation's marking rules, and that every question points at real policy sections."""
from app.pipeline import chunking, documents
from app.pipeline.answer import Answer
from app.pipeline.store import Hit
from evals import scoring

QS = {q["id"]: q for q in scoring.load_questions()}


def hit(doc_id, section):
    from datetime import date
    return Hit(f"{doc_id}#{section}", doc_id, "T", "1", date(2026, 1, 1), "HR", section, "S", "text", 0.5)


def ans(status, text, sources=(), retrieved=()):
    return Answer("q", status, text, status, list(sources), list(retrieved))


def test_question_set_is_valid():
    assert 25 <= len(QS) <= 35
    chunk_ids = {c.chunk_id for c in chunking.chunk_all(documents.load_folder(), "section")}
    for q in QS.values():
        assert q["expect"] in ("found", "not_found")
        assert all(s in chunk_ids for s in q["sources"]), q["id"]
        assert bool(q["sources"]) == (q["expect"] == "found"), q["id"]
        assert q["role"] in ("Employee", "HR", "Compliance")
    assert {q["category"] for q in QS.values()} >= {"simple", "section", "wording", "confusable", "missing", "outdated"}


def test_fixed_size_chunks_spanning_sections_still_count():
    assert scoring.covers("HR-LEAVE-2026", "4-6", "HR-LEAVE-2026#5")
    assert not scoring.covers("HR-LEAVE-2026", "6-7", "HR-LEAVE-2026#5")
    assert not scoring.covers("HR-LEAVE-2024", "5", "HR-LEAVE-2026#5")


def test_facts_match_whole_words_and_alternatives():
    assert scoring.has_fact("Up to eight days by 30 June", "8 days|eight days")
    assert not scoring.has_fact("Up to 28 days", "8 days")  # "28 days" is not "8 days"
    assert scoring.has_fact("costs £1,000 a year", "1,000|1000")


def test_correct_answer_passes():
    q = QS["Q23"]
    good = hit("HR-LEAVE-2026", "5")
    m = scoring.mark(q, ans("found", "Up to 8 days, used by 30 June.", [good], [good]))
    assert m["passed"] and m["retrieval_ok"] and m["citation_ok"]


def test_outdated_rule_fails_even_with_right_number():
    q = QS["Q23"]
    good = hit("HR-LEAVE-2026", "5")
    m = scoring.mark(q, ans("found", "8 days, by 30 June (or 31 March).", [good], [good]))
    assert not m["passed"] and m["reason"].startswith("used outdated")


def test_answering_a_question_with_no_answer_is_unsupported():
    m = scoring.mark(QS["Q26"], ans("found", "You get 39 weeks."))
    assert not m["passed"] and m["reason"] == "unsupported answer"
    assert scoring.mark(QS["Q26"], ans("not_found", "x"))["passed"]


def test_restricted_document_reaching_an_employee_is_a_leak():
    m = scoring.mark(QS["Q29"], ans("not_found", "x", retrieved=[hit("HR-DISC-INV-2025", "3")]))
    assert not m["passed"] and m["reason"] == "access leak"


def test_missed_answer_says_whether_retrieval_was_the_cause():
    m = scoring.mark(QS["Q24"], ans("not_found", "x", retrieved=[hit("HR-WORKPLACE-2025", "6")]))
    assert m["reason"] == "missed answer (right section not retrieved)"
