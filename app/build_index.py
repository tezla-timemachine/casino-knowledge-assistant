"""Rebuild the search index from data/policies/ for every chunking method.

    python -m app.build_index
"""
import time

from app.pipeline import chunking, documents, store

if __name__ == "__main__":
    docs = documents.load_all()
    for method in chunking.METHODS:
        t = time.time()
        n = store.build_index(docs, method)
        (store.STORE_DIR / f"{store.collection_name(method)}.signature").write_text(store.signature(docs))
        print(f"{method:8} {n:4} passages indexed in {time.time() - t:.1f}s")
