# Key Decisions: Casino Employee Knowledge Assistant

*Version 0.2 · 6 Nov 2026 · Delivery Lead (Tez)*

Each decision says what was chosen, why, what else was considered, and what it means for the business.
Decisions marked **Experiment** are provisional until the RAG experiments confirm or change them.

## Flow

```
Policy documents (with header: version, status, effective date, department, access level)
  → load and check header → split into passages (chunking) → turn into numbers on this Mac (embeddings)
  → store in Chroma (vector database)

Question + user's role
  → filter: current, in effect, allowed for this role → find closest passages (retrieval)
  → no close match? say "not enough information" without calling the AI
  → Claude Haiku 5.5 answers from those passages only, in a fixed format
  → code checks the cited passages were really retrieved → answer + document + section + exact source text
```

## Decisions

| # | Decision | Choice | Why | Alternatives considered | Business impact |
|---|---|---|---|---|---|
| D1 | Chunking | **By numbered section**; long sections split further. Each passage starts with the document title and section heading. **Confirmed by experiment:** 100% accuracy vs 96.9% for small chunks and 93.8–96.9% for large chunks (see doc 07). | A section is a complete rule, and the citation can name it ("§5 Carrying leave forward"). | Fixed-size chunks only; whole documents | Employees can check the exact section the answer came from |
| D2 | Embedding model | **all-MiniLM-L6-v2**, free, runs on the laptop (built into Chroma) | No cost and no extra account. Policy text isn't sent to a third party to be embedded. | Voyage AI (more accurate, but paid and sends text out); OpenAI embeddings | Zero running cost for search. If the "different wording" tests show it isn't accurate enough, switching is a configuration change |
| D3 | Vector database | **Chroma**, stored in a project folder | Free, local, and can filter by document header at search time, which D7 and D8 depend on | FAISS (no filtering), Pinecone (hosted: data leaves the company), pgvector (needs a database server) | No extra infrastructure for V1 |
| D4 | Retrieval | **Meaning-based search with filters applied before the search; top 5 passages.** Confirmed by experiment: top 3 was equally accurate with section chunks, but 5 gives headroom for answers spread across documents at negligible cost | Filtering first means excluded documents can never be retrieved | Keyword search; filtering after the search | Old or restricted text cannot appear in answers |
| D5 | "Not enough information" | **Two safety nets:** (1) no passage scoring at least 0.30 → reply without calling the AI; (2) the AI must say found / not found and which passages it used, and code checks them. Confirmed by experiment: no unsupported answers in 7 runs (224 questions) | An internal policy assistant must never invent a rule | Relying on prompt wording alone | Employees can trust that an answer is backed by a policy, or are told to ask HR |
| D6 | LLM | **Claude Haiku 5.5** (same as Week 1) | Fast and low-cost; reading 3–5 short passages is a simple job | A larger Claude model (can be tested if accuracy falls short) | Quick answers at low cost per question |
| D7 | Document versions | **Superseded documents are never searched.** Documents not yet in effect are not searched. Each answer shows the version and effective date. Uploading a new version marks the one it replaces as superseded. Questions about old versions are **not supported in V1** | Removing old versions in code is reliable. Asking the AI to "prefer the newest" is not | Search everything and ask the AI to prefer the newest; allow old versions with a warning | Employees always get the current rule. Policy history is a known limitation |
| D8 | Access control | **"View as" switch (Employee / HR / Compliance)** in V1. Restricted documents are filtered out before the search. Production design: company sign-in (SSO), with roles taken from HR system groups | The brief asks for the design, not a full permission system | Separate database per department; no access control | Restricted documents never reach an unauthorised employee, the AI or the screen |
| D9 | Citations | Show the **document, version, section and the exact retrieved text**, taken from the database rather than written by the AI | Quotes cannot be invented | Asking the AI to quote | Employees can check the answer themselves |
| D10 | Upload | PDF, Word or text. **The header fields are required** before a document can be searched | An untagged document would get past the version and access filters | Guessing the header from the file | No document enters search without an owner, status and access level |
| D11 | Application | **Streamlit**, run locally first. Online hosting only with approval | Same as Week 1, so it's quick to build | A web framework with a separate front end | Fast to demonstrate to stakeholders |

## Decision history

| Date | Decision | Decided by |
|---|---|---|
| 6 Nov 2026 | D2: free local embeddings rather than Voyage AI | Delivery Lead (Tez) |
| 6 Nov 2026 | D7: hide superseded versions completely in V1 | Delivery Lead (Tez) |
| 6 Nov 2026 | D1, D4, D5 confirmed and D7 tested by the RAG experiments (doc 07) | Delivery Lead (Tez) |
