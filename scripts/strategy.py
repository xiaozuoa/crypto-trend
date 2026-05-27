#!/usr/bin/env python3
"""ATR趋势跟踪策略 — 日线, BTC/ETH, 无杠杆"""

import os, sys, json, math
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_engine import fetch_daily, SYMBOLS
from indicators import atr

WORKSPACE = os.path.expanduser("~/.crypto-trend/workspace")
os.makedirs(WORKSPACE, exist_ok=True)


def generate_signal(data):
    n = len(data)
    if n < 50:
        return {"signal": 0, "reason": "数据不足"}

    ma50_vals = []
    for i in range(49, n):
        ma50_vals.append(sum(d["c"] for d in data[i - 49:i + 1]) / 50)

    a = atr(data, 14)
    current = data[-1]
    current_ma50 = ma50_vals[-1] if ma50_vals else current["c"]
    current_atr = a[-1] if a[-1] else current["c"] * 0.03

    buy_trigger = current_ma50 + 2 * current_atr
    price_ok = current["c"] > buy_trigger

    vol_ok = True
    if len(data) >= 20:
        avg_vol = sum(d["v"] for d in data[-20:]) / 20
        if data[-1]["v"] < avg_vol * 1.2:
            vol_ok = False

    if price_ok and vol_ok:
        stop_loss = current_ma50
        trail_stop = current["c"] - 3 * current_atr
        return {
            "signal": 1,
            "action": "buy",
            "entry_price": round(current["c"], 2),
            "stop_loss": round(stop_loss, 2),
            "trail_stop": round(trail_stop, 2),
            "atr": round(current_atr, 2),
            "atr_pct": round(current_atr / current["c"] * 100, 2),
            "ma50": round(current_ma50, 2),
            "date": current["date_str"],
            "vol_ok": vol_ok,
        }

    return {
        "signal": 0,
        "action": "wait",
        "price": round(current["c"], 2),
        "ma50": round(current_ma50, 2),
        "buy_trigger": round(buy_trigger, 2),
        "atr": round(current_atr, 2),
        "date": current["date_str"],
        "vol_ok": vol_ok,
    }


def check_exit(data, entry_price, entry_date=None):
    """检查是否该卖出, entry_date用于计算入场以来最高价(而非仅最近50天)"""
    n = len(data)
    if n < 50:
        return {"exit": False, "reason": "数据不足"}

    closes = [d["c"] for d in data[-50:]]
    ma50 = sum(closes) / 50
    a = atr(data, 14)
    current_atr = a[-1] if a[-1] else data[-1]["c"] * 0.03
    current = data[-1]

    if entry_date:
        highest = max(d["h"] for d in data if d["date_str"] >= entry_date)
    else:
        highest = max(d["h"] for d in data[-50:])

    trail_stop = highest - 3 * current_atr

    reasons = []
    if current["c"] < ma50:
        reasons.append(f"跌破MA50 ({current['c']:.1f} < {ma50:.1f})")
    if current["c"] < trail_stop:
        reasons.append(f"跌破跟踪止损 ({current['c']:.1f} < {trail_stop:.1f})")

    if reasons:
        profit_pct = (current["c"] - entry_price) / entry_price * 100
        return {
            "exit": True,
            "reason": "; ".join(reasons),
            "exit_price": round(current["c"], 2),
            "profit_pct": round(profit_pct, 2),
            "date": current["date_str"],
        }

    return {
        "exit": False,
        "trail_stop": round(trail_stop, 2),
        "ma50": round(ma50, 2),
        "current": round(current["c"], 2),
        "date": current["date_str"],
    }


def run():
    results = {}
    for name, sym in SYMBOLS.items():
        data = fetch_daily(sym, 200)
        if len(data) < 60:
            results[name] = {"error": f"数据不足({len(data)}条)"}
            continue

        pos_file = os.path.join(WORKSPACE, f"position_{name}.json")
        has_position = False
        entry_price = 0
        entry_date = None
        if os.path.exists(pos_file):
            try:
                with open(pos_file) as f:
                    pos = json.load(f)
                if not pos.get("exited"):
                    has_position = True
                    entry_price = pos.get("entry_price", 0)
                    entry_date = pos.get("entry_date")
            except:
                pass

        if has_position and entry_price > 0:
            exit_r = check_exit(data, entry_price, entry_date)
            results[name] = exit_r
            if exit_r.get("exit"):
                try:
                    with open(pos_file) as f:
                        pos = json.load(f)
                    pos["exited"] = True
                    pos["exit_date"] = data[-1]["date_str"]
                    pos["exit_price"] = exit_r["exit_price"]
                    pos["profit_pct"] = exit_r["profit_pct"]
                    with open(pos_file, "w") as f:
                        json.dump(pos, f, ensure_ascii=False, indent=2)
                except:
                    pass
        else:
            sig = generate_signal(data)
            results[name] = sig
            if sig.get("signal") == 1:
                pos = {
                    "entry_date": data[-1]["date_str"],
                    "entry_price": sig["entry_price"],
                    "stop_loss": sig["stop_loss"],
                    "trail_stop": sig["trail_stop"],
                    "exited": False,
                }
                with open(pos_file, "w") as f:
                    json.dump(pos, f, ensure_ascii=False, indent=2)

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("ATR趋势跟踪 — 信号")
    print("=" * 60)
    results = run()
    for name, r in results.items():
        print(f"\n[{name}]")
        for k, v in r.items():
            print(f"  {k}: {v}")
