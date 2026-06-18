from tradingagents.paper_trade import _lot_size, build_signal_order_plan


def test_board_lot_sizes_match_small_account_execution_rules():
    assert _lot_size("688001") == 200
    assert _lot_size("300003") == 100
    assert _lot_size("600519") == 100


def test_exit_signal_plans_full_sellable_position():
    plan = build_signal_order_plan(
        {"action": "EXIT"},
        {"code": "600519", "shares": 800, "sellable": 600},
    )

    assert plan == {
        "kind": "clear",
        "action": "卖出",
        "shares": 600,
        "enabled": True,
        "reason": "平仓信号：卖出全部可卖持仓",
    }


def test_reduce_signal_plans_half_position_in_board_lots():
    plan = build_signal_order_plan(
        {"action": "TAKE_PROFIT"},
        {"code": "688001", "shares": 1000, "sellable": 1000},
    )

    assert plan["kind"] == "reduce"
    assert plan["action"] == "卖出"
    assert plan["shares"] == 400
    assert plan["enabled"]


def test_add_and_hold_signals_do_not_enable_wrong_operations():
    position = {"code": "600519", "shares": 800, "sellable": 800}

    add_plan = build_signal_order_plan({"action": "ADD"}, position)
    hold_plan = build_signal_order_plan({"action": "HOLD"}, position)

    assert add_plan["kind"] == "add"
    assert add_plan["action"] == "买入"
    assert add_plan["shares"] == 200
    assert add_plan["enabled"]
    assert hold_plan["kind"] == "hold"
    assert not hold_plan["enabled"]


def test_t1_locked_exit_signal_is_not_executable():
    plan = build_signal_order_plan(
        {"action": "STOP_LOSS"},
        {"code": "600519", "shares": 800, "sellable": 0},
    )

    assert plan["kind"] == "clear"
    assert not plan["enabled"]
    assert "T+1" in plan["reason"]
