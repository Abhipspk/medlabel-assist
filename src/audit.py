import hashlib
import json
import os
import threading
import time

_LOCK = threading.Lock()
GENESIS = "0" * 64


def _digest(prev, record):
    return hashlib.sha256((prev + json.dumps(record, sort_keys=True)).encode()).hexdigest()


def _entries(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def log_event(path, record):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with _LOCK:
        entries = _entries(path)
        prev = entries[-1]["hash"] if entries else GENESIS
        record = {**record, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        entry = {"record": record, "prev": prev, "hash": _digest(prev, record)}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    return entry


def read_events(path, limit=50):
    return _entries(path)[-limit:]


def verify_chain(path):
    """Returns (ok, number_of_entries). Any edited, deleted or reordered line breaks it."""
    prev = GENESIS
    entries = _entries(path)
    for e in entries:
        if e["prev"] != prev or e["hash"] != _digest(prev, e["record"]):
            return False, len(entries)
        prev = e["hash"]
    return True, len(entries)