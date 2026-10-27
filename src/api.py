import asyncio
import os
import uuid
from contextlib import asynccontextmanager

import time
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from tracing import start_trace, write_trace

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

import answer as answer_mod
from answer import answer_question
from audit import log_event, read_events, verify_chain
from auth import authenticate, make_token, require_role
from guardrails import redact_pii
from retrieval import Retriever

AUDIT_PATH = "logs/audit.jsonl"
TRACE_PATH = "logs/traces.jsonl"
ASK_TOTAL = Counter("medlabel_ask_total", "Questions by final decision", ["decision"])
ASK_SECONDS = Histogram("medlabel_ask_seconds", "Seconds per question, queue included",
                        buckets=(1, 5, 10, 20, 40, 80))
DISCLAIMER = ("Answers are generated from FDA label excerpts for information only. "
              "They are not medical advice. Always verify against the full official label.")
state = {}


@asynccontextmanager
async def lifespan(app):
    state["retriever"] = Retriever()          # load models once, not per request
    state["lock"] = asyncio.Lock()            # one LLM job at a time on a laptop
    yield
    state["retriever"].close()


app = FastAPI(title="MedLabel Assist", version="0.1.0", lifespan=lifespan)


class LoginRequest(BaseModel):
    username: str
    password: str


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class Citation(BaseModel):
    n: int
    drug: str
    section: str
    manufacturer: str
    chunk_id: str
    snippet: str = ""


class AskResponse(BaseModel):
    request_id: str
    answer: str
    abstained: bool
    reason: str
    citations: list[Citation]
    seconds: float
    disclaimer: str


def _run(question):
    try:
        return answer_question(state["retriever"], question)
    except SystemExit as e:                   # answer.py exits if Ollama is down
        raise RuntimeError(str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/login")
async def login(req: LoginRequest):
    user = authenticate(req.username, req.password)
    if not user:
        log_event(AUDIT_PATH, {"event": "login_failed", "user": req.username})
        raise HTTPException(401, "Wrong username or password")
    log_event(AUDIT_PATH, {"event": "login", "user": user["user"], "role": user["role"]})
    return {"access_token": make_token(user), "token_type": "bearer"}


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, user=Depends(require_role("analyst", "admin"))):
    request_id = str(uuid.uuid4())
    safe_q, pii = redact_pii(req.question)    # personal data never reaches search, LLM or logs
    spans = start_trace()
    t0 = time.perf_counter()
    try:
        async with state["lock"]:
            queue_ms = round((time.perf_counter() - t0) * 1000)
            out = await asyncio.to_thread(_run, safe_q)
    except RuntimeError:
        ASK_TOTAL.labels(decision="llm_unavailable").inc()
        raise HTTPException(503, "Language model service is unavailable")
    total = time.perf_counter() - t0
    ASK_TOTAL.labels(decision=out["reason"]).inc()
    ASK_SECONDS.observe(total)
    write_trace(TRACE_PATH, {"request_id": request_id, "user": user["user"],
                             "decision": out["reason"], "queue_ms": queue_ms,
                             "total_ms": round(total * 1000), "spans": spans})

    citations = []
    for n in out["cited"]:
        h = out["evidence"][n - 1]
        citations.append(Citation(n=n, drug=h["generic_name"], section=h["section"],
                                  manufacturer=h["manufacturer"], chunk_id=h["chunk_id"],
                                  snippet=h.get("text", "")[:700]))
    log_event(AUDIT_PATH, {
        "event": "ask", "request_id": request_id, "user": user["user"], "role": user["role"],
        "question": safe_q, "pii_redacted": pii, "decision": out["reason"],
        "abstained": out["abstained"], "answer": out["answer"],
        "cited_chunks": [c.chunk_id for c in citations],
        "model": answer_mod.LLM, "prompt": os.environ.get("MEDLABEL_PROMPT", "v3"),
    })
    return AskResponse(request_id=request_id, answer=out["answer"], abstained=out["abstained"],
                       reason=out["reason"], citations=citations,
                       seconds=round(out["seconds"], 1), disclaimer=DISCLAIMER)


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/audit")
async def audit(limit: int = 50, user=Depends(require_role("auditor", "admin"))):
    ok, total = verify_chain(AUDIT_PATH)
    return {"chain_intact": ok, "total_entries": total, "recent": read_events(AUDIT_PATH, limit)}