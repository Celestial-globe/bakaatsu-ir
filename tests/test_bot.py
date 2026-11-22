from datetime import date, datetime, timedelta, timezone

from bakaatsu import alerts, config, scoring, tdnet
from bakaatsu.main import in_window

JST = timezone(timedelta(hours=9))

SAMPLE = """
<table id="main-list-table">
<tr>
<td class="oddnew-L kjTime" noWrap>15:30</td>
<td class="oddnew-M kjCode" noWrap>12340</td>
<td class="oddnew-M kjName" noWrap>テスト工業</td>
<td class="oddnew-M kjTitle" align="left"><a href="140120261120500001.pdf" target="_blank">通期業績予想の上方修正に関するお知らせ</a></td>
<td class="oddnew-M kjXbrl" noWrap></td>
<td class="oddnew-M kjPlace" noWrap>東</td>
<td class="oddnew-R kjHistroy" noWrap></td>
</tr>
<tr>
<td class="evennew-L kjTime" noWrap>15:00</td>
<td class="evennew-M kjCode" noWrap>130A0</td>
<td class="evennew-M kjName" noWrap>新コード社</td>
<td class="evennew-M kjTitle" align="left"><a href="140120261120500002.pdf">定款一部変更に関するお知らせ</a></td>
<td class="evennew-M kjXbrl" noWrap></td>
<td class="evennew-M kjPlace" noWrap>東</td>
<td class="evennew-R kjHistroy" noWrap></td>
</tr>
</table>"""


def test_parse():
    rows = tdnet.parse_list_html(SAMPLE, "20261120")
    assert len(rows) == 2
    assert rows[0].code == "1234" and rows[1].code == "130A"
    assert rows[0].pdf_url.endswith("/inbs/140120261120500001.pdf")
    assert rows[0].ticker == "1234.T"


def test_title_filter():
    assert config.title_is_candidate("通期業績予想の上方修正に関するお知らせ")
    assert config.title_is_candidate("株式会社ABCによる当社株式に対する公開買付けに関する賛同の意見表明")
    assert not config.title_is_candidate("定款一部変更に関するお知らせ")
    assert not config.title_is_candidate("（訂正）業績予想の修正に関するお知らせ")
    assert not config.title_is_candidate("自己株式の取得状況に関するお知らせ")


def test_window():
    assert in_window(datetime(2026, 11, 20, 8, 30, tzinfo=JST))       # 金
    assert in_window(datetime(2026, 11, 20, 20, 0, tzinfo=JST))
    assert not in_window(datetime(2026, 11, 20, 20, 5, tzinfo=JST))
    assert not in_window(datetime(2026, 11, 20, 8, 25, tzinfo=JST))
    assert not in_window(datetime(2026, 11, 21, 12, 0, tzinfo=JST))   # 土
    assert not in_window(datetime(2026, 11, 23, 12, 0, tzinfo=JST))   # 勤労感謝の日


def test_score_monster():
    ex = {"is_positive": True, "categories": ["upward_revision", "dividend_increase"],
          "revision": {"prev_operating": 1000, "new_operating": 1800},
          "dividend": {"prev_annual": 20, "new_annual": 40}, "surprise_score": 14}
    r = scoring.score(ex, market_cap=80e8, price=1000, turnover=3e8)
    # 営業益+80% → 55, 増配+100% → 55/2=27 → 材料70上限, +15, +14 = 99
    assert r.total == 99


def test_score_tob():
    ex = {"is_positive": True, "categories": ["tob_target"],
          "tob": {"is_target_company": True, "tob_price": 1600}, "surprise_score": 15}
    r = scoring.score(ex, market_cap=90e8, price=1000, turnover=2e8)
    # プレミアム60% → 70, +15, +15 = 100
    assert r.total == 100


def test_score_negative_and_liquidity():
    ex = {"is_positive": False, "categories": ["downward_revision"], "surprise_score": 0}
    assert scoring.score(ex).total == 0
    ex = {"is_positive": True, "categories": ["buyback"], "buyback": {"ratio_pct": 12}, "surprise_score": 10}
    r = scoring.score(ex, market_cap=50e8, turnover=0.1e8)
    assert r.total == 50 + 15 + 10 - 15


def test_kurotenkan():
    pts, label = scoring.revision_points({"prev_operating": -200, "new_operating": 300})
    assert pts == 60 and "黒字転換" in label


def test_alerts_fire_once():
    items = [{"code": "7203", "above": 3000, "below": 2500}]
    fired, sent = set(), []
    n = alerts.check(items, lambda t: 3100, fired, lambda it, s, p: sent.append(s))
    assert n == 1 and sent == ["above"]
    n = alerts.check(items, lambda t: 3200, fired, lambda it, s, p: sent.append(s))
    assert n == 0
