"""Step 1: Load policy documents and check their header (D7, D8, D10).

Every document starts with a header between --- lines, giving its version, status, effective date,
department and access level. The search filters depend on it, so a document with a missing or
invalid header is rejected rather than loaded without it.

Uploaded documents (PDF, Word, text) get their header from the upload form instead (D10), and are
saved to data/uploads/ as JSON. When an upload replaces an older document, the old one is recorded as
superseded in data/uploads/registry.yaml, so the original file is never edited.
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "data" / "policies"
UPLOAD_DIR = ROOT / "data" / "uploads"
REGISTRY_PATH = UPLOAD_DIR / "registry.yaml"
DEPARTMENTS = ["General", "HR", "Finance", "Compliance", "IT", "Security", "Operations", "Customer Service"]

REQUIRED = ["doc_id", "title", "version", "department", "access_level", "status", "effective_date", "owner"]
ACCESS_LEVELS = {"all_staff", "hr", "compliance"}
STATUSES = {"current", "superseded"}


class HeaderError(ValueError):
    """The document's header is missing or invalid, so it cannot be searched safely."""


@dataclass
class Section:
    number: str   # "5"; "" for text before the first numbered heading, or for PDF pages
    title: str    # "Carrying leave forward", or "Page 3"
    text: str

    @property
    def key(self) -> str:
        """Short, unique-within-document id used in passage ids: "5", "introduction", "page-3"."""
        return self.number or re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")


@dataclass
class Document:
    meta: dict
    sections: list[Section]
    source: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def doc_id(self) -> str:
        return self.meta["doc_id"]

    def is_searchable(self, today: date | None = None) -> bool:
        """Current and already in effect (D7)."""
        return self.meta["status"] == "current" and self.meta["effective_date"] <= (today or date.today())


def check_header(meta: dict, source: str = "") -> dict:
    missing = [k for k in REQUIRED if not meta.get(k)]
    if missing:
        raise HeaderError(f"{source}: header is missing {', '.join(missing)}")
    if meta["access_level"] not in ACCESS_LEVELS:
        raise HeaderError(f"{source}: access_level must be one of {sorted(ACCESS_LEVELS)}")
    if meta["status"] not in STATUSES:
        raise HeaderError(f"{source}: status must be one of {sorted(STATUSES)}")
    if not isinstance(meta["effective_date"], date):
        raise HeaderError(f"{source}: effective_date must be a date like 2026-01-01")
    meta["version"] = str(meta["version"])
    return meta


def split_sections(body: str) -> list[Section]:
    """Split on '## 5. Heading' lines. Text before the first numbered heading becomes section ''."""
    parts = re.split(r"^## (\d+)\.\s*(.+)$", body, flags=re.M)
    sections = []
    intro = re.sub(r"^# .+$", "", parts[0], count=1, flags=re.M)  # drop the document title line
    intro = re.sub(r"^\*.*Mock document.*\*$", "", intro, flags=re.M).strip()  # and the mock disclaimer
    if intro:
        sections.append(Section("", "Introduction", intro))
    for i in range(1, len(parts), 3):
        sections.append(Section(parts[i], parts[i + 1].strip(), parts[i + 2].strip()))
    return sections


def parse(text: str, source: str = "") -> Document:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise HeaderError(f"{source}: no header found (it must start and end with ---)")
    meta = check_header(yaml.safe_load(m.group(1)) or {}, source)
    return Document(meta, split_sections(m.group(2)), source)


def load_folder(folder: Path = POLICY_DIR) -> list[Document]:
    return [parse(p.read_text(encoding="utf-8"), p.name) for p in sorted(folder.glob("*.md"))]


# --- Uploads ------------------------------------------------------------------------------------

def read_header(data: bytes) -> dict:
    """The header of an uploaded text/Markdown file, if it has one, to pre-fill the upload form."""
    m = re.match(r"^---\n(.*?)\n---\n", data.decode("utf-8", errors="replace"), re.S)
    try:
        return (yaml.safe_load(m.group(1)) or {}) if m else {}
    except yaml.YAMLError:
        return {}


