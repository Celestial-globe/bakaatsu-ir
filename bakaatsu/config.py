"""設定まわり。数字はここをいじれば調整できる。"""
import os
import re

# --- 稼働時間（JST） ---
START_HHMM = (8, 30)
END_HHMM = (20, 0)

# --- 通知のしきい値 ---
NOTIFY_THRESHOLD = int(os.getenv("NOTIFY_THRESHOLD", "95"))

# 1回の実行でAIに読ませるPDFの上限（API代の暴走防止）
MAX_PDFS_PER_RUN = int(os.getenv("MAX_PDFS_PER_RUN", "15"))

# --- Claude ---
EXTRACT_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
AGENT_MODEL = os.getenv("AGENT_MODEL", EXTRACT_MODEL)
MAX_PDF_BYTES = 30 * 1024 * 1024

# --- ②タイトルでざっくり絞る ---
TITLE_INCLUDE = re.compile(
    r"上方修正|業績予想の修正|業績予想修正|通期業績予想|配当予想の修正|増配|復配|特別配当|記念配当|"
    r"公開買付け|公開買付|TOB|MBO|マネジメント・バイアウト|子会社化|株式の取得|株式取得|"
    r"合併|経営統合|株式交換|事業譲受|買収|自己株式の取得|自己株式取得|株式分割|"
    r"資本業務提携|資本提携|第三者割当.*引受"
)
TITLE_EXCLUDE = re.compile(
    r"訂正|一部変更|説明資料|説明会|補足資料|ETF|ETN|REIT|投資法人|上場投資信託|"
    r"取得状況|取得結果|取得終了|進捗|結果に関する|延長"
)

# 決算短信も読むか（決算期は数百件になるので既定OFF）
INCLUDE_KESSAN_TANSHIN = os.getenv("INCLUDE_KESSAN_TANSHIN", "0") == "1"
TANSHIN_PATTERN = re.compile(r"決算短信")


def title_is_candidate(title: str) -> bool:
    if TITLE_EXCLUDE.search(title):
        return False
    if TITLE_INCLUDE.search(title):
        return True
    if INCLUDE_KESSAN_TANSHIN and TANSHIN_PATTERN.search(title):
        return True
    return False
