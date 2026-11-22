"""④投資担当AI委員会。立場の違う3体に目標株価と撤退ラインを出させる。"""
import json
import statistics
from concurrent.futures import ThreadPoolExecutor

from . import config

PERSONAS = {
    "モメンタム担当": "短期の需給と値動きを重視するトレーダー。開示翌日〜数週間の値幅を狙う。",
    "バリュー担当": "PER・PBR・利益水準から妥当株価を考えるファンダメンタルズ派。",
    "弱気担当": "必ず『買わない理由』『織り込み済みの可能性』『一過性要因』を探すリスク管理役。楽観は禁止。",
}

OPINION_TOOL = {
    "name": "record_opinion",
    "description": "投資判断を記録する",
    "input_schema": {
        "type": "object",
        "properties": {
            "stance": {"type": "string", "enum": ["買い", "様子見", "見送り"]},
            "target_price": {"type": "number", "description": "目標株価（円）"},
            "stop_loss": {"type": "number", "description": "撤退ライン（円）"},
            "horizon": {"type": "string", "description": "想定期間"},
            "reason": {"type": "string", "description": "80字以内"},
        },
        "required": ["stance", "target_price", "stop_loss", "reason"],
    },
}


def _ask(client, persona, role, payload):
    msg = client.messages.create(
        model=config.AGENT_MODEL,
        max_tokens=800,
        system=f"あなたは日本株の{persona}。{role} 発注はしない。意見だけ述べる。",
        tools=[OPINION_TOOL],
        tool_choice={"type": "tool", "name": "record_opinion"},
        messages=[{"role": "user", "content":
                   "次の開示について目標株価と撤退ラインを出して。\n" +
                   json.dumps(payload, ensure_ascii=False, default=str)}],
    )
    for b in msg.content:
        if b.type == "tool_use":
            return {"persona": persona, **b.input}
    return None


def committee(payload: dict, client=None) -> dict:
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(_ask, client, p, r, payload) for p, r in PERSONAS.items()]
        opinions = []
        for f in futs:
            try:
                o = f.result()
                if o:
                    opinions.append(o)
            except Exception as e:
                opinions.append({"persona": "?", "stance": "エラー", "reason": str(e)[:80]})
    return summarize(opinions)


def summarize(opinions: list[dict]) -> dict:
    tps = [o["target_price"] for o in opinions if isinstance(o.get("target_price"), (int, float))]
    sls = [o["stop_loss"] for o in opinions if isinstance(o.get("stop_loss"), (int, float))]
    return {
        "opinions": opinions,
        "target_price": statistics.median(tps) if tps else None,
        "stop_loss": statistics.median(sls) if sls else None,
    }
