1. Source: openFDA bulk labels, first partition only. CC0, no API key or cost.
2. Filter: prescription labels only. 16,016 records lacked product_type and were excluded (known limitation).
3. Chunking: ~1000 chars, sentence boundaries, 1-sentence overlap, contextual header per chunk.
4. Missing section: system states the section is absent; it never guesses.