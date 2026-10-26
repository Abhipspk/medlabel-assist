import json

import pytest
from fastapi.testclient import TestClient

import api
from audit import log_event, verify_chain


class FakeRetriever:
    def close(self):
        pass


def fake_answer(retriever, question):
    return {"answer": "Dose is 1 mg [1].", "abstained": False, "reason": "answered",
            "top_score": 3.0, "routed": None, "uncited": False, "seconds": 0.1, "cited": [1],
            "evidence": [{"chunk_id": "abc:dosage:0", "generic_name": "terazosin",
                          "section": "dosage_and_administration", "manufacturer": "X"}]}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "Retriever", FakeRetriever)
    monkeypatch.setattr(api, "answer_question", fake_answer)
    monkeypatch.setattr(api, "AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    with TestClient(api.app) as c:
        yield c


def token(client, user, pw):
    r = client.post("/login", json={"username": user, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_wrong_password_rejected(client):
    assert client.post("/login", json={"username": "analyst1", "password": "nope"}).status_code == 401


def test_ask_requires_token(client):
    assert client.post("/ask", json={"question": "dose of terazosin?"}).status_code in (401, 403)


def test_roles_are_enforced(client):
    analyst = token(client, "analyst1", "analyst-pass")
    auditor = token(client, "auditor1", "auditor-pass")
    assert client.post("/ask", json={"question": "dose of terazosin?"}, headers=auditor).status_code == 403
    assert client.get("/audit", headers=analyst).status_code == 403
    assert client.post("/ask", json={"question": "dose of terazosin?"}, headers=analyst).status_code == 200


def test_pii_never_reaches_the_audit_log(client):
    h = token(client, "analyst1", "analyst-pass")
    client.post("/ask", json={"question": "Patient 9876543210 dose of terazosin?"}, headers=h)
    audit = client.get("/audit", headers=token(client, "auditor1", "auditor-pass")).json()
    text = json.dumps(audit)
    assert "9876543210" not in text and "[PHONE]" in text and audit["chain_intact"]


def test_question_length_is_validated(client):
    h = token(client, "analyst1", "analyst-pass")
    assert client.post("/ask", json={"question": "x" * 600}, headers=h).status_code == 422


def test_tampering_breaks_the_chain(tmp_path):
    p = str(tmp_path / "a.jsonl")
    for i in range(3):
        log_event(p, {"event": "ask", "n": i})
    assert verify_chain(p)[0]
    lines = open(p).read().splitlines()
    lines[1] = lines[1].replace('"n": 1', '"n": 99')
    open(p, "w").write("\n".join(lines) + "\n")
    assert not verify_chain(p)[0]