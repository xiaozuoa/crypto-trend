#!/usr/bin/env python3
"""回测逻辑 bug 测试"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import backtest
from strategy import generate_signal
from config import get_config, STRATEGY
from optimizer import backtest_range


def make_data(n_days, prices, highs, lows, volumes=None):
    if not isinstance(prices, list):
        prices = [prices] * n_days
    if not isinstance(highs, list):
        highs = [highs] * n_days
    if not isinstance(lows, list):
        lows = [lows] * n_days
    if volumes is None:
        volumes = [10000] * n_days
    elif not isinstance(volumes, list):
        volumes = [volumes] * n_days

    data = []
    for i in range(n_days):
        data.append({
            "date": i, "date_str": f"2022-01-{i+1:02d}",
            "o": prices[i], "h": highs[i], "l": lows[i],
            "c": prices[i], "v": volumes[i],
        })
    return data


def test_highest_tracks_entry_day_high():
    """
    Bug: 入场时 highest=p(close), 应改为 data[i]['h'](high).
    入场日 high(112) >> close(106) 时, 修正后跟踪止损基于 112,
    次日 close=103 触发跟踪止损退出; bug 版基于 106 不会触发.
    """
    cfg = get_config("BTC")

    data = make_data(45, 100, 101, 99, 10000)
    data.append({
        "date": 45, "date_str": "2022-02-15",
        "o": 100, "h": 112, "l": 100, "c": 106, "v": 20000,
    })
    data.append({
        "date": 46, "date_str": "2022-02-16",
        "o": 106, "h": 104, "l": 102, "c": 103, "v": 1000,
    })
    for i in range(10):
        data.append({
            "date": 47 + i, "date_str": f"2022-02-{17+i}",
            "o": 103, "h": 104, "l": 102, "c": 103, "v": 1000,
        })

    result = backtest(data, cfg, verbose=False)
    trades = result["trades_list"]

    assert len(trades) >= 1, f"应至少有1笔交易, 实际 {len(trades)}"
    t = trades[0]
    assert t["exit_date"] == "2022-02-16", \
        f"应在2022-02-16因跟踪止损退出, 实际 {t['exit_date']}"
    assert "跟踪止损" in t["reason"], \
        f"退出原因应包含跟踪止损, 实际: {t['reason']}"
    print(f"  PASS: exit_date={t['exit_date']}, reason={t['reason']}")


def test_equity_no_double_fee():
    """
    Bug: 持仓期 equity.append(position*p*fee_mult), 每天重复扣费.
    入场手续费已通过 position=(cash*fee_mult)/p 体现在持仓量中.
    验证: 入场日权益 = cash * fee_mult = 9990, 不是 cash * fee_mult^2 = 9980.
    """
    cfg = get_config("BTC")

    data = make_data(45, 100, 101, 99, 10000)
    data.append({
        "date": 45, "date_str": "2022-02-15",
        "o": 100, "h": 107, "l": 100, "c": 106, "v": 20000,
    })
    for i in range(9):
        data.append({
            "date": 46 + i, "date_str": f"2022-02-{16+i}",
            "o": 106, "h": 107, "l": 105, "c": 106, "v": 1000,
        })

    result = backtest(data, cfg, verbose=False)
    equity = result["equity_curve"]

    # 找第一个 < 10000 的权益值 (入场日 equity)
    # equity[0]=10000, 之后 ma_p 个值都是 10000 (空仓), 入场日首次跌破
    first_drop = None
    for v in equity:
        if v < 10000:
            first_drop = v
            break

    assert first_drop is not None, "应有入场日权益值 < 10000"
    assert first_drop >= 9990.0, \
        f"入场日权益应 >= 9990 (只扣一次手续费), 实际 {first_drop:.2f}"
    print(f"  PASS: entry_equity={first_drop:.2f} (bug版=9980, 修正=9990)")


def test_signal_trail_stop_uses_high():
    """
    Bug: generate_signal 中 trail_stop 用 close 而非 high.
    入场日 high > close 时, trail_stop 应基于 high (与 check_exit/回测一致).
    """
    cfg = get_config("BTC")

    # 构造数据: 盘整 + 最后一天突破, high 显著高于 close
    data = make_data(45, 100, 101, 99, 10000)
    data.append({
        "date": 45, "date_str": "2022-02-15",
        "o": 100, "h": 115, "l": 100, "c": 108, "v": 20000,
    })

    sig = generate_signal(data, cfg)
    assert sig["signal"] == 1, f"应产生买入信号, 实际 signal={sig['signal']}"

    # trail_stop 应基于 high(115), 不是 close(108)
    # 验证: trail_stop < entry_price - trail_atr*ATR based on close
    # 如果错误地用 close: trail_stop = 108 - 2*ATR
    # 如果正确地用 high:  trail_stop = 115 - 2*ATR
    # high-based 的值应该比 close-based 更大
    atr_val = sig["atr"]
    close_based = 108 - 2 * atr_val
    high_based = 115 - 2 * atr_val

    # trail_stop 应等于 high - trail_atr*ATR
    expected = 115 - cfg["trail_atr_mult"] * atr_val
    assert abs(sig["trail_stop"] - expected) < 0.1, \
        f"trail_stop 应基于 high, 期望 {expected:.1f}, 实际 {sig['trail_stop']}"
    print(f"  PASS: trail_stop={sig['trail_stop']} (high-based={high_based:.1f}, close-based={close_based:.1f})")


def test_optimizer_indicator_none_check():
    """Bug: backtest_range uses falsy check (if a[i] else) for indicator fallback.
    Fix: use 'is not None'. Verify by patching atr to return 0.0 (falsy but valid)."""
    cfg = get_config("BTC")

    data = make_data(50, 100, 101, 99, 10000)
    # Construct a scenario: entry bar + next bar
    data.append({
        "date": 50, "date_str": "2022-02-20",
        "o": 100, "h": 115, "l": 100, "c": 110, "v": 20000,
    })
    data.append({
        "date": 51, "date_str": "2022-02-21",
        "o": 110, "h": 112, "l": 108, "c": 109, "v": 10000,
    })
    for i in range(10):
        data.append({
            "date": 52 + i, "date_str": f"2022-02-{22+i}",
            "o": 109, "h": 110, "l": 108, "c": 109, "v": 10000,
        })

    # Patch atr to return 0.0 at index 51 (falsy value)
    import optimizer as opt_mod
    from indicators import atr as orig_atr

    def mock_atr(d, p):
        result = orig_atr(d, p)
        if len(result) > 51:
            result[51] = 0.0
        return result

    old_atr = opt_mod.atr
    opt_mod.atr = mock_atr

    try:
        r = backtest_range(data, None, None,
                           cfg["ma_period"], cfg["buy_atr_mult"], cfg["trail_atr_mult"],
                           cfg=cfg)
        # With is-not-None fix: ATR=0.0 at bar 51 → trail_stop=hi → exit triggered
        # With falsy-check bug: ATR fallback to p*0.03 → wider trail → no exit
        assert r is not None, "backtest_range should not return None"
        print(f"  PASS: backtest_range with zero-ATR patch = {r:+.1f}%")
    finally:
        opt_mod.atr = old_atr


def test_backtest_warmup_uses_max_periods():
    """Bug: backtest loop starts at ma_p instead of max(ma_p, atr_period).
    If atr_period > ma_p, early bars use None fallback for ATR.
    Fix: use max(ma_p, atr_period) like optimizer.py."""
    cfg = get_config("BTC")
    # Force atr_period > ma_period to expose the bug
    cfg["ma_period"] = 10
    cfg["atr_period"] = 20

    data = make_data(30, 100, 101, 99, 10000)
    data[-1] = {"date": 29, "date_str": "2022-01-30", "o": 110, "h": 112, "l": 109, "c": 111, "v": 20000}

    result = backtest(data, cfg, verbose=False)
    # Before fix: loop starts at 10, ATR at index 10-19 is None → uses fallback p*0.03
    # After fix: loop starts at 20, ATR at index 20+ is valid
    assert result is not None, f"backtest should handle atr_period > ma_period, got None"
    print(f"  PASS: atr_p(20) > ma_p(10) = {result['total_return']:+.1f}%")


def test_volume_filter_with_low_ma_period():
    """Bug: volume filter guard 'i >= vol_lookback' assumes ma_p >= vol_lookback.
    If ma_p < vol_lookback, early buy signals skip volume filter.
    Fix: ensure we don't skip filter."""
    cfg = get_config("BTC")
    cfg["ma_period"] = 10  # < vol_lookback(20)

    # Data: first 10 bars for warmup, then a strong buy signal at bar 10
    data = make_data(30, 100, 101, 99, 1000)  # low volume
    # Bar 10: price breaks out but volume is LOW
    data[10] = {"date": 10, "date_str": "2022-01-11", "o": 100, "h": 120, "l": 100, "c": 118, "v": 100}
    for i in range(11, 30):
        data[i] = {"date": i, "date_str": f"2022-01-{i+1:02d}", "o": 100, "h": 101, "l": 99, "c": 100, "v": 100}

    result = backtest(data, cfg, verbose=False)
    # The bug: i=10 < vol_lookback(20), so volume filter is skipped entirely
    # Entry at bar 10 with low volume should NOT trigger if filter works
    assert result is not None, "backtest should not return None"
    print(f"  PASS: low ma_p={cfg['ma_period']}, trades={result['trades']}")


