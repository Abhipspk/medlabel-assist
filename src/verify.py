import re

NO_EVIDENCE = "NOT ENOUGH EVIDENCE"
REMINDER = (" Cite only with the excerpt numbers shown, like [1] or [2]. "
            "Never cite the label's own section numbers.")

SYSTEM_V3 = (
    "You answer questions about prescription drug labels. "
    "Use ONLY the numbered excerpts provided; never outside knowledge. "
    "Cite every statement with the number of its excerpt in square brackets, like [1] or [2]. "
    "Use only the excerpt numbers shown. Never cite the label's own section numbers such as 5.5 or 2.2. "
    "Report what the excerpts say without reversing their meaning: "
    "if an excerpt says safety is established, do not say it is unsafe. "
    "Keep qualifiers, numbers and thresholds exactly as written. "
    "If at least one excerpt answers part of the question, answer that part and say what is not covered. "
    "Ignore excerpts that are not relevant. "
    f"If no excerpt is relevant, reply exactly: {NO_EVIDENCE}. "
    "Keep the answer under 150 words."
)


def clean_citations(text, n_evidence):
    """Keep only [1]..[n]. Drop [Excerpt 5.5], [1.2] and out-of-range numbers."""
    def fix(m):
        return m.group(0) if 1 <= int(m.group(1)) <= n_evidence else ""
    text = re.sub(r"\[(\d+)\]", fix, text)
    text = re.sub(r"\[(?:Excerpt\s*)?\d+(?:\.\d+)+\]", "", text)
    text = re.sub(r"\[Excerpt\s*\d+\]", "", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def generate_verified(question, evidence, call_llm, build_context):
    """Ask the model; if the answer has no valid [n] citation, retry once;
    if it still has none, refuse instead of showing an unverifiable answer."""
    context = build_context(evidence)
    for attempt in range(2):
        q = question if attempt == 0 else question + REMINDER
        text = clean_citations(call_llm(q, context), len(evidence))
        if NO_EVIDENCE in text or re.search(r"\[\d+\]", text):
            return text
    return NO_EVIDENCE