"""TDnetの適時開示一覧を取ってくる。"""
from dataclasses import dataclass
from datetime import date
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://www.release.tdnet.info/inbs/"
HEADERS = {"User-Agent": "Mozilla/5.0 (bakaatsu-ir personal bot)"}


@dataclass
class Disclosure:
    id: str          # PDFファイル名（一意）
    date: str        # YYYYMMDD
    time: str        # HH:MM
    code: str        # 4桁（英字コード対応）
    name: str
    title: str
    pdf_url: str
    place: str = ""

    @property
    def ticker(self) -> str:
        return f"{self.code}.T"


def normalize_code(raw: str) -> str:
    raw = raw.strip()
    # TDnetは5桁（末尾0）。72030 -> 7203、130A0 -> 130A
    if len(raw) == 5 and raw.endswith("0"):
        return raw[:4]
    return raw


def parse_list_html(html: str, ymd: str) -> list[Disclosure]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for tr in soup.find_all("tr"):
        def cell(cls):
            return tr.find("td", class_=lambda c: c and cls in c.split())
        t, c, n, ti = cell("kjTime"), cell("kjCode"), cell("kjName"), cell("kjTitle")
        if not (t and c and n and ti):
            continue
        a = ti.find("a")
        if not a or not a.get("href"):
            continue
        href = a["href"].strip()
        place = cell("kjPlace")
        items.append(Disclosure(
            id=href.rsplit("/", 1)[-1],
            date=ymd,
            time=t.get_text(strip=True),
            code=normalize_code(c.get_text(strip=True)),
            name=n.get_text(strip=True),
            title=a.get_text(" ", strip=True),
            pdf_url=href if href.startswith("http") else BASE + href,
            place=place.get_text(strip=True) if place else "",
        ))
    return items


def fetch_day(d: date, session: requests.Session | None = None, max_pages: int = 40) -> list[Disclosure]:
    s = session or requests.Session()
    ymd = d.strftime("%Y%m%d")
    results: list[Disclosure] = []
    for page in range(1, max_pages + 1):
        url = f"{BASE}I_list_{page:03d}_{ymd}.html"
        r = s.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 404:
            break
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        rows = parse_list_html(r.text, ymd)
        if not rows:
            break
        results.extend(rows)
        time.sleep(0.5)  # 相手サーバーに優しく
    return results


def download_pdf(url: str, session: requests.Session | None = None) -> bytes:
    s = session or requests.Session()
    r = s.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.content
