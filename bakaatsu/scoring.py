"""100点満点の採点（ルールベース）。
  材料の強さ   最大70点（上方修正・増配・TOB・M&A・自社株買い…の合算）
  時価総額     最大15点（小さいほど加点）
  AIの質的評価 最大15点
  流動性ペナルティ（売買代金が細いと減点）
"""
from dataclasses import dataclass, field


@dataclass
class ScoreResult:
    total: int
    breakdown: list[tuple[str, int]] = field(default_factory=list)


def _step(value, table):
    """table: [(しきい値, 点), ...] を上から見て最初に超えた点を返す"""
    if value is None:
        return 0
    for th, pts in table:
        if value >= th:
            return pts
    return 0


def pct_change(prev, new):
    if prev is None or new is None or prev == 0:
        return None
    return (new - prev) / abs(prev) * 100


def revision_points(rev: dict) -> tuple[int, str]:
    if not rev:
        return 0, ""
    best_rate, label = None, ""
    for key, jp in (("operating", "営業益"), ("ordinary", "経常益"), ("net", "純利益")):
        prev, new = rev.get(f"prev_{key}"), rev.get(f"new_{key}")
        if prev is not None and new is not None and prev <= 0 < new:
            return 60, f"{jp}黒字転換"
        r = pct_change(prev, new)
        if r is not None and (best_rate is None or r > best_rate):
            best_rate, label = r, jp
        if key == "operating" and r is not None:
            break  # 営業益が取れたら最優先
    pts = _step(best_rate, [(100, 65), (50, 55), (30, 45), (20, 32), (10, 18), (0.01, 6)])
    return pts, f"{label}{best_rate:+.0f}%" if best_rate is not None else ""


def dividend_points(div: dict) -> tuple[int, str]:
    if not div:
        return 0, ""
    if div.get("is_resumption"):
        return 40, "復配"
    r = pct_change(div.get("prev_annual"), div.get("new_annual"))
    pts = _step(r, [(100, 55), (50, 45), (30, 34), (15, 20), (0.01, 8)])
    if pts and div.get("is_special"):
        pts = max(pts - 6, 4)  # 一過性なので割引
    return pts, f"配当{r:+.0f}%" if r is not None else ""


def tob_points(tob: dict, price: float | None) -> tuple[int, str]:
    if not tob or not tob.get("is_target_company"):
        return 0, ""
    prem = tob.get("stated_premium_pct")
    if prem is None and tob.get("tob_price") and price:
        prem = (tob["tob_price"] / price - 1) * 100
    pts = _step(prem, [(50, 70), (30, 62), (20, 50), (0.01, 35)]) or 30
    return pts, f"TOBプレミアム{prem:.0f}%" if prem is not None else "TOB対象"


def deal_points(deal: dict, market_cap: float | None) -> tuple[int, str]:
    v = (deal or {}).get("deal_value_million_yen")
    if not v or not market_cap:
        return 0, ""
    ratio = v * 1_000_000 / market_cap * 100
    pts = _step(ratio, [(50, 55), (20, 40), (10, 25), (0.01, 8)])
    return pts, f"M&A規模 時価総額比{ratio:.0f}%"


def buyback_points(bb: dict) -> tuple[int, str]:
    r = (bb or {}).get("ratio_pct")
    pts = _step(r, [(10, 50), (5, 35), (3, 20), (0.01, 6)])
    return pts, f"自社株買い{r:.1f}%" if r else ""


def mcap_points(mc: float | None) -> tuple[int, str]:
    if not mc:
        return 0, "時価総額不明"
    oku = mc / 1e8
    pts = _step(-oku, [(-100, 15), (-300, 11), (-1000, 6), (-3000, 2)])
    return pts, f"時価総額{oku:,.0f}億円"


def liquidity_penalty(turnover: float | None) -> tuple[int, str]:
    if turnover is None:
        return 0, ""
    oku = turnover / 1e8
    if oku < 0.3:
        return -15, f"売買代金{oku:.2f}億/日（細すぎ）"
    if oku < 1:
        return -5, f"売買代金{oku:.2f}億/日"
    return 0, ""


def score(ex: dict, market_cap=None, price=None, turnover=None) -> ScoreResult:
    cats = set(ex.get("categories") or [])
    if not ex.get("is_positive") or cats & {"downward_revision", "dividend_decrease"} and not (
        cats & {"upward_revision", "dividend_increase", "tob_target", "mbo"}
    ):
        return ScoreResult(0, [("ネガティブ判定", 0)])

    material = []
    material.append(revision_points(ex.get("revision") or {}) if "upward_revision" in cats else (0, ""))
    material.append(dividend_points(ex.get("dividend") or {}) if "dividend_increase" in cats else (0, ""))
    tob = dict(ex.get("tob") or {})
    if "mbo" in cats:
        tob["is_target_company"] = True
    material.append(tob_points(tob, price))
    if cats & {"acquisition", "merger"}:
        material.append(deal_points(ex.get("deal") or {}, market_cap))
    if "buyback" in cats:
        material.append(buyback_points(ex.get("buyback") or {}))
    if "stock_split" in cats:
        material.append((6, "株式分割"))
    if "capital_alliance" in cats:
        material.append((6, "資本業務提携"))

    material = sorted([m for m in material if m[0] > 0], reverse=True)
    # 一番強い材料はそのまま、2つ目以降は半分だけ加算
    mat_total = 0
    for i, (p, _) in enumerate(material):
        mat_total += p if i == 0 else p // 2
    mat_total = min(mat_total, 70)

    breakdown = [(label, p) for p, label in material]
    mc_p, mc_l = mcap_points(market_cap)
    ai_p = max(0, min(15, int(ex.get("surprise_score") or 0)))
    lq_p, lq_l = liquidity_penalty(turnover)

    breakdown += [(mc_l, mc_p), ("AI質的評価", ai_p)]
    if lq_p:
        breakdown.append((lq_l, lq_p))
    total = max(0, min(100, mat_total + mc_p + ai_p + lq_p))
    return ScoreResult(total, breakdown)
