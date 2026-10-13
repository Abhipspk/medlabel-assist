import zipfile
from pathlib import Path
import requests

INDEX_URL = "https://api.fda.gov/download.json"
OUT_DIR = Path("data/raw")
OUT_DIR.mkdir(parents=True, exist_ok=True)

index = requests.get(INDEX_URL, timeout=60)
index.raise_for_status()
label = index.json()["results"]["drug"]["label"]
parts = label["partitions"]
print("Total records:", label.get("total_records"), "| parts:", len(parts))

first = parts[0]
print("Downloading:", first["file"], "| size_mb:", first.get("size_mb"))

zip_path = OUT_DIR / Path(first["file"]).name
with requests.get(first["file"], stream=True, timeout=120) as r:
    r.raise_for_status()
    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)

with zipfile.ZipFile(zip_path) as z:
    z.extractall(OUT_DIR)
    print("Extracted:", z.namelist())