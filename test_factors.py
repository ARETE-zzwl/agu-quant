"""Fast in-memory factor backtest — preload all data once."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from tradingagents.factors import ALL_FACTORS
from tradingagents.dataflows.a_stock import _load_ohlcv_astock

CODES = ["600519", "000858", "300750", "002594", "600036", "601318", "000001",
         "600276", "603259", "600900", "000333", "600585"]

END = "2026-05-16"
START = "2025-01-01"

# ---- Step 1: Preload all OHLCV data ----
print("Preloading OHLCV data...")
stock_data = {}
for code in CODES:
    df = _load_ohlcv_astock(code, END)
    if not df.empty:
        df = df.set_index("Date").sort_index()
        df = df[df.index >= START]
        if len(df) > 60:
            stock_data[code] = df
print(f"  {len(stock_data)}/{len(CODES)} stocks loaded")

# ---- Step 2: Find working factors and precompute ----
print("Computing factor scores...")
working = []
for name, f in ALL_FACTORS.items():
    try:
        test_df = stock_data.get("600519", list(stock_data.values())[0])
        s = f.compute_series(test_df)
        vals = s.dropna()
        if len(vals) > 30 and vals.std() > 0.001:
            working.append((name, f.category, f.ic_value))
    except:
        pass
working.sort(key=lambda x: x[2], reverse=True)
print(f"  {len(working)} working factors")

# ---- Step 3: Run simplified backtest (in-memory) ----
REBALANCE_DATES = [d.strftime("%Y-%m-%d") for d in pd.date_range(START, END, freq="14D")]
TOP_PCT = 0.3

def backtest_factor(factor_name, factor_obj):
    """Simple equal-weight long-only backtest."""
    try:
        equity = 1.0
        eq_curve = [1.0]
        daily_rets = []

        for i, ds in enumerate(REBALANCE_DATES[:-1]):
            # Score all stocks
            scores = {}
            for code, df in stock_data.items():
                try:
                    s = factor_obj.compute_series(df)
                    if ds in s.index:
                        scores[code] = float(s.loc[ds])
                except:
                    pass

            if not scores:
                continue

            # Pick top
            sorted_stocks = sorted(scores.items(), key=lambda x: x[1],
                                  reverse=(factor_obj.direction > 0))
            n = max(1, int(len(scores) * TOP_PCT))
            top = sorted_stocks[:n]

            # Equal weight
            weight = 1.0 / n
            next_ds = REBALANCE_DATES[min(i + 1, len(REBALANCE_DATES) - 1)]

            # Calculate forward returns
            for code, _ in top:
                df = stock_data.get(code)
                if df is not None and ds in df.index and next_ds in df.index:
                    ret = df["Close"].loc[next_ds] / df["Close"].loc[ds] - 1
                    equity += weight * ret * equity

            eq_curve.append(equity)
            daily_rets.append(equity / eq_curve[-2] - 1 if len(eq_curve) >= 2 else 0)

        rets = pd.Series(daily_rets)
        total_ret = equity - 1.0
        days = len(rets)
        ann_ret = (1 + total_ret) ** (252 / max(days, 1)) - 1
        avg = rets.mean()
        std = max(rets.std(), 0.001)
        sharpe = (avg / std) * np.sqrt(252)
        eq_s = pd.Series(eq_curve)
        peak = eq_s.expanding().max()
        dd = abs((eq_s - peak) / peak.replace(0, 1)).max()
        wins = (rets > 0).sum()
        win_rate = wins / max(len(rets[rets != 0]), 1)

        return ann_ret, sharpe, dd, win_rate, total_ret
    except Exception as e:
        return None, None, None, None, None

# ---- Phase 1: Individual factors ----
print()
print("=" * 85)
print("PHASE 1: Individual Factor Performance (pure price/volume)")
print("=" * 85)
print(f"{'Factor':<28} {'Cat':<10} {'AnnRet%':>8} {'Sharpe':>7} {'MaxDD%':>7} {'Win%':>7} {'TotRet%':>8}")
print("-" * 85)

ind_results = []
for name, cat, ic in working[:25]:
    f = ALL_FACTORS[name]
    ann, sh, dd, wr, tot = backtest_factor(name, f)
    if ann is not None:
        ind_results.append({"name": name, "cat": cat, "ann": ann, "sharpe": sh,
                           "dd": dd, "win": wr, "tot": tot})
ind_results.sort(key=lambda x: x["sharpe"], reverse=True)

for r in ind_results[:20]:
    print(f"{r['name']:<28} {r['cat']:<10} {r['ann']*100:>7.1f}% {r['sharpe']:>6.2f} {-r['dd']*100:>6.1f}% {r['win']*100:>6.1f}% {r['tot']*100:>7.1f}%")

# ---- Phase 2: Best pair combos ----
print()
print("=" * 85)
print("PHASE 2: Best Pair Combinations")
print("=" * 85)

top_names = [r["name"] for r in ind_results[:6]]
pair_results = []

for i, a in enumerate(top_names):
    for j, b in enumerate(top_names):
        if j <= i:
            continue

        # Create composite factor: average of z-scores
        class ComboFactor:
            name = f"{a}+{b}"
            direction = 1
            def compute_series(self, df):
                fa = ALL_FACTORS[a].compute_series(df)
                fb = ALL_FACTORS[b].compute_series(df)
                za = (fa - fa.mean()) / fa.std().replace(0, 1)
                zb = (fb - fb.mean()) / fb.std().replace(0, 1)
                return za.fillna(0) + zb.fillna(0)

        ann, sh, dd, wr, tot = backtest_factor(f"{a}+{b}", ComboFactor())
        if ann is not None:
            pair_results.append({"name": f"{a}+{b}", "ann": ann, "sharpe": sh,
                                "dd": dd, "win": wr, "tot": tot})

pair_results.sort(key=lambda x: x["sharpe"], reverse=True)
for r in pair_results[:10]:
    print(f"{r['name']:<30} {r['ann']*100:>7.1f}% {r['sharpe']:>6.2f} {-r['dd']*100:>6.1f}% {r['win']*100:>6.1f}% {r['tot']*100:>7.1f}%")

# ---- Summary ----
print()
print("=" * 85)
print("RECOMMENDED: Top by Sharpe")
for i, r in enumerate((ind_results + pair_results)[:5]):
    s = sorted(ind_results + pair_results, key=lambda x: x["sharpe"], reverse=True)[i]
    print(f"  {i+1}. {s['name']:<35} Sharpe={s['sharpe']:.2f} Win%={s['win']*100:.1f}% AnnRet={s['ann']*100:.1f}%")

print()
print("RECOMMENDED: Top by Win Rate")
for i, r in enumerate((ind_results + pair_results)[:5]):
    s = sorted(ind_results + pair_results, key=lambda x: x["win"], reverse=True)[i]
    print(f"  {i+1}. {s['name']:<35} Win%={s['win']*100:.1f}% Sharpe={s['sharpe']:.2f} AnnRet={s['ann']*100:.1f}%")
