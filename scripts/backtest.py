#!/usr/bin/env python3
"""ATR趋势回测 — BTC/ETH 2022-2026 完整验证"""

import os, sys, json, math
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_engine import fetch_daily_full, SYMBOLS
from indicators import atr
from config import STRATEGY as CFG, BACKTEST


def backtest(data, verbose=False):
    n = len(data)
    if n < 60:
        return None

    ma = CFG["ma_period"]
    a = atr(data, CFG["atr_period"])

    ma_vals = [None] * n
    for i in range(ma - 1, n):
        ma_vals[i] = sum(d["c"] for d in data[i - ma + 1:i + 1]) / ma

    cash = CFG["initial_capital"]
    position = 0
    entry_price = 0
    highest = 0
    entry_date = ""
    equity = [cash]
    trades = []

    fee_mult = 1 - CFG["fee_rate"]
    buy_atr = CFG["buy_atr_mult"]
    trail_atr = CFG["trail_atr_mult"]
    vol_lb = CFG["vol_lookback"]
    vol_th = CFG["vol_threshold"]

    for i in range(ma, n):
        p = data[i]["c"]
        atr_val = a[i] if a[i] else p * 0.03
        ma_val = ma_vals[i] if ma_vals[i] else p

        if position > 0:
            highest = max(highest, p)
            trail_stop = highest - trail_atr * atr_val

            exit_signal = False
            exit_reason = ""
            if p < ma_val:
                exit_signal = True
                exit_reason = f"跌破MA{ma}"
            if p < trail_stop:
                exit_signal = True
                exit_reason = f"跌破跟踪止损"

            if exit_signal:
                profit = (p - entry_price) / entry_price * 100
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": data[i]["date_str"],
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(p, 2),
                    "profit_pct": round(profit, 2),
                    "reason": exit_reason,
                    "bars": i - [j for j, d in enumerate(data) if d["date_str"] == entry_date][0] if entry_date else 0,
                })
                cash = position * p * fee_mult
                position = 0
                entry_date = ""
        else:
            buy_trigger = ma_val + buy_atr * atr_val
            vol_ok = True
            if i >= vol_lb:
                avg_vol = sum(d["v"] for d in data[i - vol_lb + 1:i + 1]) / vol_lb
                if data[i]["v"] < avg_vol * vol_th:
                    vol_ok = False
            if p > buy_trigger and vol_ok:
                position = (cash * fee_mult) / p
                entry_price = p
                highest = p
                entry_date = data[i]["date_str"]
                cash = 0

        if position > 0:
            equity.append(position * p * fee_mult)
        else:
            equity.append(cash)

    if position > 0:
        cash = position * data[-1]["c"] * fee_mult
        equity[-1] = cash
        trades[-1]["exit_date"] = data[-1]["date_str"] + "(强平)"
        trades[-1]["exit_price"] = round(data[-1]["c"], 2)
        trades[-1]["profit_pct"] = round((data[-1]["c"] - entry_price) / entry_price * 100, 2)

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

    win_rate = sum(1 for t in trades if t["profit_pct"] > 0) / max(len(trades), 1) * 100
    avg_win = sum(t["profit_pct"] for t in trades if t["profit_pct"] > 0) / max(sum(1 for t in trades if t["profit_pct"] > 0), 1)
    avg_loss = sum(t["profit_pct"] for t in trades if t["profit_pct"] < 0) / max(sum(1 for t in trades if t["profit_pct"] < 0), 1)

    bh = (data[-1]["c"] / data[0]["c"] - 1) * 100

    result = {
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

    if verbose and trades:
        print(f"\n  📋 交易明细 ({len(trades)}笔):")
        print(f"  {'入场':>10} {'出场':>10} {'入场价':>8} {'出场价':>8} {'盈亏':>8} {'持仓天':>6} {'原因'}")
        print(f"  {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*20}")
        for t in trades:
            print(f"  {t['entry_date']:>10} {t['exit_date']:>10} ${t['entry_price']:>7.1f} ${t['exit_price']:>7.1f} {t['profit_pct']:>+7.2f}% {t['bars']:>5}d  {t['reason']}")

    return result


def main():
    print("=" * 80)
    print("ATR趋势跟踪 — 完整回测")
    print(f"  参数: MA{CFG['ma_period']} + {CFG['buy_atr_mult']}×ATR买入, 跌破MA{CFG['ma_period']}或{CFG['trail_atr_mult']}×ATR跟踪止损卖出")
    print(f"  手续费: {CFG['fee_rate']*100:.1f}%  成交量确认: {CFG['vol_threshold']}×{CFG['vol_lookback']}日均量")
    print("=" * 80)

    for name, sym in SYMBOLS.items():
        print(f"\n[{name}] 获取全量数据...")
        data = fetch_daily_full(sym)
        if not data:
            print("  ❌ 获取失败")
            continue

        today = datetime.now().strftime("%Y-%m-%d")
        d4y = [d for d in data if BACKTEST["start_date"] <= d["date_str"] <= today]
        print(f"  数据: {d4y[0]['date_str']} ~ {d4y[-1]['date_str']} ({len(d4y)}天)")

        r = backtest(d4y, verbose=True)
        if not r:
            print("  ❌ 回测失败")
            continue

        print(f"\n  {'指标':<16} {'数值':>10}")
        print(f"  {'-'*16} {'-'*10}")
        for k, v in r.items():
            if isinstance(v, float):
                print(f"  {k:<16} {v:>+9.1f}%")
            else:
                print(f"  {k:<16} {v:>10}")
        years = (datetime.strptime(d4y[-1]["date_str"], "%Y-%m-%d") - datetime.strptime(d4y[0]["date_str"], "%Y-%m-%d")).days / 365.25
        if years > 0:
            print(f"  年交易: {r['trades']/years:.0f}笔")
        print(f"  盈亏比: {r['avg_win']/abs(r['avg_loss']):.1f}" if r.get('avg_loss') and r['avg_loss'] != 0 else "")


if __name__ == "__main__":
    main()
