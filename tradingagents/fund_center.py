"""Fund research data helpers for the Streamlit fund center.

The module uses direct Eastmoney/Tiantian Fund HTTP endpoints, matching the
project's A-share dataflow style without adding new vendor dependencies.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
import json
import math
import re
from typing import Any

import pandas as pd
import requests

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_HEADERS = {"User-Agent": _UA, "Referer": "https://fund.eastmoney.com/"}

PINGZHONGDATA_URL = "https://fund.eastmoney.com/pingzhongdata/{code}.js"
FUND_CATALOG_URL = "https://fund.eastmoney.com/js/fundcode_search.js"
RANKHANDLER_URL = "http://fund.eastmoney.com/data/rankhandler.aspx"
PUSH2_LIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
PUSH2_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"

DEFAULT_WATCHLIST = [
    "110011",
    "001475",
    "000083",
    "003834",
    "005827",
    "006502",
    "161725",
    "000001",
    "510300",
    "510500",
    "159919",
    "588000",
]

HORIZON_RANK_FIELDS = {
    "近1月": "1yzf",
    "近3月": "3yzf",
    "近6月": "6yzf",
    "近1年": "1nzf",
    "今年来": "jnzf",
}


def normalize_fund_code(value: str) -> str:
    """Return a strict six-digit fund code."""
    code = str(value or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("基金代码必须是6位数字")
    return code


def _to_float(value: Any, default: float | None = None) -> float | None:
    if value in (None, "", "-", "--"):
        return default
    try:
        if isinstance(value, str):
            value = value.strip().replace("%", "").replace(",", "")
        return float(value)
    except (TypeError, ValueError):
        return default


def _percent_to_rate(value: Any) -> float:
    parsed = _to_float(value, 0.0) or 0.0
    return parsed / 100.0


def _request_text(url: str, *, params: dict[str, Any] | None = None, timeout: int = 15) -> str:
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def classify_fund_type(raw_type: str | None, code: str, name: str) -> str:
    raw = raw_type or ""
    label = f"{raw} {name or ''}".upper()
    code = str(code or "")
    if code.startswith(("15", "16", "18", "50", "51", "52", "56", "58")):
        if "ETF" in label or "LOF" in label or raw == "":
            return "场内 ETF/LOF"
    if "QDII" in label:
        return "QDII"
    if "货币" in raw or "货币" in name:
        return "货币型"
    if "债券" in raw or "债券" in name:
        return "债券型"
    if "指数" in raw or "指数" in name or "ETF联接" in name:
        return "指数型"
    if "股票" in raw or "股票" in name:
        return "股票型"
    if "混合" in raw or "混合" in name:
        return "混合型"
    return "其他"


def _extract_var(text: str, name: str) -> str | None:
    match = re.search(rf"var\s+{re.escape(name)}\s*=\s*(.*?);", text, re.S)
    if not match:
        return None
    return match.group(1).strip()


def _extract_string(text: str, name: str) -> str:
    raw = _extract_var(text, name)
    if raw is None:
        return ""
    try:
        parsed = json.loads(raw)
        return str(parsed)
    except json.JSONDecodeError:
        return raw.strip("'\"")


def _extract_json_array(text: str, name: str) -> list[Any]:
    raw = _extract_var(text, name)
    if not raw or not raw.startswith("["):
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _timestamp_to_date(value: Any) -> str:
    try:
        ts = int(value)
        if ts > 10_000_000_000:
            ts = ts // 1000
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


def parse_pingzhongdata(text: str) -> dict[str, Any]:
    """Parse Tiantian Fund pingzhongdata JavaScript into a stable dict."""
    code = normalize_fund_code(_extract_string(text, "fS_code"))
    name = _extract_string(text, "fS_name") or code
    nav_points = _extract_json_array(text, "Data_netWorthTrend")
    nav_history = []
    for item in nav_points:
        nav = _to_float(item.get("y") if isinstance(item, dict) else None)
        day = _timestamp_to_date(item.get("x") if isinstance(item, dict) else None)
        if nav is not None and day:
            nav_history.append({"date": day, "nav": nav})

    holdings = []
    for raw_code in _extract_json_array(text, "stockCodesNew"):
        clean = str(raw_code).split(".")[-1]
        if re.fullmatch(r"\d{6}", clean):
            holdings.append(clean)

    returns = {
        "近1月": _to_float(_extract_string(text, "syl_1y")),
        "近3月": _to_float(_extract_string(text, "syl_3y")),
        "近6月": _to_float(_extract_string(text, "syl_6y")),
        "近1年": _to_float(_extract_string(text, "syl_1n")),
    }
    returns = {k: v for k, v in returns.items() if v is not None}
    metrics = compute_nav_metrics(nav_history)
    latest = nav_history[-1] if nav_history else {}
    raw_type = _extract_string(text, "fund_type") or _extract_string(text, "Data_fluctuationScale")

    return {
        "code": code,
        "name": name,
        "fund_type": classify_fund_type(raw_type, code, name),
        "raw_type": raw_type,
        "latest_nav": metrics.get("latest_nav") or latest.get("nav"),
        "nav_date": latest.get("date", ""),
        "returns": {**metrics.get("returns", {}), **returns},
        "metrics": metrics,
        "nav_history": nav_history,
        "holdings": holdings,
        "source_fee_rate": _percent_to_rate(_extract_string(text, "fund_sourceRate")),
        "purchase_fee_rate": _percent_to_rate(_extract_string(text, "fund_Rate")),
        "min_purchase": _to_float(_extract_string(text, "fund_minsg"), 0.0) or 0.0,
        "data_source": "天天基金 pingzhongdata",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def compute_nav_metrics(nav_history: list[dict[str, Any]]) -> dict[str, Any]:
    if not nav_history:
        return {
            "latest_nav": None,
            "total_return": None,
            "max_drawdown": None,
            "annualized_volatility": None,
            "returns": {},
        }

    df = pd.DataFrame(nav_history)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df.dropna(subset=["date", "nav"]).sort_values("date")
    if df.empty:
        return {
            "latest_nav": None,
            "total_return": None,
            "max_drawdown": None,
            "annualized_volatility": None,
            "returns": {},
        }

    nav = df["nav"]
    latest_nav = float(nav.iloc[-1])
    first_nav = float(nav.iloc[0])
    total_return = (latest_nav / first_nav - 1) * 100 if first_nav else None
    running_max = nav.cummax()
    max_drawdown = float(((nav / running_max) - 1).min() * 100)
    pct = nav.pct_change().dropna()
    if len(pct) >= 2:
        day_diffs = df["date"].diff().dt.days.dropna()
        avg_days = max(float(day_diffs.mean() or 1), 1.0)
        periods_per_year = 365.0 / avg_days
        annualized_volatility = float(pct.std() * math.sqrt(periods_per_year) * 100)
    else:
        annualized_volatility = 0.0

    latest_date = df["date"].iloc[-1]

    def period_return(days: int) -> float | None:
        target = latest_date - timedelta(days=days)
        before = df[df["date"] <= target]
        base = before.iloc[-1] if not before.empty else df.iloc[0]
        base_nav = float(base["nav"])
        if not base_nav:
            return None
        return float((latest_nav / base_nav - 1) * 100)

    latest_year = int(latest_date.year)
    ytd_base = df[df["date"].dt.year == latest_year].iloc[0]
    ytd_return = (latest_nav / float(ytd_base["nav"]) - 1) * 100 if float(ytd_base["nav"]) else None

    returns = {
        "近1月": period_return(30),
        "近3月": period_return(90),
        "近6月": period_return(180),
        "近1年": period_return(365),
        "今年来": float(ytd_return) if ytd_return is not None else None,
    }
    returns = {k: round(v, 2) for k, v in returns.items() if v is not None}

    return {
        "latest_nav": round(latest_nav, 4),
        "total_return": round(total_return, 2) if total_return is not None else None,
        "max_drawdown": round(max_drawdown, 2),
        "annualized_volatility": round(annualized_volatility, 2),
        "returns": returns,
    }


@lru_cache(maxsize=1)
def load_fund_catalog() -> list[dict[str, str]]:
    text = _request_text(FUND_CATALOG_URL, timeout=20)
    match = re.search(r"var\s+r\s*=\s*(\[.*\]);?", text, re.S)
    if not match:
        return []
    try:
        rows = json.loads(match.group(1).rstrip(";"))
    except json.JSONDecodeError:
        return []

    catalog = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 4:
            continue
        code, pinyin, name, raw_type = row[:4]
        try:
            norm_code = normalize_fund_code(code)
        except ValueError:
            continue
        catalog.append(
            {
                "code": norm_code,
                "pinyin": str(pinyin),
                "name": str(name),
                "raw_type": str(raw_type),
                "fund_type": classify_fund_type(str(raw_type), norm_code, str(name)),
            }
        )
    return catalog


def _catalog_map() -> dict[str, dict[str, str]]:
    try:
        return {row["code"]: row for row in load_fund_catalog()}
    except Exception:
        return {}


def fetch_fund_profile(code: str) -> dict[str, Any]:
    code = normalize_fund_code(code)
    try:
        text = _request_text(PINGZHONGDATA_URL.format(code=code), params={"v": int(datetime.now().timestamp())})
        profile = parse_pingzhongdata(text)
    except Exception:
        if not _is_exchange_fund_code(code):
            raise
        profile = {}

    if _is_exchange_fund_code(code):
        quote = fetch_exchange_fund_quote(code)
        if profile:
            merged = {**profile, **{k: v for k, v in quote.items() if v not in (None, "", {})}}
            merged["data_source"] = f"{profile.get('data_source', '')} + 东方财富 push2".strip(" +")
            return merged
        return quote
    return profile


def _is_exchange_fund_code(code: str) -> bool:
    return str(code).startswith(("15", "16", "18", "50", "51", "52", "56", "58"))


def _exchange_secid(code: str) -> str:
    code = normalize_fund_code(code)
    market = "1" if code.startswith(("50", "51", "52", "56", "58")) else "0"
    return f"{market}.{code}"


def _push2_scaled_price(value: Any) -> float | None:
    raw = _to_float(value)
    if raw is None:
        return None
    return raw / 1000.0 if abs(raw) >= 100 else raw


def fetch_exchange_fund_quote(code: str) -> dict[str, Any]:
    code = normalize_fund_code(code)
    params = {
        "secid": _exchange_secid(code),
        "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f116,f117,f152,f169,f170,f171",
    }
    data = requests.get(PUSH2_QUOTE_URL, params=params, headers=_HEADERS, timeout=8).json().get("data") or {}
    name = data.get("f58") or code
    price = _push2_scaled_price(data.get("f43"))
    prev_close = _push2_scaled_price(data.get("f60"))
    change_pct = _to_float(data.get("f170"), 0.0) or 0.0
    if abs(change_pct) > 50:
        change_pct = change_pct / 100.0
    return {
        "code": code,
        "name": name,
        "fund_type": "场内 ETF/LOF",
        "raw_type": "场内基金",
        "latest_nav": price,
        "nav_date": date.today().isoformat(),
        "returns": {"日内": round(change_pct, 2)},
        "metrics": {"latest_nav": price, "previous_close": prev_close},
        "nav_history": [],
        "holdings": [],
        "source_fee_rate": 0.0,
        "purchase_fee_rate": 0.00015,
        "min_purchase": 100.0,
        "amount": _to_float(data.get("f48"), 0.0),
        "market_value": _to_float(data.get("f116"), 0.0),
        "data_source": "东方财富 push2",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def load_exchange_fund_list(limit: int = 60) -> list[dict[str, Any]]:
    params = {
        "pn": 1,
        "pz": max(1, min(int(limit), 200)),
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fs": "b:MK0021,b:MK0022,b:MK0023,b:MK0024",
        "fields": "f2,f3,f4,f5,f6,f12,f13,f14,f17,f18,f20,f21,f23",
    }
    data = requests.get(PUSH2_LIST_URL, params=params, headers=_HEADERS, timeout=8).json().get("data") or {}
    rows = []
    for item in data.get("diff") or []:
        code = str(item.get("f12", ""))
        if not re.fullmatch(r"\d{6}", code):
            continue
        change_pct = _to_float(item.get("f3"), 0.0) or 0.0
        rows.append(
            {
                "code": code,
                "name": item.get("f14") or code,
                "fund_type": "场内 ETF/LOF",
                "raw_type": "场内基金",
                "latest_nav": _to_float(item.get("f2")),
                "nav_date": date.today().isoformat(),
                "returns": {"日内": round(change_pct, 2)},
                "metrics": {"max_drawdown": None, "annualized_volatility": None},
                "purchase_fee_rate": 0.00015,
                "min_purchase": 100.0,
                "amount": _to_float(item.get("f6"), 0.0),
                "market_value": _to_float(item.get("f20"), 0.0),
                "data_source": "东方财富 push2",
            }
        )
    return rows


def _rankhandler_sort_key(horizon: str) -> str:
    return HORIZON_RANK_FIELDS.get(horizon, "1nzf")


def load_ranked_open_funds(horizon: str = "近1年", limit: int = 80) -> list[dict[str, Any]]:
    today = date.today()
    pn = max(1, min(int(limit), 200))
    query = (
        f"op=ph&dt=kf&ft=all&rs=&gs=0&sc={_rankhandler_sort_key(horizon)}&st=desc"
        f"&sd={(today - timedelta(days=365)).isoformat()}&ed={today.isoformat()}"
        f"&qdii=&tabSubtype=,,,,,&pi=1&pn={pn}&dx=1&v={datetime.now().timestamp()}"
    )
    text = _request_text(f"{RANKHANDLER_URL}?{query}", timeout=8)
    segment_match = re.search(r"datas:\[(.*?)\](?:,allRecords|})", text, re.S)
    if not segment_match:
        return []
    rows = []
    for raw in re.findall(r'"([^"]*)"', segment_match.group(1)):
        fields = raw.split(",")
        if len(fields) < 16:
            continue
        try:
            code = normalize_fund_code(fields[0])
        except ValueError:
            continue
        name = fields[1] or code
        raw_type = ""
        returns = {
            "日内": _to_float(fields[6]),
            "近1周": _to_float(fields[7]),
            "近1月": _to_float(fields[8]),
            "近3月": _to_float(fields[9]),
            "近6月": _to_float(fields[10]),
            "近1年": _to_float(fields[11]),
            "近2年": _to_float(fields[12]),
            "近3年": _to_float(fields[13]),
            "今年来": _to_float(fields[14]),
            "成立来": _to_float(fields[15]),
        }
        rows.append(
            {
                "code": code,
                "name": name,
                "fund_type": classify_fund_type(raw_type, code, name),
                "raw_type": raw_type,
                "latest_nav": _to_float(fields[4]),
                "nav_date": fields[3],
                "returns": {k: v for k, v in returns.items() if v is not None},
                "metrics": {"max_drawdown": None, "annualized_volatility": None},
                "source_fee_rate": _percent_to_rate(fields[20] if len(fields) > 20 else 0),
                "purchase_fee_rate": _percent_to_rate(fields[21] if len(fields) > 21 else 0),
                "min_purchase": 10.0,
                "data_source": "东方财富 rankhandler",
            }
        )
    return rows


def _fallback_watchlist(limit: int = 6) -> list[dict[str, Any]]:
    rows = []
    for code in DEFAULT_WATCHLIST[:limit]:
        try:
            rows.append(fetch_fund_profile(code))
        except Exception:
            continue
    return rows


def load_fund_universe(limit: int = 120) -> list[dict[str, Any]]:
    open_rows: list[dict[str, Any]] = []
    exchange_rows: list[dict[str, Any]] = []
    open_limit = max(10, min(80, limit // 2))
    exchange_limit = max(10, min(80, limit - open_limit))
    try:
        open_rows = load_ranked_open_funds(limit=open_limit)
    except Exception:
        open_rows = []
    try:
        exchange_rows = load_exchange_fund_list(limit=exchange_limit)
    except Exception:
        pass

    rows: list[dict[str, Any]] = []
    max_len = max(len(open_rows), len(exchange_rows))
    for idx in range(max_len):
        if idx < len(open_rows):
            rows.append(open_rows[idx])
        if idx < len(exchange_rows):
            rows.append(exchange_rows[idx])
    if not rows:
        rows = _fallback_watchlist()

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = row.get("code")
        if code and code not in deduped:
            deduped[code] = row
    return list(deduped.values())[:limit]


def _matches_query(row: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    q = query.strip().lower()
    return q in str(row.get("code", "")).lower() or q in str(row.get("name", "")).lower()


def _matches_fund_type(row: dict[str, Any], fund_type: str) -> bool:
    if not fund_type or fund_type == "全部":
        return True
    row_type = row.get("fund_type", "")
    if fund_type == "场外开放式":
        return row_type != "场内 ETF/LOF"
    return row_type == fund_type


def _risk_penalty(metrics: dict[str, Any], risk_level: str) -> float:
    drawdown = abs(_to_float(metrics.get("max_drawdown"), 0.0) or 0.0)
    volatility = _to_float(metrics.get("annualized_volatility"), 0.0) or 0.0
    if risk_level == "稳健":
        return max(0.0, drawdown - 8) * 0.8 + max(0.0, volatility - 12) * 0.35
    if risk_level == "进取":
        return max(0.0, drawdown - 25) * 0.25 + max(0.0, volatility - 35) * 0.12
    return max(0.0, drawdown - 15) * 0.45 + max(0.0, volatility - 22) * 0.2


def _candidate_score(row: dict[str, Any], horizon: str, risk_level: str) -> float:
    returns = row.get("returns") or {}
    base = _to_float(returns.get(horizon), None)
    if base is None:
        base = _to_float(returns.get("近1年"), None)
    if base is None:
        base = _to_float(returns.get("日内"), 0.0) or 0.0
    fee = _to_float(row.get("purchase_fee_rate"), 0.0) or 0.0
    liquidity_bonus = 0.5 if (row.get("amount") or 0) and row.get("amount", 0) > 10_000_000 else 0.0
    return round(float(base) - _risk_penalty(row.get("metrics") or {}, risk_level) - fee * 100 + liquidity_bonus, 2)


def screen_funds(
    query: str = "",
    fund_type: str = "全部",
    horizon: str = "近1年",
    risk_level: str = "均衡",
    limit: int = 20,
) -> list[dict[str, Any]]:
    query = (query or "").strip()
    if re.fullmatch(r"\d{6}", query):
        try:
            rows = [fetch_fund_profile(query)]
        except Exception:
            rows = []
    else:
        fetch_limit = max(20, limit * 4)
        if fund_type == "场内 ETF/LOF":
            try:
                rows = load_exchange_fund_list(limit=fetch_limit)
            except Exception:
                rows = []
        elif fund_type not in ("全部", "场内 ETF/LOF"):
            try:
                rows = load_ranked_open_funds(horizon=horizon, limit=fetch_limit)
            except Exception:
                rows = []
        else:
            rows = load_fund_universe(limit=max(20, limit * 2))
        if not rows:
            rows = _fallback_watchlist(limit=limit)

    candidates = [
        row.copy()
        for row in rows
        if _matches_query(row, query) and _matches_fund_type(row, fund_type)
    ]
    for row in candidates:
        row["score"] = _candidate_score(row, horizon, risk_level)
    candidates.sort(key=lambda item: item.get("score", -999), reverse=True)
    return candidates[:limit]
