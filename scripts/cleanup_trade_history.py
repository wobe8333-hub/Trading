"""One-off: remove invalid lines from data/trade_history/*.jsonl (see project prompt)."""
import json
import glob

for f in glob.glob("data/trade_history/*.jsonl"):
    lines = open(f, encoding="utf-8").readlines()
    valid = []
    for l in lines:
        try:
            d = json.loads(l)
            if (
                d.get("symbol")
                and d.get("strategy")
                and d.get("timestamp")
                and "2024" not in str(d.get("timestamp", ""))
                and d.get("entry_score", 0) > 0
            ):
                valid.append(l)
        except Exception:
            pass
    removed = len(lines) - len(valid)
    open(f, "w", encoding="utf-8").writelines(valid)
    print(f"cleaned: {f} valid={len(valid)} removed={removed}")
