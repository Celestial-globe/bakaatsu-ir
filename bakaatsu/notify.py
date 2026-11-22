"""Discord Webhookへ通知。"""
import os
import logging

import requests

log = logging.getLogger(__name__)


def _cut(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def _yen(v):
    return f"{v:,.0f}円" if isinstance(v, (int, float)) else "-"


def send(payload: dict, dry_run: bool = False):
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if dry_run or not url:
        log.info("[dry-run] discord: %s", payload.get("embeds", [{}])[0].get("title"))
        return
    r = requests.post(url, json=payload, timeout=20)
    if r.status_code >= 300:
        log.error("discord %s %s", r.status_code, r.text[:200])


def hot_ir(d, sc, ex, quote, review, dry_run=False):
    lines = "\n".join(f"・{l}: {p:+d}" for l, p in sc.breakdown if l)
    fields = [
        {"name": "開示", "value": _cut(f"{d.time} {d.title}", 1024)},
        {"name": "要約", "value": _cut(ex.get("summary"), 1024)},
        {"name": "採点内訳", "value": _cut(lines, 1024)},
        {"name": "現在値（約20分遅れ）", "value": _yen(quote.price), "inline": True},
        {"name": "目標株価(中央値)", "value": _yen(review.get("target_price")), "inline": True},
        {"name": "撤退ライン(中央値)", "value": _yen(review.get("stop_loss")), "inline": True},
    ]
    for o in review.get("opinions", []):
        fields.append({
            "name": f"{o.get('persona')}：{o.get('stance')}",
            "value": _cut(f"目標{_yen(o.get('target_price'))} / 撤退{_yen(o.get('stop_loss'))}\n{o.get('reason')}", 1024),
        })
    send({
        "content": "🔥 **バカアツIR** 🔥",
        "embeds": [{
            "title": _cut(f"{sc.total}点 [{d.code}] {d.name}", 256),
            "url": d.pdf_url,
            "color": 0xFF3300,
            "fields": fields[:25],
            "footer": {"text": "AIは発注しません。最終判断はご自身で。"},
        }],
    }, dry_run)


def holding_disclosure(d, dry_run=False):
    send({"embeds": [{
        "title": _cut(f"📌 見張り中の銘柄に開示 [{d.code}] {d.name}", 256),
        "url": d.pdf_url,
        "description": _cut(f"{d.time} {d.title}", 2000),
        "color": 0x3399FF,
    }]}, dry_run)


def price_alert(item, side, price, dry_run=False):
    arrow = "⬆️ 到達" if side == "above" else "⬇️ 割れ"
    target = item.get(side)
    send({"embeds": [{
        "title": _cut(f"{arrow} [{item['code']}] {item.get('name', '')} {_yen(price)}", 256),
        "description": _cut(f"設定 {_yen(target)} に{'到達' if side == 'above' else '到達（撤退ライン）'}\n{item.get('memo', '')}", 2000),
        "color": 0x33CC66 if side == "above" else 0xCC3333,
    }]}, dry_run)


def error(msg, dry_run=False):
    send({"embeds": [{"title": "⚠️ botエラー", "description": _cut(msg, 2000), "color": 0x999999}]}, dry_run)
