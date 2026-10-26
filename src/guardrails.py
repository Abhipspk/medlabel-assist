import re

INJECTION_MSG = "This request looks like an attempt to change my instructions, so I can't process it."

# Used on both questions and retrieved evidence
STRICT = [
    r"ignore (all |any |the |your )?(previous|prior|above|earlier) (instructions|rules|guidance|prompts?)",
    r"disregard (all |any |the |your )?(rules|instructions|guidelines)",
    r"(reveal|print|show|repeat|output) (me )?(your|the) (system |hidden |initial )?(prompt|instructions)",
    r"forget (everything|the labels|your (rules|instructions))",
    r"developer mode|jailbreak",
]
# Questions only (labels legitimately contain text like "Nervous System:")
QUERY_ONLY = [
    r"you are now\b",
    r"pretend (to be|you are|that)",
    r"^\s*(system|assistant)\s*:",
    r"(new|updated) (rule|instruction)s?\s*:",
]
_STRICT = [re.compile(p, re.I | re.M) for p in STRICT]
_QUERY = [re.compile(p, re.I | re.M) for p in STRICT + QUERY_ONLY]

PII = [  # order matters: longer digit patterns first
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("AADHAAR", re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("PHONE", re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}\b|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")),
]


def looks_like_injection(text):
    return any(p.search(text) for p in _QUERY)


def redact_pii(text):
    found = {}
    for name, pat in PII:
        text, n = pat.subn(f"[{name}]", text)
        if n:
            found[name] = n
    return text, found


def drop_injected(evidence):
    """Indirect-injection defence: discard retrieved chunks that try to give orders."""
    return [h for h in evidence if not any(p.search(h["text"]) for p in _STRICT)]