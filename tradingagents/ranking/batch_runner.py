"""Batch analysis: lightweight LLM review of top scoring stocks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional


def _quick_review(code: str, name: str, score: int, factors: dict, reason: str,
                  config: dict) -> dict:
    """One-shot LLM review: generate a concise recommendation for a top stock."""
    from langchain_core.messages import HumanMessage

    provider = config.get("llm_provider", "deepseek")
    backend = config.get("backend_url", "https://api.deepseek.com")

    from tradingagents.llm_clients import create_llm_client
    client = create_llm_client(provider=provider, model=config["quick_think_llm"],
                               base_url=backend)
    llm = client.get_llm()

    prompt = (
        f"你是A股分析师。以下是股票 {code} {name} 的量化评分（百分位，0-100，越高越好）：\n"
        f"综合分: {score}/100\n"
        f"子因子: 价值品质{factors.get('value_quality',0)} 动量{factors.get('momentum',0)} "
        f"资金流{factors.get('money_flow',0)} 情绪{factors.get('sentiment',0)} "
        f"规模{factors.get('size',0)}\n"
        f"突出方向: {reason}\n\n"
        f"请用一句中文(不超过40字)给出该股票的投资看点或风险提示。"
        f"只输出这一句话，不要前缀。"
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        ai_comment = response.content.strip()
    except Exception as e:
        ai_comment = f"AI分析失败: {e}"

    return {
        "code": code,
        "name": name,
        "score": score,
        "ai_comment": ai_comment[:120],
    }


def run_batch_analysis(
    top_stocks: list[dict],
    config: dict,
    max_workers: int = 3,
    progress_callback: Optional[Callable] = None,
) -> list[dict]:
    """Run quick LLM review on top scoring stocks in parallel.

    Args:
        top_stocks: list of dicts with keys: code, name, _score, _factors, _reason
        config: LLM config dict
        max_workers: max parallel calls
        progress_callback: fn(completed, total, code)

    Returns:
        list of {code, name, score, ai_comment}
    """
    results: list[dict] = []
    total = len(top_stocks)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for s in top_stocks:
            fut = executor.submit(
                _quick_review,
                s["code"], s.get("name", ""),
                s.get("_score", 0),
                s.get("_factors", {}),
                s.get("_reason", ""),
                config,
            )
            futures[fut] = s["code"]

        completed = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            if progress_callback:
                progress_callback(completed, total, result["code"])

    # Maintain input order
    ordered = []
    code_order = [s["code"] for s in top_stocks]
    result_map = {r["code"]: r for r in results}
    for code in code_order:
        r = result_map.get(code)
        if r:
            ordered.append(r)
        else:
            ordered.append({"code": code, "name": "", "score": 0, "ai_comment": "分析失败"})

    return ordered
