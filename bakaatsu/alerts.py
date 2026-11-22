"""⑥「この値段来たら教えて」。watchlist.yml（またはSecretのWATCHLIST_YAML）を見張る。"""
import hashlib
import os

import yaml


def load_watchlist(path="watchlist.yml") -> list[dict]:
    text = os.getenv("WATCHLIST_YAML")  # 公開リポジトリならSecretに入れる
    if not text and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
    items = yaml.safe_load(text or "") or []
    out = []
    for it in items:
        if isinstance(it, dict) and it.get("code"):
            it["code"] = str(it["code"]).strip()
            out.append(it)
    return out


def alert_key(code, side, target) -> str:
    # 状態ファイルに価格をそのまま残さない（公開リポジトリ対策）
    return hashlib.sha256(f"{code}|{side}|{target}".encode()).hexdigest()[:16]


def check(items, get_price, fired: set, notify) -> int:
    count = 0
    for it in items:
        sides = [s for s in ("above", "below") if isinstance(it.get(s), (int, float))]
        if not sides:
            continue
        price = get_price(f"{it['code']}.T")
        if price is None:
            continue
        for side in sides:
            target = it[side]
            hit = price >= target if side == "above" else price <= target
            key = alert_key(it["code"], side, target)
            if hit and key not in fired:
                notify(it, side, price)
                fired.add(key)
                count += 1
    return count
