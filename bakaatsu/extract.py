"""PDFをClaudeに読ませて「数字だけ」抜き出す。点数はscoring.pyがルールで計算する。"""
import base64

from . import config

N = {"type": ["number", "null"]}

EXTRACT_TOOL = {
    "name": "record_disclosure",
    "description": "適時開示PDFから投資判断に必要な数値を記録する。書かれていない数値はnull。",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_positive": {"type": "boolean", "description": "株価に総合的にプラスの内容か"},
            "categories": {
                "type": "array",
                "items": {"type": "string", "enum": [
                    "upward_revision", "downward_revision", "dividend_increase", "dividend_decrease",
                    "tob_target", "mbo", "acquisition", "merger", "buyback", "stock_split",
                    "capital_alliance", "other"]},
            },
            "revision": {
                "type": "object",
                "description": "通期業績予想の修正（百万円）。前回予想と今回予想。",
                "properties": {
                    "prev_operating": N, "new_operating": N,
                    "prev_ordinary": N, "new_ordinary": N,
                    "prev_net": N, "new_net": N,
                },
            },
            "dividend": {
                "type": "object",
                "description": "1株あたり年間配当（円）",
                "properties": {
                    "prev_annual": N, "new_annual": N,
                    "is_resumption": {"type": "boolean", "description": "無配からの復配"},
                    "is_special": {"type": "boolean", "description": "特別・記念配当を含む"},
                },
            },
            "tob": {
                "type": "object",
                "properties": {
                    "is_target_company": {"type": "boolean", "description": "開示会社が買付けられる側か"},
                    "tob_price": N,
                    "stated_premium_pct": {**N, "description": "開示に書かれた直近終値に対するプレミアム%"},
                },
            },
            "deal": {
                "type": "object",
                "properties": {"deal_value_million_yen": {**N, "description": "買収・取得の総額（百万円）"}},
            },
            "buyback": {
                "type": "object",
                "properties": {
                    "ratio_pct": {**N, "description": "発行済株式（自己株除く）に対する上限株数の割合%"},
                    "amount_million_yen": N,
                },
            },
            "surprise_score": {
                "type": "integer", "minimum": 0, "maximum": 15,
                "description": "数字以外の質的な強さ（意外性・持続性・説明の具体性）。0-15",
            },
            "summary": {"type": "string", "description": "60字以内の要約"},
            "key_points": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        },
        "required": ["is_positive", "categories", "surprise_score", "summary"],
    },
}

PROMPT = """あなたは日本株の適時開示を読むアナリストです。
添付PDF（{name} {code}「{title}」）を読み、record_disclosure ツールで数値を記録してください。
- 単位は百万円・円・%に揃える（千円や億円は換算）
- 業績修正は通期の前回予想と今回予想。前回が未定なら null
- 書かれていない数値は推測せず null
- surprise_score は数字に表れない質的な強さだけを評価（一過性の特益頼みなら低く）"""


def extract(pdf_bytes: bytes, code: str, name: str, title: str, client=None) -> dict:
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    if len(pdf_bytes) > config.MAX_PDF_BYTES:
        raise ValueError("PDFが大きすぎる")
    msg = client.messages.create(
        model=config.EXTRACT_MODEL,
        max_tokens=2000,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "record_disclosure"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {
                    "type": "base64", "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf_bytes).decode()}},
                {"type": "text", "text": PROMPT.format(name=name, code=code, title=title)},
            ],
        }],
    )
    for block in msg.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("抽出結果が返ってこなかった")
