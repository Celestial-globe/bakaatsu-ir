# バカアツIR bot

TDnetの新着開示を平日8:30〜20:00に5分おきにチェックし、AIが100点満点で採点、95点以上だけDiscordに通知します。**AIは発注しません。**

## しくみ

1. TDnetの当日・前日の一覧を取得（既読はスキップ）
2. タイトルで絞り込み（`bakaatsu/config.py` の `TITLE_INCLUDE` / `TITLE_EXCLUDE`）
3. ClaudeがPDFを読んで**数字だけ**抜き出し → `scoring.py` がルールで採点
   - 材料の強さ 最大70点（一番強い材料＋2つ目以降は半分。上方修正率・増配率・TOBプレミアム・M&A規模/時価総額・自社株買い比率…）
   - 時価総額 最大15点（100億以下15 / 300億以下11 / 1000億以下6 / 3000億以下2）
   - AIの質的評価 最大15点
   - 売買代金が1日0.3億未満なら −15、1億未満なら −5
4. 95点以上なら、立場の違うAI3体（モメンタム担当・バリュー担当・弱気担当）が目標株価と撤退ラインを出して、中央値と一緒に通知
5. 見張り中の銘柄（watchlist）に開示が出たら点数に関係なく通知
6. watchlistの価格に到達したら通知（1回だけ。価格を変えるとまた有効になる）

## セットアップ（スマホでもOK）

1. GitHubで新しいリポジトリを作り、このフォルダの中身をアップロード
2. Discordで通知したいチャンネル → 設定 → 連携サービス → ウェブフック → URLをコピー
3. https://console.anthropic.com でAPIキーを発行
4. リポジトリの Settings → Secrets and variables → Actions → New repository secret
   - `ANTHROPIC_API_KEY` … APIキー
   - `DISCORD_WEBHOOK_URL` … Webhook URL
   - `WATCHLIST_YAML` …（任意）見張りリスト。公開リポジトリならこっちに書く
5. Actionsタブ → bakaatsu-ir → Run workflow で手動実行して動作確認
   - 初回は既存の開示を既読にするだけで、通知は出ません

## しきい値の調整

Actions → Run workflow の `date` に過去の日付（例 `20261120`）を入れると、その日の開示を採点してログに点数を出します（通知なし）。何点が何件出るか見て、Settings → Variables に `NOTIFY_THRESHOLD` を入れれば変更できます。

## 注意

- **GitHub Actionsの無料枠**：非公開リポジトリは月2,000分。5分おき×平日だと月およそ2,900分になり超えます。
  - 公開リポジトリにすれば無制限（watchlistはSecretの `WATCHLIST_YAML` に入れる。ログには価格を出さない作り）
  - または `bot.yml` の `*/5` を `*/10` にする
- GitHubの定期実行は混雑時に数分〜十数分遅れることがあります
- 株価はyfinance（無料・約20分遅れ）です
- Claude APIの料金は読んだPDFの数に比例します。`MAX_PDFS_PER_RUN`（既定15）で1回あたりの上限を設定しています
- TDnetのHTML構造が変わると取得できなくなるので、その時は `tdnet.py` の `parse_list_html` を直します

## ローカルで試す

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python -m bakaatsu.main --force --dry-run --date 20261120
pytest
```
