"""株価・時価総額・売買代金（yfinance。無料なので約20分遅れ）。"""
from dataclasses import dataclass
import logging

log = logging.getLogger(__name__)


@dataclass
class Quote:
    price: float | None = None
    market_cap: float | None = None        # 円
    avg_turnover: float | None = None      # 直近20日の平均売買代金（円）
    per: float | None = None
    pbr: float | None = None


def get_quote(ticker: str) -> Quote:
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        q = Quote()
        hist = tk.history(period="1mo", auto_adjust=False)
        if not hist.empty:
            q.price = float(hist["Close"].iloc[-1])
            tail = hist.tail(20)
            q.avg_turnover = float((tail["Close"] * tail["Volume"]).mean())
        try:
            fi = tk.fast_info
            q.market_cap = float(fi.get("market_cap") or fi.get("marketCap") or 0) or None
            if q.price is None:
                q.price = float(fi.get("last_price") or 0) or None
        except Exception:
            pass
        try:
            info = tk.info
            q.market_cap = q.market_cap or info.get("marketCap")
            q.per = info.get("trailingPE")
            q.pbr = info.get("priceToBook")
        except Exception:
            pass
        return q
    except Exception as e:  # 取れなくても止めない
        log.warning("quote failed %s: %s", ticker, e)
        return Quote()


def get_price(ticker: str) -> float | None:
    return get_quote(ticker).price
