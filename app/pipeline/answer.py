"""Step 6: Answer from the retrieved passages only, or say there isn't enough information (D5, D9).

Two safety nets against invented answers:
1. No passage close enough in meaning to the question -> "not enough information", without calling the AI.
2. The AI must reply in a fixed format (found / not_found + the passage IDs it used). Code then checks
   that every cited passage was really retrieved. A "found" answer citing no real passage is not shown.

The sources shown to the employee are the stored policy passages, never text written by the AI.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

from . import llm, store

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "prompts" / "answer_v1.txt"
PROMPT_VERSION = PROMPT_PATH.stem
# Below this closeness score, no passage is treated as relevant. Provisional: the first search tests showed
# real answers can score as low as ~0.39 and unrelated passages ~0.41, so this only catches clear misses.
# The experiments set the final value.
MIN_SCORE = 0.30

NOT_FOUND_MESSAGE = ("I don't have enough information in the approved policies to answer this. "
                     "Please ask your line manager, or HR through the HR Help form on StaffHub.")


@dataclass
class Answer:
    question: str
    status: str                 # "found" or "not_found"
    text: str
    reason: str                 # found | no_close_match | ai_not_found | no_valid_source | no_valid_reply
    sources: list[store.Hit] = field(default_factory=list)    # passages the answer is based on
    retrieved: list[store.Hit] = field(default_factory=list)  # everything the search returned
    seconds: float = 0.0
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def found(self) -> bool:
        return self.status == "found"


def build_user_message(question: str, hits: list[store.Hit]) -> str:
    passages = "\n\n".join(f"[P{i}] {h.citation}\n{h.text}" for i, h in enumerate(hits, 1))
    return f"POLICY PASSAGES\n\n{passages}\n\nQUESTION\n{question}"


def ask(question: str, role: str = "Employee", k: int = store.TOP_K, method: str = "section",
        today: date | None = None, path: Path = store.STORE_DIR, min_score: float = MIN_SCORE,
        complete: Callable = llm.complete) -> Answer:
    start = time.time()
    hits = store.search(question, role=role, k=k, method=method, today=today, path=path)

    def done(a: Answer) -> Answer:
        a.retrieved, a.seconds = hits, round(time.time() - start, 2)
        return a

    # Safety net 1: nothing relevant enough was found, so don't ask the AI at all.
    if not hits or hits[0].score < min_score:
        return done(Answer(question, "not_found", NOT_FOUND_MESSAGE, "no_close_match"))

    reply, usage = complete(PROMPT_PATH.read_text(encoding="utf-8"), build_user_message(question, hits))
    tokens = dict(model=usage.model, input_tokens=usage.input_tokens, output_tokens=usage.output_tokens)

    if reply is None:
        return done(Answer(question, "not_found", NOT_FOUND_MESSAGE, "no_valid_reply", **tokens))
    if reply.status == "not_found":
        return done(Answer(question, "not_found", NOT_FOUND_MESSAGE, "ai_not_found", **tokens))

    # Safety net 2: keep only citations of passages that were really retrieved, in the order given.
    by_id = {f"P{i}": h for i, h in enumerate(hits, 1)}
    cited = list(dict.fromkeys(s.strip().strip("[]") for s in reply.source_ids))
    sources = [by_id[s] for s in cited if s in by_id]
    if not sources:
        return done(Answer(question, "not_found", NOT_FOUND_MESSAGE, "no_valid_source", **tokens))
    return done(Answer(question, "found", reply.answer.strip(), "found", sources, **tokens))
