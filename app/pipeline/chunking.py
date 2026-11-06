"""Step 2: Chunking, i.e. cutting documents into passages for search (D1).

Three methods, compared in the RAG experiments:
- by_section: one passage per numbered section; long sections are split on paragraph breaks.
- small: fixed passages of about 300 characters with an overlap, ignoring section breaks.
- large: fixed passages of about 1,000 characters (usually several sections) with an overlap.
Our policy sections are short (median ~190 characters), so "large" is needed for a real
smaller-vs-larger comparison: by_section turned out to be the small end, not the large one.

Every passage starts with the document title and section heading, so that a passage like
"Up to 8 days..." still carries the words "Annual Leave Policy" and "Carrying leave forward" for search.
Each passage also carries the document's header, which the search filters use (D4, D7, D8).
"""
from __future__ import annotations

from dataclasses import dataclass

from .documents import Document

SECTION_MAX_CHARS = 1500   # longer sections are split further
SMALL_SIZE = 300           # the "smaller chunks" experiment
SMALL_OVERLAP = 60
LARGE_SIZE = 1000          # the "larger chunks" experiment
LARGE_OVERLAP = 150


@dataclass
class Chunk:
    chunk_id: str        # "HR-LEAVE-2026#5" or "HR-LEAVE-2026#s3"
    doc_id: str
    section: str         # "5" or "5-6" when a small chunk spans sections
    section_title: str
    text: str            # the policy text shown to the user as the source
    meta: dict           # the document header

    @property
    def search_text(self) -> str:
        """What gets embedded: title and heading for context, then the policy text."""
        where = f"§{self.section} {self.section_title}" if self.section else self.section_title
        return f"{self.meta['title']}, {where}\n{self.text}"


def _split_long(text: str, limit: int) -> list[str]:
    """Split on blank lines into pieces no longer than `limit` (a single paragraph is never cut)."""
    pieces, current = [], ""
    for para in text.split("\n\n"):
        if current and len(current) + len(para) + 2 > limit:
            pieces.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        pieces.append(current)
    return pieces


def by_section(doc: Document, max_chars: int = SECTION_MAX_CHARS) -> list[Chunk]:
    chunks = []
    for s in doc.sections:
        pieces = _split_long(s.text, max_chars)
        for n, piece in enumerate(pieces, 1):
            suffix = f".{n}" if len(pieces) > 1 else ""
            chunks.append(Chunk(f"{doc.doc_id}#{s.key}{suffix}", doc.doc_id, s.number, s.title, piece, doc.meta))
    return chunks


def fixed_size(doc: Document, size: int = SMALL_SIZE, overlap: int = SMALL_OVERLAP) -> list[Chunk]:
    """Slide a window of `size` characters (moved to word boundaries) across the whole document."""
    # Join the sections, remembering where each one starts, so every chunk can still be cited.
    text, starts = "", []
    for s in doc.sections:
        starts.append((len(text), s))
        text += s.text + "\n\n"
    text = text.rstrip()

    def section_at(pos: int):
        return [s for start, s in starts if start <= pos][-1]

    chunks, pos, n = [], 0, 1
    while pos < len(text):
        end = min(len(text), pos + size)
        if end < len(text):  # don't cut a word in half
            space = text.rfind(" ", pos + size // 2, end)
            end = space if space > 0 else end
        first, last = section_at(pos), section_at(end - 1)
        number = first.number if first is last else f"{first.number}-{last.number}"
        chunks.append(Chunk(f"{doc.doc_id}#s{n}", doc.doc_id, number, first.title, text[pos:end].strip(), doc.meta))
        if end >= len(text):
            break
        nxt = text.rfind(" ", pos, end - overlap)  # step back by the overlap, again on a word boundary
        pos = nxt + 1 if nxt > pos else end
        n += 1
    return chunks


def large(doc: Document) -> list[Chunk]:
    return fixed_size(doc, LARGE_SIZE, LARGE_OVERLAP)


METHODS = {"section": by_section, "small": fixed_size, "large": large}


def chunk_all(docs: list[Document], method: str = "section") -> list[Chunk]:
    return [c for d in docs for c in METHODS[method](d)]
