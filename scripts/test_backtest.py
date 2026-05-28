#!/usr/bin/env python3
"""回测逻辑 bug 测试"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import backtest
from strategy import generate_signal
from config import get_config


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

    print("\nDone.")
