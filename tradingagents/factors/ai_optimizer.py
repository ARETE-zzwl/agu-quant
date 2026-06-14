"""AI-driven factor optimization: weight tuning, synergy analysis, discovery."""

from __future__ import annotations

import json


class AIWeightOptimizer:
    """Use LLM to analyze factor reports and suggest optimal weights."""

    def _build_prompt(self, reports: list[dict], current_weights: dict) -> str:
        lines = [
            "你是一位量化投资专家。以下是各因子的历史表现报告：",
            "",
            "| 因子 | IC均值 | IC_IR | 年化收益% | 夏普 | 最大回撤% | 胜率% | 综合分 |",
            "|------|--------|-------|-----------|------|-----------|--------|--------|",
        ]
        for r in reports:
            lines.append(
                f"| {r['factor']} | {r['ic_mean']:.4f} | {r['ic_ir']:.1f} | "
                f"{r['annual_return']*100:.1f} | {r['sharpe_ratio']:.1f} | "
                f"{r['max_drawdown']*100:.1f} | {r['win_rate']:.1f} | {r['score']:.1f} |"
            )

        lines.extend([
            "",
            "当前权重: " + ", ".join(f"{k}={v:.2f}" for k, v in current_weights.items()),
            "",
            "请根据表现报告，给出新的因子权重分配建议。要求：",
            "1. 所有权重之和=1.0",
            "2. 综合分越高的因子应获得更高权重",
            "3. IC_IR更高、夏普更高、最大回撤更小的因子优先",
            "4. 避免过度集中在单一因子(单因子不超过40%)",
            "5. 输出JSON格式: {\"weights\": {\"因子名\": 0.XX, ...}, \"reasoning\": \"理由...\"}",
            "",
            "只输出JSON，不要其他内容。",
        ])
        return "\n".join(lines)

    def optimize(
        self,
        reports: list[dict],
        current_weights: dict[str, float],
        llm_config: dict,
    ) -> dict:
        """Return {weights: {factor: weight}, reasoning: str}."""
        from tradingagents.llm_clients import create_llm_client
        from langchain_core.messages import HumanMessage

        prompt = self._build_prompt(reports, current_weights)

        try:
            client = create_llm_client(
                provider=llm_config.get("llm_provider", "deepseek"),
                model=llm_config.get("deep_think_llm", "deepseek-chat"),
                base_url=llm_config.get("backend_url", "https://api.deepseek.com"),
            )
            llm = client.get_llm()
            response = llm.invoke([HumanMessage(content=prompt)])
            text = response.content.strip()

            # Parse JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)
            weights = data.get("weights", {})
            reasoning = data.get("reasoning", "")

            # Normalize weights to sum to 1.0
            total = sum(w for w in weights.values())
            if total > 0:
                weights = {k: round(v / total, 4) for k, v in weights.items()}

            return {"weights": weights, "reasoning": reasoning}

        except Exception as e:
            return {
                "weights": current_weights,
                "reasoning": f"AI优化失败({e})，保留当前权重",
            }


class AISynergyAnalyzer:
    """LLM analyzes multi-factor synergy relationships."""

    def analyze(
        self,
        reports: list[dict],
        corr_matrix: list[list],
        factor_names: list[str],
        llm_config: dict,
    ) -> str:
        """Return natural language analysis of factor synergy."""
        prompt = (
            "你是一位量化分析师。以下是各因子的表现和相关矩阵：\n\n"
            "--- 因子表现 ---\n"
        )
        for r in reports:
            prompt += (
                f"- {r['factor']}: IC={r['ic_mean']:.3f}, IC_IR={r['ic_ir']:.1f}, "
                f"夏普={r['sharpe_ratio']:.1f}, 回撤={r['max_drawdown']*100:.1f}%\n"
            )

        prompt += "\n--- 因子相关性矩阵 ---\n"
        prompt += "       " + "  ".join(f"{n[:8]:>8}" for n in factor_names) + "\n"
        for i, row in enumerate(corr_matrix):
            prompt += f"{factor_names[i][:8]:>8} " + "  ".join(
                f"{v:8.3f}" if isinstance(v, (int, float)) else "    None"
                for v in row
            ) + "\n"

        prompt += (
            "\n请分析:\n"
            "1. 哪些因子对是互补的(低相关+双良好)？如何组合效果最好？\n"
            "2. 哪些因子是冗余的(高相关)？建议合并或放弃哪个？\n"
            "3. 建议的最优因子组合(3-5个)以及各自的角色\n"
            "用简洁的中文回答，不超过300字。"
        )

        try:
            from tradingagents.llm_clients import create_llm_client
            from langchain_core.messages import HumanMessage

            client = create_llm_client(
                provider=llm_config.get("llm_provider", "deepseek"),
                model=llm_config.get("quick_think_llm", "deepseek-chat"),
                base_url=llm_config.get("backend_url", "https://api.deepseek.com"),
            )
            llm = client.get_llm()
            response = llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            return f"AI联动分析失败: {e}"


class AIFactorDiscovery:
    """LLM suggests new factor candidates based on market regime."""

    def suggest(
        self,
        market_context: str,
        existing_factors: list[str],
        llm_config: dict,
    ) -> str:
        """Suggest new factor ideas."""
        prompt = (
            f"当前市场环境: {market_context}\n"
            f"已有因子: {', '.join(existing_factors)}\n\n"
            "请根据当前市场环境，建议2-3个新的Alpha因子方向。\n"
            "每个因子: 名称(中英文)、计算逻辑(用价格/成交量/基本面等描述)、\n"
            "为什么在当前市场环境下有效。用简洁中文，每个因子不超过60字。"
        )

        try:
            from tradingagents.llm_clients import create_llm_client
            from langchain_core.messages import HumanMessage

            client = create_llm_client(
                provider=llm_config.get("llm_provider", "deepseek"),
                model=llm_config.get("quick_think_llm", "deepseek-chat"),
                base_url=llm_config.get("backend_url", "https://api.deepseek.com"),
            )
            llm = client.get_llm()
            response = llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            return f"AI因子发现失败: {e}"
