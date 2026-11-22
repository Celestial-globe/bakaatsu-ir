"""既読の開示IDと発火済みアラートを保存（GitHub Actionsがリポジトリにコミットする）。"""
import json
import os
from datetime import datetime, timedelta

PATH = os.getenv("STATE_PATH", "state/state.json")


def load() -> dict:
    if os.path.exists(PATH):
        with open(PATH, encoding="utf-8") as f:
            s = json.load(f)
    else:
        s = {}
    s.setdefault("seen", {})          # id -> YYYYMMDD
    s.setdefault("fired_alerts", [])
    return s


def save(s: dict, keep_days: int = 10):
    cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y%m%d")
    s["seen"] = {k: v for k, v in s["seen"].items() if v >= cutoff}
    os.makedirs(os.path.dirname(PATH) or ".", exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1, sort_keys=True)