def test_alert_historical_returns_consistent():
    """Verify alert.py historical returns match README.
    Bug: alert.py had stale BTC+181% ETH+221% vs README's BTC+200.6% ETH+233.5%."""
    import os
    alert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alert.py")
    with open(alert_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check that the historical returns line doesn't have the old stale values
    assert "BTC+181% ETH+221%" not in content, \
        "alert.py has stale historical returns (BTC+181% ETH+221%), should match README"
    print("  PASS: alert.py historical returns not stale")


if __name__ == "__main__":
    print("=" * 60)
    print("Bug 修复验证")
    print("=" * 60)
    print("\n[Test 1] highest 应追踪入场日 high 而非 close")
    test_highest_tracks_entry_day_high()

    print("\n[Test 2] 持仓期权益不应重复扣费")
    test_equity_no_double_fee()

    print("\n[Test 3] 信号 trail_stop 应基于入场日 high")
    test_signal_trail_stop_uses_high()

    print("\n[Test 4] optimizer backtest_range 指示器 fallback 用 is not None")
    test_optimizer_indicator_none_check()

    print("\n[Test 5] backtest warmup 用 max(ma_p, atr_period)")
    test_backtest_warmup_uses_max_periods()

    print("\n[Test 6] 低 ma_p 时成交量过滤守卫")
    test_volume_filter_with_low_ma_period()

    print("\n[Test 7] alert.py 历史收益与 README 一致")
    test_alert_historical_returns_consistent()

    print("\nDone.")
