"""Answer step safety nets (D5), tested with a fake AI so no key or network is needed."""
from datetime import date

import pytest

from app.pipeline import answer, documents, llm, store
from app.pipeline.llm import Reply, Usage

TODAY = date(2026, 11, 6)


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    path = tmp_path_factory.mktemp("vectorstore")
    store.build_index(documents.load_folder(), "section", path)
    return path


def fake(reply):
    calls = []

    def complete(system, user):
        calls.append(user)
        return reply, Usage("fake", 100, 20)
    complete.calls = calls
    return complete


def ask(index, q, ai, **kw):
    return answer.ask(q, today=TODAY, path=index, complete=ai, **kw)


Q = "How much annual leave can I carry forward?"


def test_found_answer_shows_the_real_policy_text_as_source(index):
    ai = fake(Reply(status="found", answer="Up to 8 days, used by 30 June.", source_ids=["P1"]))
    a = ask(index, Q, ai)
    assert a.found and a.text == "Up to 8 days, used by 30 June."
    assert a.sources[0].chunk_id == "HR-LEAVE-2026#5"
    assert "up to 8 days" in a.sources[0].text  # stored policy text, not AI text
    assert "[P1] Annual Leave Policy (v2026.1" in ai.calls[0]


def test_no_close_match_never_calls_the_ai(index):
    ai = fake(Reply(status="found", answer="Invented", source_ids=["P1"]))
    a = ask(index, Q, ai, min_score=0.99)
    assert not a.found and a.reason == "no_close_match" and ai.calls == []
    assert a.text == answer.NOT_FOUND_MESSAGE


def test_ai_not_found_gives_the_standard_message(index):
    a = ask(index, "How much maternity pay do I get?", fake(Reply(status="not_found", answer="Not covered.", source_ids=[])))
    assert not a.found and a.reason == "ai_not_found" and a.sources == []


@pytest.mark.parametrize("ids", [[], ["P99"], ["made-up"]])
def test_found_without_a_real_retrieved_source_is_not_shown(index, ids):
    a = ask(index, Q, fake(Reply(status="found", answer="Invented rule", source_ids=ids)))
    assert not a.found and a.reason == "no_valid_source" and "Invented" not in a.text


def test_bad_citations_are_dropped_and_duplicates_merged(index):
    a = ask(index, Q, fake(Reply(status="found", answer="x", source_ids=["[P2]", "P9", "P2", "P1"])))
    assert [h.chunk_id for h in a.sources] == [a.retrieved[1].chunk_id, a.retrieved[0].chunk_id]


def test_unusable_ai_reply_is_treated_as_not_found(index):
    a = ask(index, Q, fake(None))
    assert not a.found and a.reason == "no_valid_reply"


def test_restricted_passages_are_never_sent_to_the_ai(index):
    ai = fake(Reply(status="not_found", answer="", source_ids=[]))
    ask(index, "Can I be suspended during a disciplinary investigation?", ai, role="Employee")
    assert ai.calls and "Disciplinary Investigation Procedure" not in ai.calls[0]


def test_old_policy_is_never_sent_to_the_ai(index):
    ai = fake(Reply(status="not_found", answer="", source_ids=[]))
    ask(index, Q, ai, k=10)
    assert "v2024.1" not in ai.calls[0] and "31 March" not in ai.calls[0]


def test_mock_provider_answers_from_first_passage(index, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    a = answer.ask(Q, today=TODAY, path=index)
    assert a.found and a.sources[0].chunk_id == "HR-LEAVE-2026#5" and a.model == "mock-first-sentence"
