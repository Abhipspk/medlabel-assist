import contextvars
import functools
import json
import os
import time

_spans = contextvars.ContextVar("spans", default=None)


def start_trace():
    """Begin collecting spans for the current request."""
    spans = []
    _spans.set(spans)
    return spans


def traced(name):
    """Decorator: record how long this function took as a span."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                spans = _spans.get()
                if spans is not None:
                    spans.append({"span": name, "ms": round((time.perf_counter() - t) * 1000)})
        return wrapper
    return deco


def write_trace(path, record):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")