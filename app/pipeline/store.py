"""Steps 3-5: Embeddings, vector database and retrieval (D2, D3, D4, D7, D8).

Passages are turned into numbers on this machine (all-MiniLM-L6-v2) and stored in Chroma,
one collection per chunking method so the experiments can compare them.

Every search is filtered BEFORE matching: only current documents, already in effect,
at an access level the user's role allows. Superseded and restricted text can never be returned.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import chromadb
import yaml
from chromadb.config import Settings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from . import chunking, documents

ROOT = Path(__file__).resolve().parents[2]
STORE_DIR = ROOT / "data" / "vectorstore"
ROLES_PATH = ROOT / "config" / "roles.yaml"
TOP_K = 5  # provisional: the experiments compare 3 and 5 (D4)

_embedder = DefaultEmbeddingFunction()  # free, runs locally; downloads ~80 MB once (D2)


def roles(path: Path = ROLES_PATH) -> dict[str, list[str]]:
    return yaml.safe_load(path.read_text())["roles"]


def _date_int(d: date) -> int:
    """Chroma can only compare numbers, so 2026-01-01 is stored as 20260101."""
    return d.year * 10000 + d.month * 100 + d.day


def client(path: Path = STORE_DIR):
    # Anonymous usage statistics are switched off: nothing leaves the machine from the database.
    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))


def collection_name(method: str) -> str:
    return f"policies_{method}"


def build_index(docs: list[documents.Document], method: str = "section", path: Path = STORE_DIR) -> int:
    """(Re)build the collection for one chunking method. Returns the number of passages stored."""
    db = client(path)
    name = collection_name(method)
    if name in [c.name for c in db.list_collections()]:
        db.delete_collection(name)
    col = db.create_collection(name, embedding_function=_embedder, configuration={"hnsw": {"space": "cosine"}})
    chunks = chunking.chunk_all(docs, method)
    col.add(
        ids=[c.chunk_id for c in chunks],
        embeddings=_embedder([c.search_text for c in chunks]),  # title + heading + text is what gets matched
        documents=[c.text for c in chunks],                     # the policy text shown as the source (D9)
        metadatas=[{
            "doc_id": c.doc_id, "title": c.meta["title"], "version": c.meta["version"],
            "department": c.meta["department"], "access_level": c.meta["access_level"],
            "status": c.meta["status"], "effective_date": _date_int(c.meta["effective_date"]),
            "section": c.section, "section_title": c.section_title,
        } for c in chunks],
    )
    return len(chunks)


def signature(docs: list[documents.Document]) -> str:
    """Changes whenever any document's text or header changes (including being superseded)."""
    payload = [[d.doc_id, {k: str(v) for k, v in sorted(d.meta.items())}, [[s.number, s.title, s.text] for s in d.sections]]
               for d in sorted(docs, key=lambda d: d.doc_id)]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:16]


def ensure_index(docs: list[documents.Document], method: str = "section", path: Path = STORE_DIR) -> bool:
    """Rebuild the index only if the documents changed since it was built. Returns True if rebuilt."""
    marker = path / f"{collection_name(method)}.signature"
    sig = signature(docs)
    if marker.exists() and marker.read_text() == sig and \
            collection_name(method) in [c.name for c in client(path).list_collections()]:
        return False
    build_index(docs, method, path)
    marker.write_text(sig)
    return True


@dataclass
class Hit:
    chunk_id: str
    doc_id: str
    title: str
    version: str
    effective_date: date
    department: str
    section: str
    section_title: str
    text: str
    score: float  # 0 to 1: how close in meaning the passage is to the question (cosine similarity)

    @property
    def citation(self) -> str:
        where = f"§{self.section} {self.section_title}" if self.section else self.section_title
        return f"{self.title} (v{self.version}, effective {self.effective_date:%-d %b %Y}), {where}"


def search_filter(role: str, today: date | None = None, apply_version_filter: bool = True) -> dict:
    """The rules applied before any matching (D7, D8)."""
    allowed = roles()[role]
    rules = [{"access_level": {"$in": allowed}}]
    if apply_version_filter:
        rules += [{"status": "current"}, {"effective_date": {"$lte": _date_int(today or date.today())}}]
    return rules[0] if len(rules) == 1 else {"$and": rules}


def search(question: str, role: str = "Employee", k: int = TOP_K, method: str = "section",
           today: date | None = None, path: Path = STORE_DIR, apply_version_filter: bool = True) -> list[Hit]:
    """Closest passages the role may see, best first.

    apply_version_filter=False exists only for the experiments that show why the filter is needed;
    the app never turns it off.
    """
    col = client(path).get_collection(collection_name(method), embedding_function=_embedder)
    res = col.query(query_texts=[question], n_results=k,
                    where=search_filter(role, today, apply_version_filter),
                    include=["documents", "metadatas", "distances"])
    hits = []
    for cid, text, m, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
        d = m["effective_date"]
        hits.append(Hit(cid, m["doc_id"], m["title"], m["version"], date(d // 10000, d // 100 % 100, d % 100),
                        m["department"], m["section"], m["section_title"], text, round(1 - dist, 3)))
    return hits
