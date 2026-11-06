from datetime import date

import pytest

from app.pipeline import chunking, documents
from app.pipeline.documents import HeaderError

DOCS = documents.load_folder()
BY_ID = {d.doc_id: d for d in DOCS}

HEADER = """---
doc_id: T-1
title: Test Policy
version: 1
department: HR
access_level: all_staff
status: current
effective_date: 2026-01-01
owner: Head of People
---
# Test Policy

## 1. First

Alpha.

## 2. Second

Beta.
"""


def test_all_policies_load_with_valid_headers():
    assert len(DOCS) == 17
    assert len(BY_ID) == 17  # doc_ids are unique


def test_sections_are_split_and_numbered():
    leave = BY_ID["HR-LEAVE-2026"]
    assert [s.number for s in leave.sections] == [str(i) for i in range(1, 12)]
    s5 = leave.sections[4]
    assert s5.title == "Carrying leave forward" and "up to 8 days" in s5.text


def test_superseded_and_future_documents_are_not_searchable():
    assert BY_ID["HR-LEAVE-2026"].is_searchable(date(2026, 11, 6))
    assert not BY_ID["HR-LEAVE-2024"].is_searchable(date(2026, 11, 6))      # superseded
    assert not BY_ID["HR-LEAVE-2026"].is_searchable(date(2025, 12, 31))     # not yet in effect


@pytest.mark.parametrize("change, message", [
    ("access_level: all_staff", "access_level"),          # removed
    ("status: current", "status"),                        # removed
])
def test_missing_header_fields_are_rejected(change, message):
    with pytest.raises(HeaderError, match=message):
        documents.parse(HEADER.replace(change, ""), "test.md")


def test_invalid_access_level_and_no_header_are_rejected():
    with pytest.raises(HeaderError, match="access_level"):
        documents.parse(HEADER.replace("all_staff", "everyone"), "test.md")
    with pytest.raises(HeaderError, match="no header"):
        documents.parse("# Just a title\n\nSome text", "test.md")


def test_section_chunks_carry_citation_and_header():
    chunks = chunking.by_section(documents.parse(HEADER, "test.md"))
    assert [c.chunk_id for c in chunks] == ["T-1#1", "T-1#2"]
    assert chunks[0].search_text.startswith("Test Policy, §1 First")
    assert chunks[0].meta["access_level"] == "all_staff" and chunks[0].meta["version"] == "1"


def test_long_sections_are_split_without_losing_text():
    doc = documents.parse(HEADER.replace("Alpha.", "\n\n".join(["word " * 50] * 10)), "test.md")
    chunks = chunking.by_section(doc, max_chars=600)
    first = [c for c in chunks if c.section == "1"]
    assert len(first) > 1 and all(len(c.text) <= 600 for c in first)
    assert "".join(c.text for c in first).count("word") == 500


def test_small_chunks_cover_the_whole_document_and_overlap():
    doc = BY_ID["HR-LEAVE-2026"]
    chunks = chunking.fixed_size(doc)
    assert all(len(c.text) <= chunking.SMALL_SIZE for c in chunks)
    joined = " ".join(c.text for c in chunks)
    for s in doc.sections:  # every word of the document appears in some chunk
        assert set(s.text.split()) <= set(joined.split())
    assert chunks[0].text.split()[-1] in chunks[1].text  # consecutive chunks overlap


def test_every_chunk_id_is_unique():
    for method in chunking.METHODS:
        ids = [c.chunk_id for c in chunking.chunk_all(DOCS, method)]
        assert len(ids) == len(set(ids)), method


def test_large_chunks_are_bigger_than_section_chunks():
    med = lambda cs: sorted(len(c.text) for c in cs)[len(cs) // 2]
    assert med(chunking.chunk_all(DOCS, "large")) > 2 * med(chunking.chunk_all(DOCS, "section"))


# --- Uploads ----------------------------------------------------------------------------------

def upload_meta(**kw):
    meta = {"title": "Parking Policy", "version": "1.0", "department": "Operations", "access_level": "all_staff",
            "effective_date": date(2026, 1, 1), "owner": "Director of Operations"}
    return {**meta, **kw}


def test_text_upload_is_saved_and_reloaded(tmp_path):
    text = b"# Parking Policy\n\n## 1. Staff car park\n\nStaff park in car park B.\n\n## 2. Permits\n\nPermits cost nothing."
    doc = documents.save_upload("parking.md", text, upload_meta(), DOCS, tmp_path)
    assert doc.doc_id == "OPERATIONS-PARKING-POLICY-2026" and [s.number for s in doc.sections] == ["1", "2"]
    again = documents.load_all(documents.POLICY_DIR, tmp_path)
    assert len(again) == 18 and again[-1].sections[1].text == "Permits cost nothing."


def test_upload_that_replaces_a_policy_supersedes_the_old_one(tmp_path):
    documents.save_upload("leave.txt", b"Carry forward is 10 days.", upload_meta(
        title="Annual Leave Policy", department="HR", effective_date=date(2026, 6, 1), supersedes="HR-LEAVE-2026"),
        DOCS, tmp_path)
    by_id = {d.doc_id: d for d in documents.load_all(documents.POLICY_DIR, tmp_path)}
    assert by_id["HR-LEAVE-2026"].meta["status"] == "superseded"
    assert by_id["HR-ANNUAL-LEAVE-POLICY-2026"].is_searchable(date(2026, 11, 6))
    # the shipped file itself is untouched
    assert "status: current" in (documents.POLICY_DIR / "hr-annual-leave-policy-2026.md").read_text()


def test_upload_without_required_fields_or_text_is_rejected(tmp_path):
    with pytest.raises(HeaderError, match="access_level"):
        documents.save_upload("x.txt", b"text", upload_meta(access_level=""), DOCS, tmp_path)
    with pytest.raises(HeaderError, match="no readable text"):
        documents.save_upload("x.txt", b"   ", upload_meta(), DOCS, tmp_path)
    with pytest.raises(HeaderError, match="only PDF"):
        documents.save_upload("x.xlsx", b"data", upload_meta(), DOCS, tmp_path)
    assert list(tmp_path.glob("*.json")) == []


def test_pdf_and_word_uploads_keep_pages_and_headings(tmp_path):
    from docx import Document as Docx
    d = Docx()
    d.add_heading("1. Scope", level=2); d.add_paragraph("Applies to all staff.")
    d.add_heading("2. Rules", level=2); d.add_paragraph("Park in bay B.")
    buf = __import__("io").BytesIO(); d.save(buf)
    sections = documents.sections_from_file("p.docx", buf.getvalue())
    assert [(s.number, s.title, s.text) for s in sections] == [("1", "Scope", "Applies to all staff."), ("2", "Rules", "Park in bay B.")]
    pdf = make_pdf(["Page one text.", "Page two text."])
    pages = documents.sections_from_file("p.pdf", pdf)
    assert [(s.title, s.text, s.key) for s in pages] == [("Page 1", "Page one text.", "page-1"), ("Page 2", "Page two text.", "page-2")]


def make_pdf(pages: list[str]) -> bytes:
    """A minimal text PDF, built by hand so the tests need no PDF-writing library."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(len(pages)))}] /Count {len(pages)} >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    for i, text in enumerate(pages):
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {5 + 2 * i} 0 R "
                    "/Resources << /Font << /F1 3 0 R >> >> >>")
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    out, offsets = "%PDF-1.4\n", []
    for n, o in enumerate(objs, 1):
        offsets.append(len(out)); out += f"{n} 0 obj\n{o}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    return out.encode()
