import json

import pytest
from fastapi.testclient import TestClient

import api
from tracing import start_trace, traced


def test_traced_records_a_span():
    spans = start_trace()

    @traced("demo")
    def f():
        return 5

    assert f() == 5 and spans[0]["span"] == "demo" and spans[0]["ms"] >= 0


class FakeRetriever:
    def close(self):
        pass


def fake_answer(retriever, question):
    return {"answer": "ok [1]", "abstained": False, "reason": "answered", "top_score": 3.0,
            "routed": None, "uncited": False, "seconds": 0.1, "cited": [1],
            "evidence": [{"chunk_id": "a:b:0", "generic_name": "x", "section": "s", "manufacturer": "m"}]}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "Retriever", FakeRetriever)
    monkeypatch.setattr(api, "answer_question", fake_answer)
    monkeypatch.setattr(api, "AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(api, "TRACE_PATH", str(tmp_path / "traces.jsonl"))
    with TestClient(api.app) as c:
        yield c, tmp_path


def test_ask_writes_trace_and_metrics(client):
    c, tmp = client
    tok = c.post("/login", json={"username": "analyst1", "password": "analyst-pass"}).json()["access_token"]
    c.post("/ask", json={"question": "dose of terazosin?"}, headers={"Authorization": f"Bearer {tok}"})
    trace = json.loads((tmp / "traces.jsonl").read_text().splitlines()[0])
    assert trace["decision"] == "answered" and "total_ms" in trace and "queue_ms" in trace
    assert 'medlabel_ask_total{decision="answered"}' in c.get("/metrics").text