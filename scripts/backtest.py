#!/usr/bin/env python3
"""ATR趋势回测 — BTC/ETH 2022-2026 完整验证"""

import os, sys, json, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_engine import fetch_daily_full, SYMBOLS
from indicators import atr


def backtest(data):
    """ATR趋势回测"""
    n = len(data)
    if n < 60:
        return None

    a = atr(data, 14)
    ma50 = [None] * n
    for i in range(49, n):
        ma50[i] = sum(d["c"] for d in data[i - 49:i + 1]) / 50

    cash = 10000
    position = 0
    entry_price = 0
    highest = 0
    equity = [cash]
    trades = []

    for i in range(50, n):
        p = data[i]["c"]
        atr_val = a[i] if a[i] else p * 0.03
        ma = ma50[i] if ma50[i] else p

        if position > 0:
            highest = max(highest, p)
            trail_stop = highest - 3 * atr_val

            exit_signal = False
            if p < ma: exit_signal = True
            if p < trail_stop: exit_signal = True

            if exit_signal:
                profit = (p - entry_price) / entry_price * 100
                trades.append(profit)
                cash = position * p * 0.999
                position = 0
        else:
            buy_trigger = ma + 2 * atr_val
            vol_ok = True
            if i >= 20:
                avg_vol = sum(d["v"] for d in data[i - 19:i + 1]) / 20
                if data[i]["v"] < avg_vol * 1.2:
                    vol_ok = False
            if p > buy_trigger and vol_ok:
                position = (cash * 0.999) / p
                entry_price = p
                highest = p
                cash = 0

        if position > 0:
            equity.append(position * p * 0.999)
        else:
            equity.append(cash)

    if position > 0:
        cash = position * data[-1]["c"] * 0.999
        equity[-1] = cash

    total_ret = (equity[-1] / equity[0] - 1) * 100
    peak = equity[0]
    max_dd = 0
    for v in equity:
        dd = (v - peak) / peak * 100
        if v > peak: peak = v; dd = 0
        if dd < max_dd: max_dd = dd

    years = len(data) / 365
    annual_ret = ((equity[-1] / equity[0]) ** (1 / max(years, 0.5)) - 1) * 100 if equity[-1] > 0 else 0
    daily_r = [(equity[i] / equity[i - 1] - 1) for i in range(1, len(equity)) if equity[i - 1] > 0]
    if daily_r:
        avg = sum(daily_r) / len(daily_r)
        std = (sum((r - avg) ** 2 for r in daily_r) / len(daily_r)) ** 0.5
        sharpe = (avg / std * (365 ** 0.5)) if std > 0 else 0
    else:
        sharpe = 0

    win_rate = sum(1 for t in trades if t > 0) / max(len(trades), 1) * 100
    avg_win = sum(t for t in trades if t > 0) / max(sum(1 for t in trades if t > 0), 1)
    avg_loss = sum(t for t in trades if t < 0) / max(sum(1 for t in trades if t < 0), 1)

    bh = (data[-1]["c"] / data[0]["c"] - 1) * 100

    return {
        "total_return": round(total_ret, 1),
        "annual_return": round(annual_ret, 1),
        "max_drawdown": round(max_dd, 1),
        "sharpe": round(sharpe, 2),
        "trades": len(trades),
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 1) if avg_win else 0,
        "avg_loss": round(avg_loss, 1) if avg_loss else 0,
        "buy_hold": round(bh, 1),
        "excess": round(total_ret - bh, 1),
    }


def main():
    print("=" * 80)
    print("ATR趋势跟踪 — 完整回测")
    print("=" * 80)

    for name, sym in SYMBOLS.items():
        print(f"\n[{name}] 获取全量数据...")
        data = fetch_daily_full(sym)
        if not data:
            print("  ❌ 获取失败")
            continue

        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        d4y = [d for d in data if "2022-01-01" <= d["date_str"] <= today]
        print(f"  数据: {d4y[0]['date_str']} ~ {d4y[-1]['date_str']} ({len(d4y)}天)")

        r = backtest(d4y)
        if not r:
            print("  ❌ 回测失败")
            continue

        print(f"  {'指标':<16} {'数值':>10}")
        print(f"  {'-'*16} {'-'*10}")
        for k, v in r.items():
            if isinstance(v, float):
                print(f"  {k:<16} {v:>+9.1f}%")
            else:
                print(f"  {k:<16} {v:>10}")
        print(f"  年交易: {r['trades']/4.5:.0f}笔")
        print(f"  盈亏比: {r['avg_win']/abs(r['avg_loss']):.1f}" if r.get('avg_loss') and r['avg_loss'] != 0 else "")


if __name__ == "__main__":
    main()
