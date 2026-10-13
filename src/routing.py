import re

RULES = [
    (r"should not|shouldn't|must not|not be (used|given|taken)|avoid|contraindicat|cannot take|can't take|not recommended",
     ["contraindications", "boxed_warning", "warnings"]),
    (r"interact|taken with|take with|together with|combine|combination|along with",
     ["drug_interactions"]),
    (r"side effect|adverse|reaction",
     ["adverse_reactions"]),
    (r"\bdose\b|dosage|how much|how often|how to take|titrat|maximum",
     ["dosage_and_administration"]),
    (r"used for|indicated|indication|treat",
     ["indications_and_usage"]),
    (r"overdose|overdosage|too much",
     ["overdosage"]),
    (r"pregnan|breast|nursing|pediatric|children|elderly|geriatric|renal impairment|hepatic impairment|lactation",
     ["use_in_specific_populations", "warnings"]),
    (r"warning|precaution|risk|serious|boxed|black box",
     ["boxed_warning", "warnings"]),
]


def route_sections(question):
    q = question.lower()
    out = []
    for pattern, sections in RULES:
        if re.search(pattern, q):
            for s in sections:
                if s not in out:
                    out.append(s)
    return out or None