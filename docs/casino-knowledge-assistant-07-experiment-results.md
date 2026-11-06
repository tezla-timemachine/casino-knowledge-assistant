# RAG Experiment Results: Casino Employee Knowledge Assistant

*Version 1.0 · 6 Nov 2026 · Delivery Lead (Tez)*

All runs use the same 32 evaluation questions ([questions](../evals/questions.yaml),
[sheet](../evals/casino-knowledge-assistant-evaluation.xlsx)), Claude Haiku 5.5, prompt `answer_v1`, and the
free local embedding model. Each run costs under 1p. Raw results: `evals/results/`.

## 1. Chunking and top 3 vs top 5

| Chunks | Typical size | Top k | Answer accuracy | Retrieval accuracy | Correct citation | Avg time | Avg answer length | Cost (32 Qs) |
|---|---|---|---|---|---|---|---|---|
| Small (fixed) | ~300 chars | 3 | 96.9% | 100% | 96.3% | 1.67 s | 63 words | $0.0065 |
| Small (fixed) | ~300 chars | 5 | 96.9% | 100% | 100% | 1.70 s | 68 words | $0.0074 |
| **By section** | ~190 chars | 3 | **100%** | 100% | 100% | **1.32 s** | 60 words | $0.0054 |
| **By section** | ~190 chars | 5 | **100%** | 100% | 100% | 1.60 s | 64 words | $0.0065 |
| Large (fixed) | ~1,000 chars | 3 | 93.8% | 81.5% | 77.8% | 1.70 s | 61 words | $0.0079 |
| Large (fixed) | ~1,000 chars | 5 | 96.9% | 85.2% | 85.2% | 1.95 s | 64 words | $0.0098 |

No run gave an unsupported answer or leaked a restricted document.

**What we learned**

- **Section chunks performed best.** Each passage is one complete rule, and citations name the exact section.
- **Small chunks can cut a rule in half, and that can mislead.** For "How many days a week can office staff
  work from home?", the 300-character chunk boundary separated "up to 2 days" from the rest of the rule. The
  answer then said the policies "do not set a maximum", which is wrong and misleading rather than just incomplete.
- **Large chunks hide specific rules.** A 1,000-character passage mixes several topics, so it matches any one
  question less closely. Retrieval accuracy fell to 81–85%. "How early do I ring in sick for a casino floor shift?"
  wasn't answered at all because the sickness section never ranked in the top passages.
- **Top 5 vs top 3:** with section chunks, the two extra passages didn't change accuracy. They made answers
  slightly longer (+4 words), slower (+0.3 s) and dearer (+20%). Top 5 did help large chunks: one answer spread
  across sections was found only at top 5. **Decision: keep top 5.** The cost is negligible, and the extra
  headroom protects questions whose answer is spread across documents, which matters more for a policy assistant
  than 0.3 seconds.
- **Our policies are written in short numbered sections, so section chunking fits them.** Long, unstructured
  documents (e.g. scanned PDFs) would need different splitting.

## 2. Old and new versions (the version filter)

The same 32 questions were run with the version filter **switched off**, so superseded policies could be searched.

| | Version filter on | Version filter off |
|---|---|---|
| Answer accuracy | 100% | 90.6% |
| Outdated-version questions passed | 3/3 | 1/3 |
| Questions where a superseded policy was **retrieved** | 0 | **16 of 32** |
| Answers that **cited** a superseded policy | 0 | 5 |
| Average answer length | 64 words | 70 words |

**What we learned**

- Superseded policies appear in the search results for **half of all questions**, not just leave and
  hybrid-working questions. They read almost the same as the current versions.
- Claude usually **worked out which version was current**, because every passage is labelled with its version
  and effective date (D9). But it then **quoted the old rule as well** ("the older policy allowed 5 days with a
  31 March deadline…") and cited the superseded document as a source. An employee skimming that answer could
  easily take away the wrong rule.
- **Conclusion: the version filter (D7) is needed.** Relying on the AI to choose the newest version works most of
  the time, but not reliably enough for HR policy. Removing old versions before the search does work reliably.

## 3. Document tests from the brief

| Situation | Questions | Result (section chunks, top 5) |
|---|---|---|
| Two policies with similar information | Q15–Q19 | 5/5 marked as passing, but see the note on Q19 below |
| Old and new version exist | Q23–Q25 | 3/3: old rules never used |
| Answer spread across sections | Q20–Q22 | 3/3 |
| Question worded differently from the policy | Q11–Q14 | 4/4 |
| Answer does not exist | Q26–Q28 | 3/3: no invented answers |
| Restricted document, wrong role | Q29, Q31 | 2/2: "not enough information", no leak |

**Q19 ("Someone on the gaming floor looks under 18. What do I do?") is still a retrieval gap.** In every run the
search found the Compliance Guidelines (Think 25) but not the Incident Reporting Procedure, which says to tell the
duty manager immediately. That procedure is one large table covering every incident type, so as a single passage
it matches any one question weakly. Claude honestly said the passages "do not say who to tell". The automatic
marking failed it in the first run, then passed it in later runs because Claude added "check with your duty
manager" as general advice. **This shows the limit of automatic marking, and why the sheet has a Human check
column.** Fix (next step): split tables so that each row becomes its own passage.

## 4. Minimum match score (safety net 1)

The best match score for each question (section chunks):

| | Lowest best match | Highest best match |
|---|---|---|
| Questions the policies answer | 0.43 | — |
| Questions with no answer, or restricted for the role | 0.29 | 0.49 |

- The two groups **overlap**. A restricted question scored 0.49, higher than some real answers, because general
  policies mention related topics. No single cut-off separates them.
- A cut-off of 0.40 would have skipped the AI for 3 of the 5 no-answer questions in this set. But the margin
  above the lowest real answer (0.43) is too thin to risk wrongly refusing real questions.
- **Decision: keep 0.30.** It only skips obvious misses. Claude's found / not found reply (safety net 2) decides
  everything else, and it made **no unsupported answers** across all 7 runs (35 no-answer or restricted questions, 224 questions in total).

## 5. Decisions confirmed or changed

| Decision | Before the experiments | After |
|---|---|---|
| D1 Chunking | By section (provisional) | **Confirmed:** best accuracy; small chunks can mislead, large chunks miss rules |
| D4 Top k | 5 (provisional) | **Confirmed: 5.** Same accuracy as 3 for section chunks, with more headroom for spread answers |
| D5 Minimum match score | 0.30 (provisional) | **Confirmed: 0.30.** Higher cut-offs risk refusing real questions |
| D7 Version filter | Filter before search | **Confirmed by test:** without it, old versions reach half of all searches |

## 6. Limits of these experiments

- 32 questions written alongside the documents. Real employees' questions will be messier, so add them before go-live.
- Automatic marking checks key facts, which is a proxy (see Q19). A person should confirm the marks.
- Claude's wording varies between runs, so a one-question difference (3%) is within normal variation.
