#!/usr/bin/env python3
"""ATR趋势回测 — BTC/ETH 2022-2026 — 支持EMA/SMA + 分币种参数"""

import os, sys, json, math
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_engine import fetch_daily_full, SYMBOLS
from indicators import atr, ema, sma
from config import get_config, BACKTEST


def backtest(data, cfg, verbose=False):
    n = len(data)
    ma_p = cfg["ma_period"]
    if n < ma_p + 14:
        return None

    if cfg.get("ma_type") == "ema":
        ma_vals = ema(data, ma_p)
    else:
        ma_vals = sma(data, ma_p)

    a = atr(data, cfg["atr_period"])

    cash = cfg["initial_capital"]
    position = 0
    entry_price = 0
    highest = 0
    entry_date = ""
    equity = [cash]
    trades = []

    fee_mult = 1 - cfg["fee_rate"]

    for i in range(ma_p, n):
        p = data[i]["c"]
        atr_val = a[i] if a[i] else p * 0.03
        ma_val = ma_vals[i] if ma_vals[i] else p

        if position > 0:
            highest = max(highest, data[i]["h"])
            trail_stop = highest - cfg["trail_atr_mult"] * atr_val

            exit_signal = False
            exit_reasons = []
            if p < ma_val:
                exit_signal = True
                exit_reasons.append(f"跌破{cfg['ma_type'].upper()}{ma_p}")
            if p < trail_stop:
                exit_signal = True
                exit_reasons.append("跌破跟踪止损")

            if exit_signal:
                profit = (p - entry_price) / entry_price * 100
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": data[i]["date_str"],
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(p, 2),
                    "profit_pct": round(profit, 2),
                    "reason": "; ".join(exit_reasons),
                })
                cash = position * p * fee_mult
                position = 0
                entry_date = ""
        elif p > ma_val + cfg["buy_atr_mult"] * atr_val:
            vol_ok = True
            if i >= cfg["vol_lookback"]:
                avg_vol = sum(d["v"] for d in data[i - cfg["vol_lookback"]:i]) / cfg["vol_lookback"]
                if data[i]["v"] < avg_vol * cfg["vol_threshold"]:
                    vol_ok = False
            if vol_ok:
                position = (cash * fee_mult) / p
                entry_price = p
                highest = data[i]["h"]
                entry_date = data[i]["date_str"]
                cash = 0

        if position > 0:
            equity.append(position * p)
        else:
            equity.append(cash)

    if position > 0:
        profit = (data[-1]["c"] - entry_price) / entry_price * 100
        trades.append({
            "entry_date": entry_date,
            "exit_date": data[-1]["date_str"] + "(强平)",
            "entry_price": round(entry_price, 2),
            "exit_price": round(data[-1]["c"], 2),
            "profit_pct": round(profit, 2),
            "reason": "回测结束强平",
        })
        cash = position * data[-1]["c"] * fee_mult
        equity[-1] = cash

    total_ret = (equity[-1] / equity[0] - 1) * 100
    peak = equity[0]
    max_dd = 0
    for v in equity:
        if v > peak:
            peak = v
        dd = (v - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd

    years = len(data) / 365
    annual_ret = ((equity[-1] / equity[0]) ** (1 / max(years, 0.5)) - 1) * 100 if equity[-1] > 0 else 0
    daily_r = [(equity[i] / equity[i - 1] - 1) for i in range(2, len(equity)) if equity[i - 1] > 0]
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
        "trades_list": trades,
        "equity_curve": equity,
    }

    if verbose and trades:
        print(f"\n  📋 交易明细 ({len(trades)}笔):")
        print(f"  {'入场':>10} {'出场':>10} {'入场价':>8} {'出场价':>8} {'盈亏':>8} {'原因'}")
        print(f"  {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*20}")
        for t in trades:
            print(f"  {t['entry_date']:>10} {t['exit_date']:>10} ${t['entry_price']:>7.1f} ${t['exit_price']:>7.1f} {t['profit_pct']:>+7.2f}%  {t['reason']}")

    return result


def main():
    print("=" * 80)
    print("ATR趋势跟踪 — 完整回测")
    print("=" * 80)

    for name, sym in SYMBOLS.items():
        cfg = get_config(name)
        ma_label = f"{cfg['ma_type'].upper()}{cfg['ma_period']}"
        print(f"\n[{name}] {ma_label}  buy={cfg['buy_atr_mult']} trail={cfg['trail_atr_mult']}  fee={cfg['fee_rate']*100:.1f}%")
        print(f"  获取全量数据...")
        data = fetch_daily_full(sym)
        if not data:
            print("  ❌ 获取失败")
            continue

        today = datetime.now().strftime("%Y-%m-%d")
        d4y = [d for d in data if BACKTEST["start_date"] <= d["date_str"] <= today]
        print(f"  数据: {d4y[0]['date_str']} ~ {d4y[-1]['date_str']} ({len(d4y)}天)")

        r = backtest(d4y, cfg, verbose=True)
        if not r:
            print("  ❌ 回测失败")
            continue

        print(f"\n  {'指标':<16} {'数值':>10}")
        print(f"  {'-'*16} {'-'*10}")
        for k, v in r.items():
            if k in ("trades_list", "equity_curve"):
                continue
            if isinstance(v, float):
                print(f"  {k:<16} {v:>+9.1f}%")
            else:
                print(f"  {k:<16} {v:>10}")
        years = (datetime.strptime(d4y[-1]["date_str"], "%Y-%m-%d") - datetime.strptime(d4y[0]["date_str"], "%Y-%m-%d")).days / 365.25
        if years > 0:
            print(f"  年交易: {r['trades']/years:.0f}笔")
        if r.get('avg_loss') and r['avg_loss'] != 0:
            print(f"  盈亏比: {r['avg_win']/abs(r['avg_loss']):.1f}")


if __name__ == "__main__":
    main()
