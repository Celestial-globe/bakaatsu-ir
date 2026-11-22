"""エントリポイント。
  python -m bakaatsu.main                 # 本番（時間外なら何もしない）
  python -m bakaatsu.main --force         # 時間外でも動かす
  python -m bakaatsu.main --date 20261120 --dry-run --force
                                          # 過去日を採点だけして通知しない（しきい値の調整用）
"""
import argparse
import logging
from datetime import date, datetime, timedelta, timezone

import requests

from . import alerts, config, extract, market, notify, scoring, state, tdnet

JST = timezone(timedelta(hours=9))
log = logging.getLogger("bakaatsu")


def is_market_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    if (d.month, d.day) in {(12, 31), (1, 1), (1, 2), (1, 3)}:
        return False
    try:
        import jpholiday
        return not jpholiday.is_holiday(d)
    except ImportError:
        return True


def in_window(now: datetime) -> bool:
    if not is_market_day(now.date()):
        return False
    hm = (now.hour, now.minute)
    return config.START_HHMM <= hm <= config.END_HHMM


def run(args):
    now = datetime.now(JST)
    if not args.force and not in_window(now):
        log.info("稼働時間外 %s", now.strftime("%Y-%m-%d %H:%M"))
        return

    st = state.load()
    seen: dict = st["seen"]
    bootstrap = not seen and not args.date
    session = requests.Session()

    days = [datetime.strptime(args.date, "%Y%m%d").date()] if args.date else [now.date() - timedelta(days=1), now.date()]
    disclosures = []
    for d in days:
        try:
            disclosures += tdnet.fetch_day(d, session)
        except Exception as e:
            log.warning("TDnet取得失敗 %s: %s", d, e)
    log.info("開示 %d件", len(disclosures))

    watch = alerts.load_watchlist()
    watch_codes = {w["code"] for w in watch}

    new = [x for x in disclosures if x.id not in seen]
    if bootstrap:
        # 初回は既存分を既読にするだけ（いきなり大量にAPIを使わない）
        for x in new:
            seen[x.id] = x.date
        log.info("初回起動：%d件を既読化", len(new))
        new = []

    processed = 0
    for x in new:
        if x.code in watch_codes:
            notify.holding_disclosure(x, args.dry_run)

        if not config.title_is_candidate(x.title):
            seen[x.id] = x.date
            continue
        if processed >= config.MAX_PDFS_PER_RUN:
            log.info("上限到達、残りは次回")
            break  # seenにしないので次回また拾う
        processed += 1
        try:
            handle(x, args.dry_run, session)
        except Exception as e:
            log.exception("処理失敗 %s", x.title)
            notify.error(f"[{x.code}] {x.title}\n{e}", args.dry_run)
        seen[x.id] = x.date

    # ⑥価格アラート
    if not args.date:
        fired = set(st["fired_alerts"])
        n = alerts.check(watch, market.get_price, fired,
                         lambda it, side, p: notify.price_alert(it, side, p, args.dry_run))
        st["fired_alerts"] = sorted(fired)
        log.info("価格アラート %d件 / 見張り %d銘柄", n, len(watch))

    if not args.dry_run:
        state.save(st)


def handle(x, dry_run, session):
    pdf = tdnet.download_pdf(x.pdf_url, session)
    ex = extract.extract(pdf, x.code, x.name, x.title)
    q = market.get_quote(x.ticker)
    sc = scoring.score(ex, market_cap=q.market_cap, price=q.price, turnover=q.avg_turnover)
    log.info("%3d点 [%s] %s %s", sc.total, x.code, x.name, x.title)
    if sc.total < config.NOTIFY_THRESHOLD:
        return
    from . import agents
    review = agents.committee({
        "銘柄": f"{x.name}({x.code})", "開示": x.title, "開示時刻": f"{x.date} {x.time}",
        "要約": ex.get("summary"), "ポイント": ex.get("key_points"), "抽出データ": ex,
        "現在値": q.price, "時価総額": q.market_cap, "PER": q.per, "PBR": q.pbr,
        "平均売買代金": q.avg_turnover, "採点": sc.total,
    })
    notify.hot_ir(x, sc, ex, q, review, dry_run)


def cli():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--date", help="YYYYMMDD 過去日を採点")
    run(p.parse_args())


if __name__ == "__main__":
    cli()
