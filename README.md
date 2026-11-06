# Casino Employee Knowledge Assistant

An internal assistant that answers employees' policy questions **only from approved
company documents**, shows the document and section it used, and says clearly when
the answer isn't in the documents.

Week 3 project (RAG Knowledge Management Product). **Status: working app; experiments and evaluation next.**

All documents in `data/policies/` are **mock documents for a fictional company**,
written for this project. They are not real policies and not legal advice.

## How it works

```
Question + role → filter: current, in effect, allowed for this role → find closest policy sections
  → nothing close enough? "not enough information" (AI not called)
  → Claude Haiku 5.5 answers from those sections only, in a fixed format
  → code checks the cited sections were really found → answer + policy + section + exact text
```

Old versions and restricted documents are removed **before** searching, so they can never reach the AI
or the screen. [The 11 decisions behind this →](docs/casino-knowledge-assistant-03-decision-log.md)

## Run it

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # then paste your Anthropic API key into .env yourself
.venv/bin/streamlit run app/streamlit_app.py
```

The search index is built automatically on first run (the free embedding model downloads once, ~80 MB).
With no API key, set `LLM_PROVIDER=mock` to try the app without AI (answers are clearly marked as not AI).

| Command | What it does |
|---|---|
| `.venv/bin/python -m pytest` | 35 tests: loading, chunking, version and access filters, answer safety nets, uploads |
| `.venv/bin/python -m app.build_index` | Rebuilds the search index for all three chunking methods |

## Layout

| Folder | What's in it |
|---|---|
| `data/policies/` | Mock policy documents, each with a metadata header |
| `app/pipeline/` | Loading, chunking, search, answering |
| `app/streamlit_app.py` | The app: Ask, Policy library, Upload, How it works |
| `config/roles.yaml` | Which documents each role can search |
| `prompts/` | The instructions given to the AI |
| `docs/` | Decision log (product document, architecture, risks to come) |
| `tests/` | Automated tests |

## The document set

17 mock documents for the fictional **Harbourlight Casino Group**. Some are built in on purpose to test
the assistant:

| Test | Documents |
|---|---|
| Old vs new version (same title) | Annual Leave Policy **2024** (superseded) vs **2026** (current). Carry forward 5 days by 31 Mar vs 8 days by 30 Jun |
| Old vs new version (different title) | Hybrid Working Policy 2023 (superseded) vs Remote and Workplace Policy 2025 (current). 3 vs 2 remote days |
| Similar policies that could be confused | Annual leave vs sickness absence; Information Security vs IT Acceptable Use; Incident Reporting vs Compliance Guidelines |
| Answer spread across sections | Annual Leave 2026 §5 (carry-forward limit) and §8 (exceptions) |
| Restricted documents | Disciplinary Investigation Procedure (HR only); AML Investigation Procedure (Compliance only) |
| Overdue for review | Incident Reporting Procedure (review date 1 Feb 2026 has passed) |
| Not covered at all | e.g. parental leave pay, pensions, company cars, shift swaps |

Each document starts with a metadata header:

```yaml
doc_id: HR-LEAVE-2026
title: Annual Leave Policy
version: "2026.1"
department: HR
access_level: all_staff      # all_staff | hr | compliance
status: current              # current | superseded
effective_date: 2026-01-01
supersedes: HR-LEAVE-2024
owner: Head of People
review_date: 2027-01-01
```
