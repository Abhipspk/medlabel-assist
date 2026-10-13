import time
import requests

URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"

start = time.time()
resp = requests.post(
    URL,
    json={"model": MODEL,
          "prompt": "In one sentence, what is a contraindication?",
          "stream": False},
    timeout=300,
)
resp.raise_for_status()
print(resp.json()["response"])
print(f"Took {time.time() - start:.1f} seconds")