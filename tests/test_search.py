"""Search filters (D7, D8). Uses a temporary index so the real one is never touched."""
from datetime import date

import pytest

from app.pipeline import documents, store

TODAY = date(2026, 11, 6)
DOCS = documents.load_folder()


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    path = tmp_path_factory.mktemp("vectorstore")
    store.build_index(DOCS, "section", path)
    return path


def ask(index, q, role="Employee", k=10, **kw):
    return store.search(q, role=role, k=k, today=kw.pop("today", TODAY), path=index, **kw)


def test_current_leave_policy_is_found_and_old_one_never_is(index):
    hits = ask(index, "How much annual leave can I carry forward?")
    ids = [h.chunk_id for h in hits]
    assert "HR-LEAVE-2026#5" in ids[:3]
    assert not any(h.doc_id == "HR-LEAVE-2024" for h in hits)


def test_renamed_successor_replaces_old_hybrid_policy(index):
    hits = ask(index, "How many days a week can I work from home?")
    assert hits[0].doc_id == "HR-WORKPLACE-2025"
    assert not any(h.doc_id == "HR-HYBRID-2023" for h in hits)


def test_without_version_filter_old_policy_does_appear(index):
    """Shows why the filter is needed (experiments only; the app never turns it off)."""
    hits = ask(index, "Can I roll over unused holiday into next year?", apply_version_filter=False)
    assert any(h.doc_id == "HR-LEAVE-2024" for h in hits)


def test_policy_not_yet_in_effect_is_not_searched(index):
    hits = ask(index, "How much annual leave can I carry forward?", today=date(2025, 12, 31))
    assert not any(h.doc_id.startswith("HR-LEAVE") for h in hits)  # 2024 superseded, 2026 not yet in effect


@pytest.mark.parametrize("role, restricted, visible", [
    ("Employee", ["HR-DISC-INV-2025", "COMP-AML-INV-2025"], []),
    ("HR", ["COMP-AML-INV-2025"], ["HR-DISC-INV-2025"]),
    ("Compliance", ["HR-DISC-INV-2025"], ["COMP-AML-INV-2025"]),
])
def test_roles_only_see_their_documents(index, role, restricted, visible):
    seen = set()
    for q in ["How long does a disciplinary investigation take?", "When must the MLRO decide on a SAR?",
              "Can I be suspended during an investigation?", "How long are SAR records kept?"]:
        seen |= {h.doc_id for h in ask(index, q, role=role, k=20)}
    assert not seen & set(restricted)
    assert set(visible) <= seen


def test_hits_carry_a_readable_citation(index):
    hit = ask(index, "How much annual leave can I carry forward?", k=1)[0]
    assert hit.citation == "Annual Leave Policy (v2026.1, effective 1 Jan 2026), §5 Carrying leave forward"
    assert "up to 8 days" in hit.text and 0 < hit.score <= 1


def test_index_is_rebuilt_only_when_documents_change(tmp_path):
    assert store.ensure_index(DOCS, "large", tmp_path) is True
    assert store.ensure_index(DOCS, "large", tmp_path) is False
    changed = documents.load_folder()
    changed[0].meta["status"] = "superseded"
    assert store.ensure_index(changed, "large", tmp_path) is True
