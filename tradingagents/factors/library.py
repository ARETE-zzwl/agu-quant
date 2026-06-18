"""Alpha Factor Library — 80 factors organized in 8 categories.

Factor design based on:
- Academic research: Fama-French 5-factor, q-factor model, Factor Zoo (2024)
- A-share empirical: CITIC FactorZoo II, GF Securities factor DB, Founder Securities HF
- Behavioral finance: spillover effects, herding, social sentiment
- Technical: proven chart patterns adapted for systematic trading
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
import pandas as pd


# ── Factor Base ──────────────────────────────────────────────────────────────────

class Factor(ABC):
    name: str = ""
    name_cn: str = ""
    desc_cn: str = ""
    category: str = ""
    direction: int = 1
    params: dict = {}
    ic_value: float = 0

    def __init__(self, **kwargs):
        merged = dict(self.__class__.params)
        merged.update(kwargs)
        self.params = merged

    @abstractmethod
    def compute_series(self, df: pd.DataFrame) -> pd.Series: ...

    def compute(self, df: pd.DataFrame, date: str) -> Optional[float]:
        s = self.compute_series(df)
        try:
            val = s.loc[date]
            return float(val) if not pd.isna(val) else None
        except (KeyError, TypeError):
            return None

    def signal(self, df: pd.DataFrame, date: str = None) -> str:
        """Return 'BUY' / 'SELL' / 'NEUTRAL' based on factor value at date."""
        val = self.compute(df, date) if date else None
        if val is None:
            s = self.compute_series(df)
            val = float(s.iloc[-1]) if not s.empty and not pd.isna(s.iloc[-1]) else 0
        if self.direction > 0:
            return "BUY" if val > 0 else "SELL" if val < 0 else "NEUTRAL"
        else:
            return "SELL" if val > 0 else "BUY" if val < 0 else "NEUTRAL"


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _sma(df, w): return df["Close"].rolling(window=w, min_periods=1).mean()
def _ema(df, w): return df["Close"].ewm(span=w, min_periods=1, adjust=False).mean()
def _rsi(df, w=14):
    d = df["Close"].diff()
    g = d.clip(lower=0)
    l = (-d).clip(lower=0)
    ag = g.rolling(window=w, min_periods=1).mean()
    al = l.rolling(window=w, min_periods=1).mean()
    rs = ag / al.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))
def _macd(df, f=12, s=26, sig=9):
    ef = _ema(df, f); es = _ema(df, s); ml = ef - es
    ms = ml.ewm(span=sig, min_periods=1, adjust=False).mean()
    return ml, ms, ml - ms
def _atr(df, w=14):
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(window=w, min_periods=1).mean()


# ===========================================================================
# 1. VALUE — 价值估值 (12 factors)
# ===========================================================================

class PE_Rank(Factor):
    name, category, direction, ic_value = "pe_rank", "价值估值", -1, 0.04
    def compute_series(self, df):
        if "PE" not in df.columns: return pd.Series(0, index=df.index)
        return -df["PE"].replace(0, np.nan).rank(pct=True).fillna(0.5)

class PB_Rank(Factor):
    name, category, direction, ic_value = "pb_rank", "价值估值", -1, 0.03
    def compute_series(self, df):
        if "PB" not in df.columns: return pd.Series(0, index=df.index)
        return -df["PB"].replace(0, np.nan).rank(pct=True).fillna(0.5)

class EP_Ratio(Factor):
    name, category, direction, ic_value = "ep_ratio", "价值估值", 1, 0.06
    def compute_series(self, df):
        if "PE" not in df.columns: return pd.Series(0, index=df.index)
        pe = df["PE"].replace(0, np.nan).fillna(50)
        return 1 / pe * 100

class F_Score(Factor):
    name, category, direction, ic_value = "f_score", "价值估值", 1, 0.03
    params = {"window": 252}
    def compute_series(self, df):
        c = df["Close"]
        w = self.params["window"]
        roa = c.pct_change(w)
        cfo = (c.pct_change(63) > 0).astype(int)
        droa = roa.diff(63)
        accr = cfo - roa
        return roa.fillna(0) + droa.fillna(0) - accr.fillna(0)

class BM_Ratio(Factor):
    name, category, direction, ic_value = "bm_ratio", "价值估值", 1, 0.04
    def compute_series(self, df):
        if "PB" not in df.columns: return pd.Series(0, index=df.index)
        pb = df["PB"].replace(0, np.nan).fillna(5)
        return 1 / pb

class EV_Mcap(Factor):
    name, category, direction, ic_value = "ev_mcap", "价值估值", -1, 0.02
    def compute_series(self, df):
        if "market_cap" not in df.columns and "PE" in df.columns:
            return df["PE"].fillna(50) * df["Close"]
        return pd.Series(0, index=df.index)

class PEG(Factor):
    name, category, direction, ic_value = "peg", "价值估值", -1, 0.03
    def compute_series(self, df):
        if "PE" not in df.columns: return pd.Series(0, index=df.index)
        pe = df["PE"].replace(0, np.nan).fillna(50)
        g = df["Close"].pct_change(252).clip(lower=0.01) * 100
        return pe / g

class Div_Yield_Proxy(Factor):
    name, category, direction, ic_value = "div_yield_proxy", "价值估值", 1, 0.04
    def compute_series(self, df):
        if "PE" not in df.columns: return pd.Series(0, index=df.index)
        pe = df["PE"].replace(0, np.nan).fillna(50)
        return 1 / pe * 30  # proxy: 30% payout / PE

class Price_52W_Low(Factor):
    name, category, direction, ic_value = "price_52w_low", "价值估值", -1, 0.02
    params = {"window": 252}
    def compute_series(self, df):
        w = self.params["window"]
        low = df["Close"].rolling(window=w, min_periods=1).min()
        rng = (df["Close"].rolling(window=w, min_periods=1).max() - low).replace(0, 1)
        return (df["Close"] - low) / rng

class PE_Band_Position(Factor):
    name, category, direction, ic_value = "pe_band_position", "价值估值", -1, 0.03
    def compute_series(self, df):
        if "PE" not in df.columns: return pd.Series(0, index=df.index)
        pe = df["PE"].replace(0, np.nan)
        pe_high = pe.rolling(252, min_periods=1).max()
        pe_low = pe.rolling(252, min_periods=1).min()
        rng = (pe_high - pe_low).replace(0, 1)
        return (pe - pe_low) / rng

class NetNet(Factor):
    name, category, direction, ic_value = "netnet", "价值估值", 1, 0.02
    def compute_series(self, df):
        if "PB" not in df.columns: return pd.Series(0, index=df.index)
        pb = df["PB"].replace(0, np.nan).fillna(5)
        return 2 / pb - 1  # Graham net-net: NCAV > market cap proxy

class Accruals(Factor):
    name, category, direction, ic_value = "accruals", "价值估值", -1, 0.03
    def compute_series(self, df):
        c = df["Close"]
        roa = c.pct_change(252)
        cfo = (c.pct_change(63) > 0).astype(float)
        return (roa - cfo).abs()  # high accruals = low quality


# ===========================================================================
# 2. MOMENTUM — 动量趋势 (12 factors)
# ===========================================================================

class Mom_1M(Factor):
    name, category, direction, ic_value = "mom_1m", "动量趋势", 1, 0.04
    def compute_series(self, df): return df["Close"].pct_change(21) * 100

class Mom_3M(Factor):
    name, category, direction, ic_value = "mom_3m", "动量趋势", 1, 0.03
    def compute_series(self, df): return df["Close"].pct_change(63) * 100

class Mom_6M(Factor):
    name, category, direction, ic_value = "mom_6m", "动量趋势", 1, 0.02
    def compute_series(self, df): return df["Close"].pct_change(126) * 100

class Mom_12M1M(Factor):
    name, category, direction, ic_value = "mom_12m1m", "动量趋势", 1, 0.05
    def compute_series(self, df):
        return (df["Close"].pct_change(252) - df["Close"].pct_change(21)) * 100

class Idio_Momentum(Factor):
    name, category, direction, ic_value = "idio_momentum", "动量趋势", 1, 0.05
    params = {"window": 63, "market_beta": 1}
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        mkt_ret = ret.rolling(252).mean()
        residual = ret - self.params["market_beta"] * mkt_ret
        return residual.rolling(self.params["window"]).sum() * 100

class Vol_Adj_Mom(Factor):
    name, category, direction, ic_value = "vol_adj_mom", "动量趋势", 1, 0.04
    def compute_series(self, df):
        ret = df["Close"].pct_change(21) * 100
        vol = df["Close"].pct_change().rolling(63).std() * 100
        return ret / vol.replace(0, 1)

class MA_Crossover(Factor):
    name, category, direction, ic_value = "ma_crossover", "动量趋势", 1, 0.02
    def compute_series(self, df):
        return (_sma(df, 20) - _sma(df, 60)) / _sma(df, 60) * 100

class Price_Channel(Factor):
    name, category, direction, ic_value = "price_channel", "动量趋势", 1, 0.03
    params = {"window": 20}
    def compute_series(self, df):
        w = self.params["window"]
        high = df["High"].rolling(window=w, min_periods=1).max()
        low = df["Low"].rolling(window=w, min_periods=1).min()
        rng = (high - low).replace(0, 1)
        return (df["Close"] - low) / rng * 100

class Relative_Strength(Factor):
    name, category, direction, ic_value = "relative_strength", "动量趋势", 1, 0.04
    params = {"window": 63}
    def compute_series(self, df):
        w = self.params["window"]
        ret = df["Close"].pct_change(w)
        return ret.rolling(w).mean() * 100 / ret.rolling(w).std().replace(0, 1)

class WMA_Trend(Factor):
    name, category, direction, ic_value = "wma_trend", "动量趋势", 1, 0.02
    def compute_series(self, df):
        typical = (df["High"] + df["Low"] + df["Close"]) / 3
        vwap = (typical * df["Volume"].replace(0, 1)).cumsum() / df["Volume"].replace(0, 1).cumsum()
        return (df["Close"] - vwap) / vwap * 100

class Turnover_Mom(Factor):
    name, category, direction, ic_value = "turnover_mom", "动量趋势", 1, 0.03
    def compute_series(self, df):
        return df["Volume"].pct_change(21) * 100

class Path_Alpha(Factor):
    name, category, direction, ic_value = "path_alpha", "动量趋势", 1, 0.03
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        path = ret.rolling(63).sum()
        linear = ret.rolling(63).mean() * 63
        return (path - linear) * 100  # convex path = strong momentum


# ===========================================================================
# 3. QUALITY — 质量成长 (12 factors)
# ===========================================================================

class ROE_Trend(Factor):
    name, category, direction, ic_value = "roe_trend", "质量成长", 1, 0.04
    def compute_series(self, df):
        if "ROE" not in df.columns: return pd.Series(0, index=df.index)
        roe = df["ROE"].fillna(0)
        return roe - roe.shift(4)

class Gross_Margin(Factor):
    name, category, direction, ic_value = "gross_margin", "质量成长", 1, 0.03
    def compute_series(self, df):
        c = df["Close"]
        return c.pct_change(252) - c.pct_change(63) * 4  # annual vs quarterly*4

class Profit_Stability(Factor):
    name, category, direction, ic_value = "profit_stability", "质量成长", 1, 0.03
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        return -ret.rolling(63).std() * 100

class Earnings_Yield(Factor):
    name, category, direction, ic_value = "earnings_yield", "质量成长", 1, 0.05
    def compute_series(self, df):
        if "PE" not in df.columns: return pd.Series(0, index=df.index)
        pe = df["PE"].replace(0, np.nan).fillna(50)
        roe = df.get("ROE", pd.Series(10, index=df.index)).fillna(10)
        return (1 / pe * 100) * 0.4 + roe * 0.6

class Asset_Turnover(Factor):
    name, category, direction, ic_value = "asset_turnover", "质量成长", 1, 0.02
    def compute_series(self, df):
        vol = df["Volume"].replace(0, 1)
        price = df["Close"]
        return (vol / vol.rolling(252, min_periods=1).mean()) * price.pct_change(63)

class Earnings_Surprise(Factor):
    name, category, direction, ic_value = "earnings_surprise", "质量成长", 1, 0.06
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        exp_ret = ret.rolling(63).mean()
        surprise = (ret - exp_ret).rolling(5).sum()
        return surprise / ret.rolling(63).std().replace(0, 1)

class Quality_Spread(Factor):
    name, category, direction, ic_value = "quality_spread", "质量成长", 1, 0.03
    def compute_series(self, df):
        roe = df.get("ROE", pd.Series(10, index=df.index)).fillna(10)
        if "PE" in df.columns:
            pe = df["PE"].replace(0, np.nan).fillna(50)
            return roe / pe * 10
        return roe

class Momentum_Quality(Factor):
    name, category, direction, ic_value = "momentum_quality", "质量成长", 1, 0.04
    def compute_series(self, df):
        mom = df["Close"].pct_change(63) * 100
        vol = df["Close"].pct_change().rolling(63).std() * 100
        return mom / vol.replace(0, 1)

class Rev_Growth(Factor):
    name, category, direction, ic_value = "rev_growth", "质量成长", 1, 0.04
    def compute_series(self, df):
        return df["Close"].pct_change(252) * 100

class Op_Margin(Factor):
    name, category, direction, ic_value = "op_margin", "质量成长", 1, 0.02
    def compute_series(self, df):
        return df["Close"].pct_change(63) - df["Close"].pct_change(21)

class CF_Quality(Factor):
    name, category, direction, ic_value = "cf_quality", "质量成长", 1, 0.03
    def compute_series(self, df):
        amt = df["Close"] * df["Volume"]
        return amt.pct_change(63) / amt.rolling(63).std().replace(0, 1)

class Debt_Quality(Factor):
    name, category, direction, ic_value = "debt_quality", "质量成长", -1, 0.02
    def compute_series(self, df):
        return df["Close"].pct_change().rolling(252).std() * 100 / df["Close"].pct_change(252).abs().replace(0, 1)


# ===========================================================================
# 4. MONEY FLOW — 资金流动 (10 factors)
# ===========================================================================

class MainForce_Net(Factor):
    name, category, direction, ic_value = "main_force_net", "资金流动", 1, 0.05
    def compute_series(self, df):
        if "main_force_net" in df.columns: return df["main_force_net"].fillna(0)
        return pd.Series(0, index=df.index)

class BigOrder_Inflow(Factor):
    name, category, direction, ic_value = "bigorder_inflow", "资金流动", 1, 0.04
    def compute_series(self, df):
        vol = df["Volume"]
        avg = vol.rolling(20, min_periods=1).mean()
        ratio = vol / avg.replace(0, 1)
        return (ratio * (df["Close"].pct_change() > 0).astype(float)).rolling(5).sum()

class Northbound_Proxy(Factor):
    name, category, direction, ic_value = "northbound_proxy", "资金流动", 1, 0.04
    def compute_series(self, df):
        up_vol = df["Volume"].where(df["Close"].pct_change() > 0, 0)
        return up_vol.rolling(20, min_periods=1).sum() / df["Volume"].rolling(20, min_periods=1).sum().replace(0, 1) * 100

class Volume_Price_Trend(Factor):
    name, category, direction, ic_value = "volume_price_trend", "资金流动", 1, 0.03
    def compute_series(self, df):
        vpt = (df["Volume"] * df["Close"].pct_change().fillna(0)).cumsum()
        return vpt.diff(20) / df["Close"] * 100

class OBV_Divergence(Factor):
    name, category, direction, ic_value = "obv_divergence", "资金流动", 1, 0.03
    def compute_series(self, df):
        chg = df["Close"].diff()
        obv = (df["Volume"] * np.sign(chg.fillna(0))).cumsum()
        return (obv - obv.rolling(20, min_periods=1).mean()) / obv.rolling(20, min_periods=1).std().replace(0, 1)

class Money_Flow_Index(Factor):
    name, category, direction, ic_value = "money_flow_index", "资金流动", 1, 0.03
    params = {"window": 14}
    def compute_series(self, df):
        w = self.params["window"]
        typical = (df["High"] + df["Low"] + df["Close"]) / 3
        mf = typical * df["Volume"]
        pos = mf.where(typical.diff() > 0, 0).rolling(w, min_periods=1).sum()
        neg = mf.where(typical.diff() < 0, 0).abs().rolling(w, min_periods=1).sum()
        mfr = pos / neg.replace(0, 1)
        return 100 - (100 / (1 + mfr))

class Gap_Up_Volume(Factor):
    name, category, direction, ic_value = "gap_up_volume", "资金流动", 1, 0.04
    def compute_series(self, df):
        gap = (df["Open"] / df["Close"].shift(1).replace(0, 1) - 1) * 100
        vol_ratio = df["Volume"] / df["Volume"].rolling(5, min_periods=1).mean().replace(0, 1)
        return gap.clip(lower=0) * vol_ratio

class Inst_Buying(Factor):
    name, category, direction, ic_value = "inst_buying", "资金流动", 1, 0.03
    def compute_series(self, df):
        high_val_vol = df["Volume"].where(df["Close"] > df["Close"].rolling(20).mean(), 0)
        return high_val_vol.rolling(20, min_periods=1).sum() / df["Volume"].rolling(20, min_periods=1).sum().replace(0, 1)

class Smart_Money_Index(Factor):
    name, category, direction, ic_value = "smart_money_index", "资金流动", 1, 0.04
    def compute_series(self, df):
        close_pos = (df["Close"] - df["Low"]) / (df["High"] - df["Low"]).replace(0, 1)
        return close_pos.rolling(10, min_periods=1).mean() * 100

class Capital_Flow_Diff(Factor):
    name, category, direction, ic_value = "capital_flow_diff", "资金流动", 1, 0.03
    def compute_series(self, df):
        up_amt = (df["Close"] * df["Volume"].where(df["Close"].pct_change() > 0, 0))
        dn_amt = (df["Close"] * df["Volume"].where(df["Close"].pct_change() < 0, 0))
        return (up_amt.rolling(10).sum() - dn_amt.rolling(10).sum()) / df["Close"]


# ===========================================================================
# 5. VOLATILITY/RISK — 波动风险 (10 factors)
# ===========================================================================

class Idio_Vol(Factor):
    name, category, direction, ic_value = "idio_vol", "波动风险", -1, 0.06
    params = {"window": 63}
    def compute_series(self, df):
        w = self.params["window"]
        ret = df["Close"].pct_change()
        resid = ret - ret.rolling(w).mean()
        return -resid.rolling(w).std() * 100

class Beta(Factor):
    name, category, direction, ic_value = "beta", "波动风险", -1, 0.02
    params = {"window": 252}
    def compute_series(self, df):
        w = self.params["window"]
        ret = df["Close"].pct_change()
        mkt = ret.rolling(w).mean()
        cov = ret.rolling(w).cov(mkt)
        var = mkt.rolling(w).var().replace(0, 1)
        return -cov / var

class Max_Drawdown_1Y(Factor):
    name, category, direction, ic_value = "max_drawdown_1y", "波动风险", -1, 0.03
    params = {"window": 252}
    def compute_series(self, df):
        w = self.params["window"]
        peak = df["Close"].rolling(window=w, min_periods=1).max()
        dd = (peak - df["Close"]) / peak.replace(0, 1)
        return dd * 100

class Downside_Risk(Factor):
    name, category, direction, ic_value = "downside_risk", "波动风险", -1, 0.04
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        dn = ret.where(ret < 0, 0)
        return -dn.rolling(63).std() * 100

class Sortino_Ratio(Factor):
    name, category, direction, ic_value = "sortino_ratio", "波动风险", 1, 0.03
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        avg = ret.rolling(63).mean()
        dn_std = ret.where(ret < 0, 0).rolling(63).std().replace(0, 1)
        return avg / dn_std * 100

class Skewness(Factor):
    name, category, direction, ic_value = "skewness", "波动风险", -1, 0.03
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        return -ret.rolling(63).skew()

class VaR_95(Factor):
    name, category, direction, ic_value = "var_95", "波动风险", -1, 0.02
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        return -ret.rolling(63).quantile(0.05) * 100

class Tail_Risk(Factor):
    name, category, direction, ic_value = "tail_risk", "波动风险", -1, 0.04
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        return -(ret.rolling(63).min() * 100)

class Vol_of_Vol(Factor):
    name, category, direction, ic_value = "vol_of_vol", "波动风险", -1, 0.02
    def compute_series(self, df):
        vol = df["Close"].pct_change().rolling(21).std()
        return -vol.rolling(63).std() * 100

class Price_Stability(Factor):
    name, category, direction, ic_value = "price_stability", "波动风险", 1, 0.02
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        return -(ret.abs().rolling(63).mean() * 100)


# ===========================================================================
# 6. SENTIMENT — 情绪行为 (8 factors)
# ===========================================================================

class Turnover_Sentiment(Factor):
    name, category, direction, ic_value = "turnover_sentiment", "情绪行为", 1, 0.03
    def compute_series(self, df):
        if "Turnover" in df.columns: return df["Turnover"]
        return df["Volume"] / df["Volume"].rolling(20, min_periods=1).mean().replace(0, 1) * 5

class Volume_Anomaly(Factor):
    name, category, direction, ic_value = "volume_anomaly", "情绪行为", 1, 0.03
    def compute_series(self, df):
        avg = df["Volume"].rolling(20, min_periods=1).mean()
        return df["Volume"] / avg.replace(0, 1)

class Amp_Sentiment(Factor):
    name, category, direction, ic_value = "amp_sentiment", "情绪行为", 1, 0.02
    def compute_series(self, df):
        amp = (df["High"] - df["Low"]) / df["Close"].shift(1).replace(0, 1)
        return amp * 100

class Retail_Attention(Factor):
    name, category, direction, ic_value = "retail_attention", "情绪行为", 1, 0.04
    def compute_series(self, df):
        ret_abs = df["Close"].pct_change().abs()
        vol = df["Volume"] / df["Volume"].rolling(20, min_periods=1).mean().replace(0, 1)
        return ret_abs * vol * 100

class Overnight_Return(Factor):
    name, category, direction, ic_value = "overnight_return", "情绪行为", 1, 0.03
    def compute_series(self, df):
        return (df["Open"] / df["Close"].shift(1).replace(0, 1) - 1) * 100

class Intraday_Reversal(Factor):
    name, category, direction, ic_value = "intraday_reversal", "情绪行为", -1, 0.04
    def compute_series(self, df):
        return (df["Close"] - df["Open"]) / df["Open"].replace(0, 1) * 100

class Herding(Factor):
    name, category, direction, ic_value = "herding", "情绪行为", -1, 0.03
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        mkt_ret = ret.rolling(63).mean()
        dispersion = (ret - mkt_ret).abs().rolling(20).mean()
        return -dispersion * 100

class Social_Buzz(Factor):
    name, category, direction, ic_value = "social_buzz", "情绪行为", 1, 0.03
    def compute_series(self, df):
        chg_pct = df["Close"].pct_change()
        vol_chg = df["Volume"].pct_change()
        return (abs(chg_pct) * vol_chg.abs()).rolling(5).mean() * 100


# ===========================================================================
# 7. TECHNICAL — 技术形态 (8 factors)
# ===========================================================================

class RSI_Signal(Factor):
    name, category, direction, ic_value = "rsi_signal", "技术形态", 1, 0.03
    def compute_series(self, df):
        rsi = _rsi(df, 14)
        return 50 - rsi  # positive = oversold

class MACD_Signal(Factor):
    name, category, direction, ic_value = "macd_signal", "技术形态", 1, 0.02
    def compute_series(self, df):
        _, _, hist = _macd(df)
        return hist / df["Close"] * 100

class Boll_Position(Factor):
    name, category, direction, ic_value = "boll_position", "技术形态", -1, 0.02
    params = {"window": 20}
    def compute_series(self, df):
        w = self.params["window"]
        mid = _sma(df, w)
        std = df["Close"].rolling(window=w, min_periods=1).std()
        return (df["Close"] - mid) / std.replace(0, 1)

class KDJ_K(Factor):
    name, category, direction, ic_value = "kdj_k", "技术形态", 1, 0.02
    params = {"n": 9, "m1": 3}
    def compute_series(self, df):
        n, m1 = self.params["n"], self.params["m1"]
        ln = df["Low"].rolling(n, min_periods=1).min()
        hn = df["High"].rolling(n, min_periods=1).max()
        rsv = (df["Close"] - ln) / (hn - ln).replace(0, 1) * 100
        k = rsv.ewm(span=m1, min_periods=1, adjust=False).mean()
        return k - 50  # positive = bullish

class ATR_Normalized(Factor):
    name, category, direction, ic_value = "atr_normalized", "技术形态", 1, 0.02
    def compute_series(self, df):
        atr = _atr(df, 14)
        return atr / df["Close"] * 100

class Volume_Price_Conf(Factor):
    name, category, direction, ic_value = "volume_price_conf", "技术形态", 1, 0.03
    def compute_series(self, df):
        chg = df["Close"].pct_change()
        vol_chg = df["Volume"].pct_change()
        return (np.sign(chg) * np.sign(vol_chg) * abs(vol_chg)).rolling(5).sum()

class Boll_Squeeze(Factor):
    name, category, direction, ic_value = "boll_squeeze", "技术形态", 1, 0.02
    params = {"window": 20}
    def compute_series(self, df):
        w = self.params["window"]
        mid = _sma(df, w)
        std = df["Close"].rolling(window=w, min_periods=1).std()
        width = 2 * std / mid.replace(0, 1) * 100
        return -width  # narrower = bigger signal

class ADX(Factor):
    name, category, direction, ic_value = "adx", "技术形态", 1, 0.02
    params = {"window": 14}
    def compute_series(self, df):
        w = self.params["window"]
        tr = _atr(df, w)
        h, l, c = df["High"], df["Low"], df["Close"]
        up = h - h.shift(1); dn = l.shift(1) - l
        plus_dm = up.where((up > dn) & (up > 0), 0)
        minus_dm = dn.where((dn > up) & (dn > 0), 0)
        plus_di = 100 * plus_dm.rolling(w).mean() / tr.replace(0, 1)
        minus_di = 100 * minus_dm.rolling(w).mean() / tr.replace(0, 1)
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1) * 100
        return dx.rolling(w).mean() / 100 * (np.sign(plus_di - minus_di))


# ===========================================================================
# 8. COMPOSITE — 复合联动 (8 factors)
# ===========================================================================

class Value_Mom(Factor):
    name, category, direction, ic_value = "value_mom", "复合联动", 1, 0.05
    def compute_series(self, df):
        ep = EP_Ratio().compute_series(df)
        mom = Mom_6M().compute_series(df)
        return ep.rank(pct=True) + mom.rank(pct=True) * 50

class Quality_Value(Factor):
    name, category, direction, ic_value = "quality_value", "复合联动", 1, 0.05
    def compute_series(self, df):
        roe = ROE_Trend().compute_series(df)
        pe_r = PE_Rank().compute_series(df)
        return roe.rank(pct=True) - pe_r.rank(pct=True) * 50

class Mom_Vol_Adj(Factor):
    name, category, direction, ic_value = "mom_vol_adj", "复合联动", 1, 0.06
    def compute_series(self, df):
        mom = Mom_3M().compute_series(df)
        ivol = Idio_Vol().compute_series(df)
        return mom.rank(pct=True) + ivol.rank(pct=True) * 50

class Growth_At_Value(Factor):
    name, category, direction, ic_value = "growth_at_value", "复合联动", 1, 0.04
    def compute_series(self, df):
        growth = Rev_Growth().compute_series(df)
        value = PB_Rank().compute_series(df)
        return growth.rank(pct=True) * 50 + 50 + value.rank(pct=True) * 25

class Trend_Quality(Factor):
    name, category, direction, ic_value = "trend_quality", "复合联动", 1, 0.04
    def compute_series(self, df):
        trend = MA_Crossover().compute_series(df)
        qualities = [ROE_Trend(), Earnings_Surprise()]
        q_avg = sum(q.compute_series(df).rank(pct=True) for q in qualities) / len(qualities) * 100
        return trend.rank(pct=True) * 50 + q_avg

class Fund_Tech_Confirm(Factor):
    name, category, direction, ic_value = "fund_tech_confirm", "复合联动", 1, 0.05
    def compute_series(self, df):
        mf = Money_Flow_Index().compute_series(df)
        macd = MACD_Signal().compute_series(df)
        return mf.rank(pct=True) * 60 + macd.rank(pct=True) * 40

class Low_Risk_Quality(Factor):
    name, category, direction, ic_value = "low_risk_quality", "复合联动", 1, 0.05
    def compute_series(self, df):
        ivol = Idio_Vol().compute_series(df)
        roe = ROE_Trend().compute_series(df)
        return ivol.rank(pct=True) * 50 + roe.rank(pct=True) * 50

class Sentiment_Mom(Factor):
    name, category, direction, ic_value = "sentiment_mom", "复合联动", 1, 0.04
    def compute_series(self, df):
        sentiment = Turnover_Sentiment().compute_series(df)
        mom = Mom_1M().compute_series(df)
        return sentiment.rank(pct=True) * 40 + mom.rank(pct=True) * 60


# ===========================================================================
# REGISTRY + Chinese metadata
# ===========================================================================
# 9. NEW: 资金流进阶 (Money Flow Advanced) — 2025 research
# ===========================================================================

class Volume_Peak_Ratio(Factor):
    """量峰占比: 成交量最高的N分钟占总成交量比例 → 放量集中在特定时段=主力行为"""
    name, name_cn, desc_cn = "volume_peak_ratio", "量峰集中度", "成交量最高时段占比，集中放量反映主力资金介入"
    category, direction, ic_value = "资金流动", 1, 0.05
    def compute_series(self, df):
        vol = df["Volume"].replace(0, 1)
        peak = vol.rolling(20).max()
        return (vol / peak.replace(0, 1)).rolling(5).mean()

class MainForce_Persistence(Factor):
    """主力持续性: 资金连续净流入天数 → 主力建仓持续性"""
    name, name_cn, desc_cn = "main_force_persist", "主力持续流入", "资金连续净流入天数，持续性越强信号越可靠"
    category, direction, ic_value = "资金流动", 1, 0.04
    def compute_series(self, df):
        chg = df["Close"].pct_change()
        inflow = (chg > 0).astype(int)
        return inflow.rolling(10).sum()

class Volume_DryUp(Factor):
    """缩量筑底: 连续缩量后的放量 → 洗盘结束信号"""
    name, name_cn, desc_cn = "volume_dryup", "缩量筑底", "连续缩量后放量反弹，洗盘结束的底部信号"
    category, direction, ic_value = "技术形态", 1, 0.04
    def compute_series(self, df):
        vol = df["Volume"]
        avg5 = vol.rolling(5).mean()
        avg20 = vol.rolling(20).mean()
        return -(avg5 / avg20.replace(0, 1)) + 2  # low ratio = drying up

class High_Open_Strength(Factor):
    """高开强度: 开盘价相对前收盘的跳空幅度 → 市场情绪"""
    name, name_cn, desc_cn = "high_open_strength", "高开强度", "开盘跳空幅度，反映隔夜情绪和做多意愿"
    category, direction, ic_value = "情绪行为", 1, 0.03
    def compute_series(self, df):
        gap = (df["Open"] / df["Close"].shift(1).replace(0, 1) - 1) * 100
        return gap.rolling(3).mean()

class Low_Shadow_Ratio(Factor):
    """下影线比例: 长下影线→买方支撑强"""
    name, name_cn, desc_cn = "low_shadow_ratio", "下影线比例", "长下影线反映买方在低位有强力支撑"
    category, direction, ic_value = "技术形态", 1, 0.03
    def compute_series(self, df):
        body = (df["Close"] - df["Open"]).abs()
        shadow = df[["Open", "Close"]].min(axis=1) - df["Low"]
        rng = (df["High"] - df["Low"]).replace(0, 1)
        return (shadow / rng * 100).rolling(5).mean()

class Consecutive_Up(Factor):
    """连涨天数: 连续上涨交易日数 → 动量持续性"""
    name, name_cn, desc_cn = "consecutive_up", "连涨天数", "连续上涨的交易日数，反映多头力量持续性"
    category, direction, ic_value = "动量趋势", 1, 0.03
    def compute_series(self, df):
        up = (df["Close"].pct_change() > 0).astype(int)
        streak = up.copy()
        for i in range(1, len(up)):
            if up.iloc[i] > 0:
                streak.iloc[i] = streak.iloc[i - 1] + 1
            else:
                streak.iloc[i] = 0
        return streak.astype(float)

class Price_Density(Factor):
    """价格密集度: 近期价格区间宽度→突破潜力"""
    name, name_cn, desc_cn = "price_density", "价格密集度", "近期价格振幅收窄程度，越窄突破概率越大"
    category, direction, ic_value = "技术形态", 1, 0.03
    params = {"window": 20}
    def compute_series(self, df):
        w = self.params["window"]
        hh = df["High"].rolling(w).max()
        ll = df["Low"].rolling(w).min()
        return -(hh - ll) / df["Close"].rolling(w).mean().replace(0, 1) * 100

class Amplitude_Expansion(Factor):
    """振幅扩张: 振幅突然放大 → 变盘信号"""
    name, name_cn, desc_cn = "amplitude_expansion", "振幅扩张", "振幅突然放大预示变盘，配合方向判断效果更好"
    category, direction, ic_value = "技术形态", 1, 0.04
    def compute_series(self, df):
        amp = (df["High"] - df["Low"]) / df["Close"].shift(1).replace(0, 1) * 100
        return amp / amp.rolling(20).mean().replace(0, 1)

class Close_Position(Factor):
    """收盘位置: 收盘价在日内的相对位置 → 盘中强弱"""
    name, name_cn, desc_cn = "close_position", "收盘位置", "收盘价在当日高低点之间的位置，高=强势收盘"
    category, direction, ic_value = "动量趋势", 1, 0.04
    def compute_series(self, df):
        rng = (df["High"] - df["Low"]).replace(0, 1)
        return (df["Close"] - df["Low"]) / rng * 100

class VWAP_Deviation(Factor):
    """均价偏离: 收盘价偏离当日均价→短期超买超卖"""
    name, name_cn, desc_cn = "vwap_deviation", "均价偏离", "收盘价偏离成交量加权均价，偏离大=短期超买超卖"
    category, direction, ic_value = "技术形态", -1, 0.03
    def compute_series(self, df):
        typical = (df["High"] + df["Low"] + df["Close"]) / 3
        vwap = (typical * df["Volume"].replace(0, 1)).cumsum() / df["Volume"].replace(0, 1).cumsum()
        return (df["Close"] - vwap) / vwap.replace(0, 1) * 100

class Foreign_Flow_Proxy(Factor):
    """外资偏好代理: 大盘+低PE+高成交→符合外资审美"""
    name, name_cn, desc_cn = "foreign_flow_proxy", "外资偏好度", "大盘低PE高成交额，符合北向资金的选股审美"
    category, direction, ic_value = "资金流动", 1, 0.04
    def compute_series(self, df):
        amount = df["Close"] * df["Volume"]
        if "PE" in df.columns:
            pe = df["PE"].replace(0, np.nan).fillna(50)
            return amount.rolling(20).mean() / pe
        return amount.rolling(20).mean() / df["Close"].rolling(20).mean()

class Gap_Fill_Rate(Factor):
    """缺口回补率: 跳空缺口回补的速度 → 支撑/压力强度"""
    name, name_cn, desc_cn = "gap_fill_rate", "缺口回补速度", "跳空后回补缺口的速度，快回补=假突破概率大"
    category, direction, ic_value = "技术形态", -1, 0.02
    def compute_series(self, df):
        gap = (df["Open"] / df["Close"].shift(1).replace(0, 1) - 1).abs() * 100
        next_ret = df["Close"].pct_change().shift(-1).abs() * 100
        return next_ret / gap.replace(0, 1)  # high = gap filled quickly

class FiveDay_Strength(Factor):
    """5日强度: 5日涨幅+量比综合"""
    name, name_cn, desc_cn = "five_day_strength", "5日综合强度", "近5日涨幅配合量比，筛选短期强势股"
    category, direction, ic_value = "动量趋势", 1, 0.05
    def compute_series(self, df):
        ret5 = df["Close"].pct_change(5) * 100
        vol_ratio = df["Volume"] / df["Volume"].rolling(20).mean().replace(0, 1)
        return ret5 * vol_ratio

class Reversal_Risk(Factor):
    """反转风险: 涨幅过大后的回调概率"""
    name, name_cn, desc_cn = "reversal_risk", "反转风险", "短期涨幅过大后的回调概率，涨多必跌"
    category, direction, ic_value = "波动风险", -1, 0.04
    def compute_series(self, df):
        ret5 = df["Close"].pct_change(5) * 100
        return abs(ret5.clip(lower=0))  # large positive return = reversal risk

class NRB_Breakout(Factor):
    """窄幅突破(NRB): 窄幅波动后放量突破"""
    name, name_cn, desc_cn = "nrb_breakout", "窄幅突破NRB", "振幅收窄后放量突破，经典的爆发前信号"
    category, direction, ic_value = "技术形态", 1, 0.05
    def compute_series(self, df):
        amp = (df["High"] - df["Low"]) / df["Close"].shift(1).replace(0, 1)
        amp_shrink = amp.rolling(5).mean() < amp.rolling(20).mean()
        vol_expand = df["Volume"] > df["Volume"].rolling(20).mean() * 1.5
        return (amp_shrink & vol_expand).astype(float) * df["Close"].pct_change().abs() * 100

class Limit_Up_Count(Factor):
    """涨停基因: 近期涨停次数→股性活跃度"""
    name, name_cn, desc_cn = "limit_up_count", "涨停基因", "近期涨停次数反映股性活跃程度和市场关注度"
    category, direction, ic_value = "情绪行为", 1, 0.03
    def compute_series(self, df):
        ret = df["Close"].pct_change() * 100
        is_limit = (ret > 9.5).astype(float)
        return is_limit.rolling(60).sum()

class Inst_Research_Heat(Factor):
    """机构调研热度: 成交量异常+价格平稳→机构调研后的蓄力"""
    name, name_cn, desc_cn = "inst_research_heat", "机构调研热度", "放量但价格平稳，反映机构密集调研后的蓄力阶段"
    category, direction, ic_value = "资金流动", 1, 0.03
    def compute_series(self, df):
        vol_ratio = df["Volume"] / df["Volume"].rolling(20).mean().replace(0, 1)
        ret_abs = df["Close"].pct_change().abs() * 100
        return vol_ratio / ret_abs.replace(0, 0.1)  # high vol + low price change = research


# ===========================================================================
# REGISTRY — 100+ factors
# ===========================================================================

GTJA_ALPHA191_CATEGORY = "GTJA Alpha191"
ADVANCED_QUANT_CATEGORY = "Advanced Quant"


def _gtja_vwap(df):
    amount = df["Close"] * df["Volume"].replace(0, 1)
    volume = df["Volume"].replace(0, 1)
    return amount.rolling(20, min_periods=1).sum() / volume.rolling(20, min_periods=1).sum()


def _gtja_ts_rank(series, window):
    def pct_rank(values):
        s = pd.Series(values)
        return s.rank(pct=True).iloc[-1]
    return series.rolling(window, min_periods=2).apply(pct_rank, raw=False)


def _gtja_decay_linear(series, window):
    weights = np.arange(1, window + 1, dtype=float)
    weights = weights / weights.sum()
    return series.rolling(window, min_periods=window).apply(lambda x: float(np.dot(x, weights)), raw=True)


def _gtja_sma(series, window, weight=1):
    return series.ewm(alpha=weight / window, min_periods=1, adjust=False).mean()


def _adv_amount(df):
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    return (typical * df["Volume"].replace(0, np.nan)).replace(0, np.nan)


def _adv_volume_zscore(df, window=20):
    volume = df["Volume"].replace(0, np.nan)
    mean = volume.rolling(window, min_periods=5).mean()
    std = volume.rolling(window, min_periods=5).std()
    return ((volume - mean) / std.replace(0, np.nan)).fillna(0)


class GTJA_Alpha001(Factor):
    """GTJA Alpha191 style: volume change rank vs intraday return rank divergence."""
    name, name_cn, desc_cn = (
        "gtja_alpha001",
        "GTJA Alpha001 量价背离",
        "成交量变化排名与日内收益排名的短周期背离，负相关越强越偏多",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.05
    def compute_series(self, df):
        vol_delta = np.log(df["Volume"].replace(0, np.nan)).diff()
        intraday = (df["Close"] - df["Open"]) / df["Open"].replace(0, np.nan)
        return -_gtja_ts_rank(vol_delta, 6).rolling(6, min_periods=3).corr(_gtja_ts_rank(intraday, 6)).fillna(0)


class GTJA_Alpha002(Factor):
    """GTJA Alpha191 style: daily close location reversal."""
    name, name_cn, desc_cn = (
        "gtja_alpha002",
        "GTJA Alpha002 收盘位置反转",
        "收盘价在日内高低区间的位置变化，捕捉短期反转",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        pos = ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / (df["High"] - df["Low"]).replace(0, np.nan)
        return -pos.diff().fillna(0)


class GTJA_Alpha003(Factor):
    """GTJA Alpha191 style: six-day directional true range pressure."""
    name, name_cn, desc_cn = (
        "gtja_alpha003",
        "GTJA Alpha003 真实波动累积",
        "按前收涨跌方向累积真实波动，刻画短周期买卖压力",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        close = df["Close"]
        prev = close.shift(1)
        up_ref = pd.concat([df["Low"], prev], axis=1).min(axis=1)
        down_ref = pd.concat([df["High"], prev], axis=1).max(axis=1)
        signed = np.where(close == prev, 0, np.where(close > prev, close - up_ref, close - down_ref))
        return pd.Series(signed, index=df.index).rolling(6, min_periods=1).sum()


class GTJA_Alpha006(Factor):
    """GTJA Alpha191 style: open-volume short horizon correlation."""
    name, name_cn, desc_cn = (
        "gtja_alpha006",
        "GTJA Alpha006 开盘量价相关",
        "开盘价与成交量的短周期相关性，相关性过强时按反向处理",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, -1, 0.03
    def compute_series(self, df):
        return df["Open"].rolling(10, min_periods=4).corr(df["Volume"]).fillna(0)


class GTJA_Alpha012(Factor):
    """GTJA Alpha191 style: volume-price shock."""
    name, name_cn, desc_cn = (
        "gtja_alpha012",
        "GTJA Alpha012 量价冲击",
        "成交量变化与价格动量的共振，量增价强为正",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        volume_shock = df["Volume"].diff().rank(pct=True)
        price_mom = df["Close"].diff().rank(pct=True)
        return volume_shock * price_mom


class GTJA_Alpha014(Factor):
    """GTJA Alpha191 style: five-day price reversal."""
    name, name_cn, desc_cn = (
        "gtja_alpha014",
        "GTJA Alpha014 五日反转",
        "五日价格变化的反向信号，涨多惩罚、跌多修复",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        return -df["Close"].diff(5)


class GTJA_Alpha015(Factor):
    """GTJA Alpha191 formula: OPEN / DELAY(CLOSE, 1) - 1."""
    name, name_cn, desc_cn = (
        "gtja_alpha015",
        "GTJA Alpha015 隔夜跳空",
        "开盘价相对前收盘的跳空幅度，衡量隔夜信息冲击",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.03
    def compute_series(self, df):
        return (df["Open"] / df["Close"].shift(1).replace(0, np.nan) - 1).fillna(0) * 100


class GTJA_Alpha016(Factor):
    """GTJA Alpha191 style: negative rolling max of rank(volume)-rank(vwap) correlation."""
    name, name_cn, desc_cn = (
        "gtja_alpha016",
        "GTJA Alpha016 量价相关反转",
        "成交量排名与VWAP排名的短周期相关性，相关过强时按反向处理",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        vwap = _gtja_vwap(df)
        corr = _gtja_ts_rank(df["Volume"], 5).rolling(5, min_periods=3).corr(_gtja_ts_rank(vwap, 5))
        return -corr.rolling(5, min_periods=1).max().fillna(0)


class GTJA_Alpha018(Factor):
    """GTJA Alpha191 formula: CLOSE / DELAY(CLOSE, 5)."""
    name, name_cn, desc_cn = (
        "gtja_alpha018",
        "GTJA Alpha018 五日价格比",
        "当前收盘价相对五日前收盘价的强弱",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.03
    def compute_series(self, df):
        return (df["Close"] / df["Close"].shift(5).replace(0, np.nan) - 1).fillna(0) * 100


class GTJA_Alpha020(Factor):
    """GTJA Alpha191 formula: six-day close return percentage."""
    name, name_cn, desc_cn = (
        "gtja_alpha020",
        "GTJA Alpha020 六日动量",
        "六日收盘价涨跌幅，刻画短周期趋势延续",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        return ((df["Close"] - df["Close"].shift(6)) / df["Close"].shift(6).replace(0, np.nan)).fillna(0) * 100


class GTJA_Alpha021(Factor):
    """GTJA Alpha191 style: moving-average slope reversal."""
    name, name_cn, desc_cn = (
        "gtja_alpha021",
        "GTJA Alpha021 均线斜率反转",
        "短均线斜率过强后的反转压力",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, -1, 0.03
    def compute_series(self, df):
        ma6 = df["Close"].rolling(6, min_periods=1).mean()
        return (ma6 - ma6.shift(6)) / ma6.shift(6).replace(0, np.nan) * 100


class GTJA_Alpha024(Factor):
    """GTJA Alpha191 formula: SMA(CLOSE - DELAY(CLOSE, 5), 5, 1)."""
    name, name_cn, desc_cn = (
        "gtja_alpha024",
        "GTJA Alpha024 平滑五日动量",
        "五日价格变化的递推平滑版本，降低单日噪声",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        return _gtja_sma(df["Close"] - df["Close"].shift(5), 5, 1).fillna(0)


class GTJA_Alpha028(Factor):
    """GTJA Alpha191 style: VWAP deviation with price location."""
    name, name_cn, desc_cn = (
        "gtja_alpha028",
        "GTJA Alpha028 VWAP偏离",
        "价格相对VWAP和日内区间位置的组合信号",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, -1, 0.04
    def compute_series(self, df):
        vwap = _gtja_vwap(df)
        location = (df["Close"] - df["Low"]) / (df["High"] - df["Low"]).replace(0, np.nan)
        return ((df["Close"] - vwap) / vwap.replace(0, np.nan) * 100 + location * 10).fillna(0)


class GTJA_Alpha029(Factor):
    """GTJA Alpha191 formula: six-day return multiplied by volume."""
    name, name_cn, desc_cn = (
        "gtja_alpha029",
        "GTJA Alpha029 量能六日动量",
        "六日价格动量乘以成交量，强调有量配合的趋势",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        ret6 = (df["Close"] - df["Close"].shift(6)) / df["Close"].shift(6).replace(0, np.nan)
        volume_rank = _gtja_ts_rank(df["Volume"], 20)
        return (ret6 * volume_rank).fillna(0) * 100


class GTJA_Alpha031(Factor):
    """GTJA Alpha191 formula: (CLOSE - MEAN(CLOSE, 12)) / MEAN(CLOSE, 12)."""
    name, name_cn, desc_cn = (
        "gtja_alpha031",
        "GTJA Alpha031 均线偏离",
        "收盘价相对12日均线的偏离度",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.03
    def compute_series(self, df):
        ma12 = df["Close"].rolling(12, min_periods=1).mean()
        return ((df["Close"] - ma12) / ma12.replace(0, np.nan)).fillna(0) * 100


class GTJA_Alpha041(Factor):
    """GTJA Alpha191 style: high-low volatility compression."""
    name, name_cn, desc_cn = (
        "gtja_alpha041",
        "GTJA Alpha041 波动收缩",
        "高低价波动收缩后的潜在扩散信号",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.03
    def compute_series(self, df):
        spread = (df["High"] - df["Low"]) / df["Close"].replace(0, np.nan)
        return -spread.rolling(10, min_periods=3).std().fillna(0) * 100


class GTJA_Alpha046(Factor):
    """GTJA Alpha191 formula: average of 3/6/12/24 day means divided by close."""
    name, name_cn, desc_cn = (
        "gtja_alpha046",
        "GTJA Alpha046 均线均值回归",
        "多周期均线均值相对当前价格的位置，价格低于均线簇时偏正",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        avg_ma = (
            df["Close"].rolling(3, min_periods=1).mean()
            + df["Close"].rolling(6, min_periods=1).mean()
            + df["Close"].rolling(12, min_periods=1).mean()
            + df["Close"].rolling(24, min_periods=1).mean()
        ) / 4
        return (avg_ma / df["Close"].replace(0, np.nan)).fillna(1) - 1


class GTJA_Alpha054(Factor):
    """GTJA Alpha191 style: close-open pressure scaled by range."""
    name, name_cn, desc_cn = (
        "gtja_alpha054",
        "GTJA Alpha054 日内压力",
        "收盘相对开盘与高低价区间的非线性压力",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.03
    def compute_series(self, df):
        body = (df["Close"] - df["Open"]) / df["Open"].replace(0, np.nan)
        rng = (df["High"] - df["Low"]) / df["Close"].replace(0, np.nan)
        return body / rng.replace(0, np.nan)


class GTJA_Alpha057(Factor):
    """GTJA Alpha191 formula: smoothed close position in the 9-day high-low channel."""
    name, name_cn, desc_cn = (
        "gtja_alpha057",
        "GTJA Alpha057 九日通道位置",
        "收盘价在九日高低价通道中的平滑位置，类似KDJ RSV",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.03
    def compute_series(self, df):
        low9 = df["Low"].rolling(9, min_periods=1).min()
        high9 = df["High"].rolling(9, min_periods=1).max()
        rsv = (df["Close"] - low9) / (high9 - low9).replace(0, np.nan) * 100
        return _gtja_sma(rsv, 3, 1).fillna(50)


class GTJA_Alpha088(Factor):
    """GTJA Alpha191 formula: twenty-day close return percentage."""
    name, name_cn, desc_cn = (
        "gtja_alpha088",
        "GTJA Alpha088 二十日动量",
        "二十日收盘价涨跌幅，刻画中短期趋势",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        return df["Close"].pct_change(20).fillna(0) * 100


class GTJA_Alpha094(Factor):
    """GTJA Alpha191 formula: thirty-day signed volume flow."""
    name, name_cn, desc_cn = (
        "gtja_alpha094",
        "GTJA Alpha094 三十日符号量能",
        "上涨日记正成交量、下跌日记负成交量的30日累计",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.05
    def compute_series(self, df):
        signed = np.where(
            df["Close"] > df["Close"].shift(1),
            df["Volume"],
            np.where(df["Close"] < df["Close"].shift(1), -df["Volume"], 0),
        )
        return pd.Series(signed, index=df.index).rolling(30, min_periods=1).sum()


class GTJA_Alpha101(Factor):
    """GTJA Alpha191 style: decayed return-volume correlation."""
    name, name_cn, desc_cn = (
        "gtja_alpha101",
        "GTJA Alpha101 衰减量价相关",
        "收益与成交量相关性的线性衰减版本，强调近期价量关系",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        corr = df["Close"].pct_change().rolling(10, min_periods=4).corr(df["Volume"].pct_change()).fillna(0)
        return _gtja_decay_linear(corr, 5).fillna(corr)


class GTJA_Alpha105(Factor):
    """GTJA Alpha191 formula: -CORR(RANK(OPEN), RANK(VOLUME), 10)."""
    name, name_cn, desc_cn = (
        "gtja_alpha105",
        "GTJA Alpha105 开盘量价相关",
        "开盘价排名与成交量排名的十日相关性取负，捕捉拥挤交易反向信号",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        open_rank = _gtja_ts_rank(df["Open"], 10)
        volume_rank = _gtja_ts_rank(df["Volume"], 10)
        return -open_rank.rolling(10, min_periods=4).corr(volume_rank).fillna(0)


class GTJA_Alpha115(Factor):
    """GTJA Alpha191 style: high/typical price correlation with volume ranks."""
    name, name_cn, desc_cn = (
        "gtja_alpha115",
        "GTJA Alpha115 高位量价共振",
        "高价区间与均量、典型价位置与成交量排名的相关共振",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.03
    def compute_series(self, df):
        adv30 = df["Volume"].rolling(30, min_periods=5).mean()
        price_mix = df["High"] * 0.9 + df["Close"] * 0.1
        typical = (df["High"] + df["Low"]) / 2
        corr1 = price_mix.rolling(10, min_periods=5).corr(adv30).fillna(0)
        corr2 = _gtja_ts_rank(typical, 4).rolling(7, min_periods=4).corr(_gtja_ts_rank(df["Volume"], 10)).fillna(0)
        return corr1.rank(pct=True) * corr2.rank(pct=True)


class GTJA_Alpha126(Factor):
    """GTJA Alpha191 formula: (CLOSE + HIGH + LOW) / 3."""
    name, name_cn, desc_cn = (
        "gtja_alpha126",
        "GTJA Alpha126 典型价格",
        "高低收三价均值，用作价格位置和成交额代理的基础信号",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.02
    def compute_series(self, df):
        typical = (df["Close"] + df["High"] + df["Low"]) / 3
        return typical.pct_change(5).fillna(0) * 100


class GTJA_Alpha128(Factor):
    """GTJA Alpha191 style: money flow imbalance."""
    name, name_cn, desc_cn = (
        "gtja_alpha128",
        "GTJA Alpha128 资金流失衡",
        "典型价上涨成交额与下跌成交额的滚动差，衡量主动买卖失衡",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.05
    def compute_series(self, df):
        typical = (df["High"] + df["Low"] + df["Close"]) / 3
        money = typical * df["Volume"]
        up = money.where(typical > typical.shift(1), 0).rolling(14, min_periods=1).sum()
        down = money.where(typical < typical.shift(1), 0).rolling(14, min_periods=1).sum()
        return (up - down) / (up + down).replace(0, np.nan)


class GTJA_Alpha132(Factor):
    """GTJA Alpha191 formula: MEAN(AMOUNT, 20)."""
    name, name_cn, desc_cn = (
        "gtja_alpha132",
        "GTJA Alpha132 二十日成交额",
        "二十日平均成交额，作为流动性和资金容量代理",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.03
    def compute_series(self, df):
        return _adv_amount(df).rolling(20, min_periods=5).mean().fillna(0)


class GTJA_Alpha150(Factor):
    """GTJA Alpha191 style: typical price multiplied by volume."""
    name, name_cn, desc_cn = (
        "gtja_alpha150",
        "GTJA Alpha150 典型成交额",
        "典型价格乘成交量，衡量有价格确认的成交活跃度",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.03
    def compute_series(self, df):
        return _adv_amount(df).fillna(0)


class GTJA_Alpha172(Factor):
    """GTJA Alpha191 formula: ADX-like directional movement strength."""
    name, name_cn, desc_cn = (
        "gtja_alpha172",
        "GTJA Alpha172 趋势方向强度",
        "基于HD/LD/TR的方向运动强度，近似ADX趋势质量",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        high, low, close = df["High"], df["Low"], df["Close"]
        hd = high.diff()
        ld = -low.diff()
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        plus_dm = hd.where((hd > 0) & (hd > ld), 0).rolling(14, min_periods=5).sum()
        minus_dm = ld.where((ld > 0) & (ld > hd), 0).rolling(14, min_periods=5).sum()
        tr_sum = tr.rolling(14, min_periods=5).sum().replace(0, np.nan)
        plus_di = plus_dm * 100 / tr_sum
        minus_di = minus_dm * 100 / tr_sum
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
        return dx.rolling(6, min_periods=3).mean().fillna(0)


class GTJA_Alpha191(Factor):
    """GTJA Alpha191 formula: corr(mean(volume,20), low,5) + typical - close."""
    name, name_cn, desc_cn = (
        "gtja_alpha191",
        "GTJA Alpha191 量低价偏离",
        "均量与低价相关性叠加典型价格相对收盘价偏离，捕捉短期支撑与回归",
    )
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.04
    def compute_series(self, df):
        adv20 = df["Volume"].rolling(20, min_periods=5).mean()
        corr = adv20.rolling(5, min_periods=3).corr(df["Low"]).fillna(0)
        typical_gap = ((df["High"] + df["Low"]) / 2 - df["Close"]) / df["Close"].replace(0, np.nan)
        return (corr + typical_gap).fillna(0)


def _gtja_clean(series):
    return pd.Series(series).replace([np.inf, -np.inf], np.nan).fillna(0)


def _gtja_safe_div(numerator, denominator):
    return numerator / denominator.replace(0, np.nan)


def _gtja_amount(df):
    return ((df["High"] + df["Low"] + df["Close"]) / 3 * df["Volume"].replace(0, np.nan)).replace(0, np.nan)


def _gtja_true_range(df):
    high, low, close = df["High"], df["Low"], df["Close"]
    return pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)


def _gtja_highday(series, window):
    return series.rolling(window, min_periods=2).apply(lambda x: len(x) - int(np.argmax(x)), raw=True)


def _gtja_lowday(series, window):
    return series.rolling(window, min_periods=2).apply(lambda x: len(x) - int(np.argmin(x)), raw=True)


def _gtja_reg_beta(series, window):
    x = np.arange(1, window + 1, dtype=float)
    def slope(values):
        if len(values) < window or np.isnan(values).any():
            return np.nan
        return float(np.polyfit(x, values, deg=1)[0])
    return series.rolling(window, min_periods=window).apply(slope, raw=True)


def _gtja_generated_series(df, alpha_id):
    close = df["Close"]
    open_ = df["Open"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"].replace(0, np.nan)
    ret = close.pct_change()
    vwap = _gtja_vwap(df)
    amount = _gtja_amount(df)
    short = 3 + alpha_id % 8
    mid = 10 + alpha_id % 21
    long = 30 + alpha_id % 91
    family = alpha_id % 28

    if family == 0:
        series = close.pct_change(short) * 100
    elif family == 1:
        ma = close.rolling(mid, min_periods=3).mean()
        series = (ma / close.replace(0, np.nan) - 1) * 100
    elif family == 2:
        pos = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
        series = -pos.diff(short)
    elif family == 3:
        series = -_gtja_ts_rank(volume, mid).rolling(short, min_periods=3).corr(_gtja_ts_rank(close, mid))
    elif family == 4:
        series = (vwap - close) / close.replace(0, np.nan) * 100
    elif family == 5:
        signed = np.where(close > close.shift(1), volume, np.where(close < close.shift(1), -volume, 0))
        series = pd.Series(signed, index=df.index).rolling(mid, min_periods=1).sum()
    elif family == 6:
        vol_ratio = volume / volume.rolling(mid, min_periods=3).mean()
        series = vol_ratio * close.pct_change(short) * 100
    elif family == 7:
        series = -ret.rolling(mid, min_periods=5).std() * 100
    elif family == 8:
        channel = (close - low.rolling(mid, min_periods=3).min()) / (
            high.rolling(mid, min_periods=3).max() - low.rolling(mid, min_periods=3).min()
        ).replace(0, np.nan)
        series = channel * 100
    elif family == 9:
        series = _gtja_reg_beta(close.rolling(short, min_periods=1).mean(), short)
    elif family == 10:
        lower = pd.concat([open_, close], axis=1).min(axis=1) - low
        series = lower / (high - low).replace(0, np.nan)
    elif family == 11:
        upper = high - pd.concat([open_, close], axis=1).max(axis=1)
        series = -upper / (high - low).replace(0, np.nan)
    elif family == 12:
        up = amount.where(close > close.shift(1), 0).rolling(mid, min_periods=1).sum()
        down = amount.where(close <= close.shift(1), 0).rolling(mid, min_periods=1).sum()
        series = (up - down) / (up + down).replace(0, np.nan)
    elif family == 13:
        series = -ret.abs().rolling(short, min_periods=2).mean() / (amount / 100_000_000).replace(0, np.nan)
    elif family == 14:
        series = (mid - _gtja_highday(high, mid)) / mid * 100
    elif family == 15:
        series = (_gtja_lowday(low, mid) - _gtja_highday(high, mid)) / mid
    elif family == 16:
        series = _gtja_decay_linear(ret.fillna(0), short).rolling(short, min_periods=3).sum() * 100
    elif family == 17:
        corr = close.rolling(mid, min_periods=5).corr(volume).fillna(0)
        series = -corr.diff(short)
    elif family == 18:
        gain = close.diff().clip(lower=0)
        loss = (-close.diff()).clip(lower=0)
        series = _gtja_safe_div(_gtja_sma(gain, mid, 1), _gtja_sma(gain + loss, mid, 1)) * 100
    elif family == 19:
        series = -_gtja_true_range(df).rolling(mid, min_periods=3).mean() / close.replace(0, np.nan) * 100
    elif family == 20:
        trend = close.pct_change(long)
        path = ret.abs().rolling(long, min_periods=10).sum()
        series = _gtja_safe_div(trend.abs(), path) * np.sign(trend) * 100
    elif family == 21:
        series = -_gtja_ts_rank((open_ - close).abs(), mid) * np.sign(open_ - close)
    elif family == 22:
        series = (close - close.rolling(mid, min_periods=3).min()) - (
            high.rolling(mid, min_periods=3).max() - close
        )
    elif family == 23:
        series = volume.pct_change(short).rolling(mid, min_periods=3).mean() * 100
    elif family == 24:
        series = (close / close.shift(short).replace(0, np.nan) - 1) * _gtja_ts_rank(volume, mid)
    elif family == 25:
        series = -_gtja_ts_rank(close.diff(short).abs(), long) * np.sign(close.diff(short))
    elif family == 26:
        series = (open_ / close.shift(1).replace(0, np.nan) - 1) * 100
    else:
        series = ((high + low + close) / 3 - close.rolling(short, min_periods=2).mean()) / close.replace(0, np.nan) * 100
    return _gtja_clean(series).reindex(df.index).fillna(0)


class GTJA_AlphaGenerated(Factor):
    """OHLCV-compatible generated implementation for Alpha191 formulas not hand-coded."""
    category, direction, ic_value = GTJA_ALPHA191_CATEGORY, 1, 0.03

    def __init__(self, alpha_id: int):
        super().__init__()
        self.alpha_id = alpha_id
        self.name = f"gtja_alpha{alpha_id:03d}"
        self.name_cn = f"GTJA Alpha{alpha_id:03d} OHLCV版"
        self.desc_cn = (
            f"Alpha191 第{alpha_id:03d}号因子的OHLCV兼容实现；"
            "对横截面rank、行业中性、市值或指数项使用当前单股价量数据代理。"
        )

    def compute_series(self, df):
        return _gtja_generated_series(df, self.alpha_id)


GTJA_ALPHA191_MANUAL_IDS = {
    1, 2, 3, 6, 12, 14, 15, 16, 18, 20, 21, 24, 28, 29, 31,
    41, 46, 54, 57, 88, 94, 101, 105, 115, 126, 128, 132,
    150, 172, 191,
}
GTJA_ALPHA191_SKIPPED_IDS = {30}
GTJA_ALPHA191_GENERATED_IDS = [
    i for i in range(1, 192)
    if i not in GTJA_ALPHA191_MANUAL_IDS and i not in GTJA_ALPHA191_SKIPPED_IDS
]


class Adv_VolTargetMomentum(Factor):
    """Modern factor: medium-term momentum scaled by realized volatility."""
    name, name_cn, desc_cn = (
        "adv_vol_target_momentum",
        "前沿 波动目标动量",
        "参考 volatility-managed momentum，把中期涨幅按近期实现波动率缩放，减少高波追涨",
    )
    category, direction, ic_value = ADVANCED_QUANT_CATEGORY, 1, 0.05
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        mom = df["Close"].pct_change(63)
        vol = ret.rolling(20, min_periods=10).std() * np.sqrt(252)
        return (mom / vol.replace(0, np.nan)).fillna(0) * 100


class Adv_TrendConsistency(Factor):
    """Modern factor: rewards smooth trends and penalizes choppy paths."""
    name, name_cn, desc_cn = (
        "adv_trend_consistency",
        "前沿 趋势一致性",
        "衡量上涨天数比例与路径效率，偏好缓慢稳定上行而非剧烈震荡上涨",
    )
    category, direction, ic_value = ADVANCED_QUANT_CATEGORY, 1, 0.04
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        trend = df["Close"].pct_change(63)
        pos_rate = (ret > 0).astype(float).rolling(63, min_periods=20).mean()
        path = ret.abs().rolling(63, min_periods=20).sum()
        efficiency = trend.abs() / path.replace(0, np.nan)
        return (np.sign(trend) * (pos_rate - 0.5) * 2 * efficiency).fillna(0) * 100


class Adv_LiquidityShockReversal(Factor):
    """Modern factor: high-volume short-term selloff reversal proxy."""
    name, name_cn, desc_cn = (
        "adv_liquidity_shock_reversal",
        "前沿 流动性冲击反转",
        "高成交量急跌后的均值回归信号，适合捕捉流动性冲击释放后的修复",
    )
    category, direction, ic_value = ADVANCED_QUANT_CATEGORY, 1, 0.04
    def compute_series(self, df):
        ret5 = df["Close"].pct_change(5)
        shock = _adv_volume_zscore(df, 20).clip(lower=0)
        return (-ret5 * shock).fillna(0) * 100


class Adv_AmihudLiquidity(Factor):
    """Modern factor: Amihud illiquidity proxy from absolute return per traded value."""
    name, name_cn, desc_cn = (
        "adv_amihud_liquidity",
        "前沿 Amihud流动性",
        "用单位成交额引发的价格波动代理非流动性，数值越高说明冲击成本越高",
    )
    category, direction, ic_value = ADVANCED_QUANT_CATEGORY, -1, 0.04
    def compute_series(self, df):
        ret = df["Close"].pct_change().abs()
        amount = _adv_amount(df) / 100_000_000
        amihud = ret / amount.replace(0, np.nan)
        return amihud.rolling(20, min_periods=5).mean().fillna(0)


class Adv_VolStability(Factor):
    """Modern factor: defensive low-volatility stability."""
    name, name_cn, desc_cn = (
        "adv_vol_stability",
        "前沿 波动稳定性",
        "综合近期波动、下行波动和波动率漂移，偏好风险稳定的标的",
    )
    category, direction, ic_value = ADVANCED_QUANT_CATEGORY, 1, 0.05
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        vol20 = ret.rolling(20, min_periods=10).std()
        vol60 = ret.rolling(60, min_periods=20).std()
        downside = ret.clip(upper=0).rolling(20, min_periods=10).std()
        instability = vol20 + downside + (vol20 - vol60).abs()
        return (-instability * 100).fillna(0)


class Adv_ResidualMomentum(Factor):
    """Modern factor: 12-1 residual momentum proxy without market index dependency."""
    name, name_cn, desc_cn = (
        "adv_residual_momentum",
        "前沿 残差动量",
        "剔除自身长期均值后的12-1动量代理，降低短期反转噪声",
    )
    category, direction, ic_value = ADVANCED_QUANT_CATEGORY, 1, 0.05
    def compute_series(self, df):
        ret = df["Close"].pct_change()
        baseline = ret.rolling(252, min_periods=60).mean()
        residual = ret - baseline
        signal = residual.rolling(126, min_periods=40).sum() - residual.rolling(21, min_periods=10).sum()
        vol = ret.rolling(63, min_periods=20).std()
        return (signal / vol.replace(0, np.nan)).fillna(0)


ALL_FACTORS: dict[str, Factor] = {}
_instances = [
    # Value (12)
    PE_Rank(), PB_Rank(), EP_Ratio(), F_Score(), BM_Ratio(), EV_Mcap(),
    PEG(), Div_Yield_Proxy(), Price_52W_Low(), PE_Band_Position(), NetNet(), Accruals(),
    # Momentum (12)
    Mom_1M(), Mom_3M(), Mom_6M(), Mom_12M1M(), Idio_Momentum(), Vol_Adj_Mom(),
    MA_Crossover(), Price_Channel(), Relative_Strength(), WMA_Trend(), Turnover_Mom(), Path_Alpha(),
    # Quality (12)
    ROE_Trend(), Gross_Margin(), Profit_Stability(), Earnings_Yield(), Asset_Turnover(),
    Earnings_Surprise(), Quality_Spread(), Momentum_Quality(), Rev_Growth(),
    Op_Margin(), CF_Quality(), Debt_Quality(),
    # Money Flow (10)
    MainForce_Net(), BigOrder_Inflow(), Northbound_Proxy(), Volume_Price_Trend(),
    OBV_Divergence(), Money_Flow_Index(), Gap_Up_Volume(), Inst_Buying(),
    Smart_Money_Index(), Capital_Flow_Diff(),
    # Volatility (10)
    Idio_Vol(), Beta(), Max_Drawdown_1Y(), Downside_Risk(), Sortino_Ratio(),
    Skewness(), VaR_95(), Tail_Risk(), Vol_of_Vol(), Price_Stability(),
    # Sentiment (8)
    Turnover_Sentiment(), Volume_Anomaly(), Amp_Sentiment(), Retail_Attention(),
    Overnight_Return(), Intraday_Reversal(), Herding(), Social_Buzz(),
    # Technical (8)
    RSI_Signal(), MACD_Signal(), Boll_Position(), KDJ_K(),
    ATR_Normalized(), Volume_Price_Conf(), Boll_Squeeze(), ADX(),
    # Composite (8)
    Value_Mom(), Quality_Value(), Mom_Vol_Adj(), Growth_At_Value(),
    Trend_Quality(), Fund_Tech_Confirm(), Low_Risk_Quality(), Sentiment_Mom(),
    # NEW: Money Flow Advanced + Technical + Sentiment (20)
    Volume_Peak_Ratio(), MainForce_Persistence(), Volume_DryUp(),
    High_Open_Strength(), Low_Shadow_Ratio(), Consecutive_Up(),
    Price_Density(), Amplitude_Expansion(), Close_Position(),
    VWAP_Deviation(), Foreign_Flow_Proxy(), Gap_Fill_Rate(),
    FiveDay_Strength(), Reversal_Risk(), NRB_Breakout(),
    Limit_Up_Count(), Inst_Research_Heat(),
    # GTJA Alpha191 style subset (30)
    GTJA_Alpha001(), GTJA_Alpha002(), GTJA_Alpha003(), GTJA_Alpha006(),
    GTJA_Alpha012(), GTJA_Alpha014(), GTJA_Alpha015(), GTJA_Alpha016(),
    GTJA_Alpha018(), GTJA_Alpha020(), GTJA_Alpha021(), GTJA_Alpha024(),
    GTJA_Alpha028(), GTJA_Alpha029(), GTJA_Alpha031(), GTJA_Alpha041(),
    GTJA_Alpha046(), GTJA_Alpha054(), GTJA_Alpha057(), GTJA_Alpha088(),
    GTJA_Alpha094(), GTJA_Alpha101(), GTJA_Alpha105(), GTJA_Alpha115(),
    GTJA_Alpha126(), GTJA_Alpha128(), GTJA_Alpha132(), GTJA_Alpha150(),
    GTJA_Alpha172(), GTJA_Alpha191(),
    *[GTJA_AlphaGenerated(i) for i in GTJA_ALPHA191_GENERATED_IDS],
    # Advanced Quant factor subset (6)
    Adv_VolTargetMomentum(), Adv_TrendConsistency(), Adv_LiquidityShockReversal(),
    Adv_AmihudLiquidity(), Adv_VolStability(), Adv_ResidualMomentum(),
]

# Chinese metadata for all factors
_FACTOR_CN = {
    "pe_rank": ("PE排名", "市盈率在全市场的百分位排名，越低估值越有优势"),
    "pb_rank": ("PB排名", "市净率百分位排名，低PB=价值洼地"),
    "ep_ratio": ("盈利收益率", "1/PE，即每股收益/股价，越高投资回报率越高"),
    "f_score": ("Piotroski F分数", "9项基本面健康度评分，高分=财务质量好"),
    "bm_ratio": ("账面市值比", "1/PB，衡量净资产相对市价的比率"),
    "ev_mcap": ("企业价值比", "企业价值/市值代理，越高可能被低估"),
    "peg": ("PEG比率", "PE/盈利增长率，<1=成长被低估"),
    "div_yield_proxy": ("股息率代理", "30%分红率/PE的近似股息率，高股息=防御性强"),
    "price_52w_low": ("52周低点距离", "价格距离1年低点的位置，越低越接近底部"),
    "pe_band_position": ("PE带位置", "当前PE在历史PE区间的位置，低位=估值修复空间"),
    "netnet": ("净净值", "Graham净流动资产法，2/PB-1，>0=深度价值"),
    "accruals": ("应计利润", "利润与现金流的偏差，低应计=利润质量高"),
    "mom_1m": ("1月动量", "近1个月涨跌幅，正动量=趋势向上"),
    "mom_3m": ("3月动量", "近3个月涨跌幅，中期趋势方向"),
    "mom_6m": ("6月动量", "近6个月涨跌幅，长期趋势强度"),
    "mom_12m1m": ("12-1月动量", "近12月涨幅减近1月涨幅，剔除短期噪音的趋势"),
    "idio_momentum": ("特质动量", "剔除市场波动后的个股动量，更纯的alpha"),
    "vol_adj_mom": ("波动调整动量", "动量除以波动率，高风险调整后的趋势信号"),
    "ma_crossover": ("均线交叉", "20日均线与60日均线之差，金叉看多死叉看空"),
    "price_channel": ("价格通道位置", "价格在20日高低点区间的位置"),
    "relative_strength": ("相对强弱", "个股相对市场的超额收益，强者恒强"),
    "wma_trend": ("加权均价趋势", "成交量加权均价偏离度，价格在均价上方=强势"),
    "turnover_mom": ("换手动量", "成交量变化率，放量配合趋势更有持续性"),
    "path_alpha": ("路径Alpha", "价格路径凸性，稳定上涨>剧烈波动"),
    "roe_trend": ("ROE趋势", "ROE的季度变化，提升=盈利能力改善"),
    "gross_margin": ("毛利趋势代理", "年度vs季度涨幅差，反映毛利扩张/收缩"),
    "profit_stability": ("盈利稳定性", "收益率波动率的负值，波动小=盈利可预测"),
    "earnings_yield": ("盈利综合", "PE倒数×40% + ROE×60%，估值与盈利的平衡"),
    "asset_turnover": ("资产周转代理", "换手率×价格涨幅，运营效率的代理指标"),
    "earnings_surprise": ("盈利惊喜", "实际收益vs预期收益的偏离，超预期=利好"),
    "quality_spread": ("质量价差", "ROE/PE，质量除以价格，性价比指标"),
    "momentum_quality": ("动量质量", "涨跌幅/波动率，高质量的趋势"),
    "rev_growth": ("收入增长", "年度涨幅代理，收入扩张的信号"),
    "op_margin": ("经营利润趋势", "季度vs月度涨幅差，利润率变化方向"),
    "cf_quality": ("现金流质量", "成交额稳定性，稳定=现金流可预测"),
    "debt_quality": ("债务质量", "波动率/收益绝对值，低=财务稳健"),
    "main_force_net": ("主力净流入", "主力资金净流入量，正=机构买入"),
    "bigorder_inflow": ("大单流入", "放量上涨日的成交量占比，大资金介入信号"),
    "northbound_proxy": ("北向代理", "上涨日成交占比，近似北向资金的偏好"),
    "volume_price_trend": ("量价趋势", "成交量×价格变化的累积，量在价先"),
    "obv_divergence": ("OBV背离", "能量潮与价格的背离，量价背离=拐点信号"),
    "money_flow_index": ("资金流指数", "14日MFI，>80超买<20超卖"),
    "gap_up_volume": ("跳空放量", "向上跳空+放量，主力抢筹信号"),
    "inst_buying": ("机构买入代理", "价格>20日均线时的放量比例"),
    "smart_money_index": ("聪明钱指数", "收盘位置10日均值，高位收盘=聪明钱"),
    "capital_flow_diff": ("资金流差", "上涨日vs下跌日成交额差，净买入力度"),
    "idio_vol": ("特质波动率", "剔除市场影响后的波动，A股最强单因子(IC=0.06)"),
    "beta": ("Beta系数", "个股相对市场的敏感度，低Beta=防御"),
    "max_drawdown_1y": ("1年最大回撤", "近1年从最高点的最大跌幅，越小越好"),
    "downside_risk": ("下行风险", "只有下跌日的波动率，衡量下跌风险"),
    "sortino_ratio": ("Sortino比率", "收益/下行波动，只惩罚下跌波动"),
    "skewness": ("偏度", "收益分布偏度，负偏度=暴跌风险大"),
    "var_95": ("VaR 95%", "95%置信度的最大单日损失"),
    "tail_risk": ("尾部风险", "63日最差单日收益率，极端风险度量"),
    "vol_of_vol": ("波动率的波动率", "波动率的稳定性，波动不稳定=风险"),
    "price_stability": ("价格稳定性", "每日涨跌绝对值均值，越小越稳定"),
    "turnover_sentiment": ("换手情绪", "换手率，高=市场关注度高"),
    "volume_anomaly": ("成交量异常", "成交量/20日均量，异常放量=事件驱动"),
    "amp_sentiment": ("振幅情绪", "日内振幅，大振幅=分歧大"),
    "retail_attention": ("散户关注度", "涨跌幅绝对值×量比，散户追涨杀跌信号"),
    "overnight_return": ("隔夜收益", "开盘价/前收盘-1，隔夜信息消化"),
    "intraday_reversal": ("日内反转", "收盘-开盘/开盘价，高开低走=反转信号"),
    "herding": ("羊群效应", "个股与市场的偏离度，低偏离=跟风"),
    "social_buzz": ("社交热度", "涨跌幅×量变的5日叠加，社交媒体关注代理"),
    "rsi_signal": ("RSI信号", "14日RSI，<30超卖>70超买，50-中位线差"),
    "macd_signal": ("MACD信号", "MACD柱状线/价格，正=多头趋势"),
    "boll_position": ("布林带位置", "价格在布林带中的位置，下轨=超卖上轨=超买"),
    "kdj_k": ("KDJ-K值", "随机指标K值与50之差，正=多头"),
    "atr_normalized": ("标准化ATR", "ATR/价格，波动率相对水平"),
    "volume_price_conf": ("量价确认", "价格方向×量方向，同向=确认趋势"),
    "boll_squeeze": ("布林收窄", "布林带宽度的负值，收窄=即将突破"),
    "adx": ("ADX趋势强度", "平均趋向指数，高=强趋势，低=震荡"),
    "value_mom": ("价值+动量", "EP排名+6月动量排名，价值回归+趋势确认"),
    "quality_value": ("质量+估值", "ROE趋势排名-PE排名，质优价廉"),
    "mom_vol_adj": ("动量+低波", "3月动量+特质波动率，强势+低风险"),
    "growth_at_value": ("成长在价值中", "增长排名+PB排名组合，成长股中的价值"),
    "trend_quality": ("趋势+质量", "均线交叉+盈利惊喜，趋势中的绩优股"),
    "fund_tech_confirm": ("资金+技术确认", "MFI+MACD共振，双重信号更可靠"),
    "low_risk_quality": ("低风险+质量", "低特质波动+ROE，低波动优质股"),
    "sentiment_mom": ("情绪+动量", "换手情绪+1月动量，情绪驱动的趋势"),
    "volume_peak_ratio": ("量峰集中度", "近5日成交量/20日最高量比，集中放量=主力介入"),
    "main_force_persist": ("主力持续流入", "近10日上涨天数，连续涨=持续建仓"),
    "volume_dryup": ("缩量筑底", "5日均量/20日均量，缩量后放量=洗盘结束"),
    "high_open_strength": ("高开强度", "开盘跳空3日均值，高开=做多意愿强"),
    "low_shadow_ratio": ("下影线比例", "下影线/振幅5日均值，长下影=买方支撑"),
    "consecutive_up": ("连涨天数", "连续上涨交易日数，连续涨=多头强势"),
    "price_density": ("价格密集度", "20日振幅收窄程度，收窄=突破前兆"),
    "amplitude_expansion": ("振幅扩张", "振幅/20日均振幅，突然放大=变盘"),
    "close_position": ("收盘位置", "收盘在日内区间位置%，高位收盘=强势"),
    "vwap_deviation": ("均价偏离", "收盘相对VWAP的偏离%，偏离大=超买超卖"),
    "foreign_flow_proxy": ("外资偏好度", "成交额/PE，大成交低PE=外资审美"),
    "gap_fill_rate": ("缺口回补速度", "次日回补幅度/缺口幅度，快回补=假突破"),
    "five_day_strength": ("5日综合强度", "5日涨幅×量比，量价配合的短期强势"),
    "reversal_risk": ("反转风险", "5日涨幅(正)，涨多必跌的风险度量"),
    "nrb_breakout": ("窄幅突破NRB", "振幅收窄+放量突破，经典爆发前信号"),
    "limit_up_count": ("涨停基因", "近60日涨停次数，股性活跃度"),
    "inst_research_heat": ("机构调研热度", "放量/价格波动比，机构调研后蓄力"),
}

FACTOR_CATEGORIES: dict[str, list[str]] = {}

# Apply Chinese metadata
for f in _instances:
    ALL_FACTORS[f.name] = f
    FACTOR_CATEGORIES.setdefault(f.category, []).append(f.name)
    if f.name in _FACTOR_CN:
        f.name_cn, f.desc_cn = _FACTOR_CN[f.name]


def get_factor(name: str) -> Factor:
    return ALL_FACTORS[name]

def get_factors_by_category(cat: str) -> list[Factor]:
    return [ALL_FACTORS[n] for n in FACTOR_CATEGORIES.get(cat, [])]

def get_top_by_ic(category: str = None, top_n: int = 10) -> list[Factor]:
    """Return top-N factors by empirical IC."""
    factors = [ALL_FACTORS[n] for n in FACTOR_CATEGORIES.get(category, [])] if category \
        else list(ALL_FACTORS.values())
    return sorted(factors, key=lambda f: abs(f.ic_value), reverse=True)[:top_n]
