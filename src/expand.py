import re

# (pattern in the user's wording) -> label vocabulary to add to the SEARCH query only
RULES = [
    (r"poison|overdos|too much|toxic", "overdosage overdose"),
    (r"unwanted effect|side effect|adverse", "adverse reactions"),
    (r"why would .*(give|prescribe)|used for|treat", "indications and usage indicated for"),
    (r"daily amount|how much|dosing|dose", "dosage and administration"),
    (r"unsafe|should not take|must not|avoid", "contraindications warnings"),
    (r"alongside|together with|combine|other medicines|interact", "drug interactions"),
]


def expand_query(question):
    q = question.lower()
    extra = [add for pattern, add in RULES if re.search(pattern, q)]
    return question + (" " + " ".join(extra) if extra else "")