def sections_from_file(filename: str, data: bytes) -> list[Section]:
    """Turn an uploaded file into sections. PDFs keep their page numbers so answers can cite them."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        pages = [(n, (page.extract_text() or "").strip()) for n, page in enumerate(PdfReader(io.BytesIO(data)).pages, 1)]
        return [Section("", f"Page {n}", text) for n, text in pages if text]
    if ext == ".docx":
        from docx import Document as Docx
        sections, title, lines = [], "Introduction", []
        for para in Docx(io.BytesIO(data)).paragraphs:
            if para.style.name.lower().startswith("heading") and para.text.strip():
                if lines:
                    sections.append((title, "\n\n".join(lines)))
                title, lines = para.text.strip(), []
            elif para.text.strip():
                lines.append(para.text.strip())
        if lines:
            sections.append((title, "\n\n".join(lines)))
        out = []
        for heading, text in sections:  # "5. Carrying leave forward" keeps its number
            m = re.match(r"^(\d+)\.\s*(.+)$", heading)
            out.append(Section(m.group(1), m.group(2), text) if m else Section("", heading, text))
        return out
    if ext in (".md", ".txt"):
        text = data.decode("utf-8", errors="replace")
        text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)  # header comes from the form
        sections = split_sections(text)
        return sections if sections else [Section("", "Document", text.strip())]
    raise HeaderError(f"{filename}: only PDF, Word (.docx), Markdown and text files can be uploaded")


def make_doc_id(meta: dict, existing: set[str]) -> str:
    base = re.sub(r"[^A-Z0-9]+", "-", f"{meta['department']}-{meta['title']}-{meta['effective_date']:%Y}".upper()).strip("-")
    doc_id, n = base, 2
    while doc_id in existing:
        doc_id, n = f"{base}-{n}", n + 1
    return doc_id


def save_upload(filename: str, data: bytes, meta: dict, existing: list[Document],
                folder: Path = UPLOAD_DIR) -> Document:
    """Check the header, convert the file and save it. If it replaces a document, mark that one superseded."""
    meta = {k: v for k, v in meta.items() if v not in (None, "")}
    meta["status"] = "current"
    meta.setdefault("doc_id", make_doc_id(meta, {d.doc_id for d in existing}))
    if meta["doc_id"] in {d.doc_id for d in existing}:
        raise HeaderError(f"A document with id {meta['doc_id']} already exists")
    check_header(meta, filename)
    sections = sections_from_file(filename, data)
    if not any(s.text for s in sections):
        raise HeaderError(f"{filename}: no readable text found (a scanned PDF may need OCR first)")
    doc = Document(meta, sections, f"uploads/{filename}")
    folder.mkdir(parents=True, exist_ok=True)
    record = {"source": filename, "meta": {**meta, "effective_date": meta["effective_date"].isoformat(),
              **({"review_date": meta["review_date"].isoformat()} if isinstance(meta.get("review_date"), date) else {})},
              "sections": [asdict(s) for s in sections]}
    (folder / f"{meta['doc_id']}.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    if meta.get("supersedes"):
        registry_path = folder / REGISTRY_PATH.name
        registry = (yaml.safe_load(registry_path.read_text()) or {}) if registry_path.exists() else {}
        registry.setdefault("superseded", {})[meta["supersedes"]] = meta["doc_id"]
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=True))
    return doc


def load_uploads(folder: Path = UPLOAD_DIR) -> list[Document]:
    docs = []
    for p in sorted(folder.glob("*.json")) if folder.exists() else []:
        record = json.loads(p.read_text(encoding="utf-8"))
        meta = record["meta"]
        for k in ("effective_date", "review_date"):
            if isinstance(meta.get(k), str):
                meta[k] = date.fromisoformat(meta[k])
        docs.append(Document(check_header(meta, p.name), [Section(**s) for s in record["sections"]], f"uploads/{record['source']}"))
    return docs


def load_all(policy_dir: Path = POLICY_DIR, upload_dir: Path = UPLOAD_DIR) -> list[Document]:
    """Shipped policies plus uploads, with any replacements made through uploads applied."""
    docs = load_folder(policy_dir) + load_uploads(upload_dir)
    registry_path = upload_dir / REGISTRY_PATH.name
    superseded = ((yaml.safe_load(registry_path.read_text()) or {}).get("superseded", {})
                  if registry_path.exists() else {})
    for d in docs:
        if d.doc_id in superseded:
            d.meta["status"], d.meta["superseded_by"] = "superseded", superseded[d.doc_id]
    return docs
