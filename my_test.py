"""Quick test: Use DeepSeek to analyze a Chinese A-stock."""
import os
import sys
import io

# Fix Windows GBK encoding for emoji characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# Build config for DeepSeek
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "deepseek"
config["deep_think_llm"] = "deepseek-chat"
config["quick_think_llm"] = "deepseek-chat"
config["backend_url"] = "https://api.deepseek.com"
config["max_debate_rounds"] = 1
config["max_risk_discuss_rounds"] = 1
config["output_language"] = "Chinese"
config["data_vendors"] = {
    "core_stock_apis": "a_stock",
    "technical_indicators": "a_stock",
    "fundamental_data": "a_stock",
    "news_data": "a_stock",
    "signal_data": "a_stock",
}

ticker = "600519"
trade_date = "2026-05-16"

print(f"开始分析 {ticker} ({trade_date})...")
print(f"使用模型: {config['deep_think_llm']} @ {config['llm_provider']}")
print("-" * 60)

ta = TradingAgentsGraph(debug=False, config=config)

try:
    final_state, decision = ta.propagate(ticker, trade_date)
    print("\n" + "=" * 60)
    print("最终决策:")
    print(decision)
    print("=" * 60)
except Exception as e:
    print(f"\n运行出错: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
