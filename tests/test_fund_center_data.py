from __future__ import annotations

import pytest

from tradingagents.fund_center import (
    classify_fund_type,
    compute_nav_metrics,
    normalize_fund_code,
    parse_pingzhongdata,
    screen_funds,
)


PINGZHONG_SAMPLE = """
var fS_name = "易方达优质精选混合(QDII)";
var fS_code = "110011";
var fund_sourceRate="1.50";
var fund_Rate="0.15";
var fund_minsg="10";
var syl_1n="-12.44";
var syl_6y="-20.92";
var syl_3y="-16.29";
var syl_1y="-6.64";
var stockCodesNew =["1.600519","0.000858"];
var Data_netWorthTrend = [
  {"x":1704067200000,"y":1.0000,"equityReturn":0,"unitMoney":""},
  {"x":1706745600000,"y":1.0500,"equityReturn":5,"unitMoney":""},
  {"x":1709251200000,"y":1.0200,"equityReturn":-2.86,"unitMoney":""},
  {"x":1711929600000,"y":1.1200,"equityReturn":9.8,"unitMoney":""}
];
"""


def test_normalize_fund_code_accepts_only_six_digits():
    assert normalize_fund_code(" 110011 ") == "110011"

    with pytest.raises(ValueError):
        normalize_fund_code("110011.js")

    with pytest.raises(ValueError):
        normalize_fund_code("基金110011")


def test_parse_pingzhongdata_extracts_profile_and_nav_history():
    profile = parse_pingzhongdata(PINGZHONG_SAMPLE)

    assert profile["code"] == "110011"
    assert profile["name"] == "易方达优质精选混合(QDII)"
    assert profile["fund_type"] == "QDII"
    assert profile["purchase_fee_rate"] == 0.0015
    assert profile["source_fee_rate"] == 0.015
    assert profile["min_purchase"] == 10.0
    assert profile["returns"]["近1年"] == -12.44
    assert profile["returns"]["近6月"] == -20.92
    assert profile["holdings"] == ["600519", "000858"]
    assert profile["nav_history"][-1]["nav"] == 1.12


def test_compute_nav_metrics_calculates_return_drawdown_and_volatility():
    nav_history = [
        {"date": "2024-01-01", "nav": 1.0},
        {"date": "2024-02-01", "nav": 1.2},
        {"date": "2024-03-01", "nav": 0.9},
        {"date": "2024-04-01", "nav": 1.1},
    ]

    metrics = compute_nav_metrics(nav_history)

    assert metrics["latest_nav"] == 1.1
    assert metrics["total_return"] == pytest.approx(10.0)
    assert metrics["max_drawdown"] == pytest.approx(-25.0)
    assert metrics["annualized_volatility"] > 0


def test_classify_fund_type_uses_code_name_and_raw_type():
    assert classify_fund_type("混合型-偏股", "001480", "财通成长优选混合A") == "混合型"
    assert classify_fund_type("股票型", "006502", "财通集成电路产业股票A") == "股票型"
    assert classify_fund_type("", "510300", "沪深300ETF") == "场内 ETF/LOF"
    assert classify_fund_type("", "110011", "易方达优质精选混合(QDII)") == "QDII"


def test_screen_funds_filters_type_and_sorts_by_horizon(monkeypatch):
    rows = [
        {
            "code": "110011",
            "name": "易方达优质精选混合",
            "fund_type": "混合型",
            "latest_nav": 1.2,
            "nav_date": "2024-04-01",
            "returns": {"近1月": 2.0, "近6月": 8.0, "近1年": 15.0},
            "metrics": {"max_drawdown": -12.0, "annualized_volatility": 18.0},
            "data_source": "fixture",
        },
        {
            "code": "510300",
            "name": "沪深300ETF",
            "fund_type": "场内 ETF/LOF",
            "latest_nav": 4.2,
            "nav_date": "2024-04-01",
            "returns": {"近1月": 4.0, "近6月": 3.0, "近1年": 6.0},
            "metrics": {"max_drawdown": -8.0, "annualized_volatility": 12.0},
            "data_source": "fixture",
        },
    ]

    monkeypatch.setattr("tradingagents.fund_center.load_ranked_open_funds", lambda horizon="近1年", limit=120: rows)
    monkeypatch.setattr("tradingagents.fund_center.load_exchange_fund_list", lambda limit=120: rows)

    result = screen_funds(query="", fund_type="场外开放式", horizon="近1年", risk_level="均衡", limit=5)

    assert [row["code"] for row in result] == ["110011"]
    assert result[0]["score"] > 0
