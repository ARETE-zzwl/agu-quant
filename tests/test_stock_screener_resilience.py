from __future__ import annotations

import requests

from tradingagents.dataflows import a_stock


class FakePush2Response:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_screen_stocks_retries_transient_remote_disconnect(monkeypatch):
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.exceptions.ConnectionError("remote end closed connection without response")
        return FakePush2Response(
            {
                "data": {
                    "total": 1,
                    "diff": [
                        {
                            "f12": "000001",
                            "f14": "平安银行",
                            "f2": 10.0,
                            "f3": 1.2,
                            "f4": 0.12,
                            "f5": 1000,
                            "f6": 1_000_000,
                            "f7": 2.3,
                            "f8": 1.1,
                            "f9": 8.5,
                            "f10": 1.0,
                            "f15": 10.2,
                            "f16": 9.8,
                            "f17": 9.9,
                            "f18": 9.88,
                            "f20": 100_000_000,
                            "f21": 90_000_000,
                            "f23": 0.9,
                            "f37": 12.0,
                            "f62": 500_000,
                        }
                    ],
                }
            }
        )

    monkeypatch.setattr(a_stock._requests, "get", fake_get)

    stocks, total = a_stock.screen_stocks(page_size=10)

    assert calls["count"] == 2
    assert total == 1
    assert stocks[0]["code"] == "000001"
    assert stocks[0]["name"] == "平安银行"


def test_screen_stocks_returns_empty_when_push2_is_unavailable(monkeypatch):
    def fake_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("remote end closed connection without response")

    monkeypatch.setattr(a_stock._requests, "get", fake_get)

    stocks, total = a_stock.screen_stocks(page_size=10)

    assert stocks == []
    assert total == 0
