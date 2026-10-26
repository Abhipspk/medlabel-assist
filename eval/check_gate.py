import json
import sys

sys.path.insert(0, "src")
from gate import failures, metrics  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else "eval/results_e2e_latest.json"
m = metrics(json.load(open(path, encoding="utf-8")))
for k, v in m.items():
    print(f"  {k:34s} {v:.2f}")
bad = failures(m)
if bad:
    print("\nGATE FAILED:")
    for b in bad:
        print("  -", b)
    sys.exit(1)
print("\nGATE PASSED")