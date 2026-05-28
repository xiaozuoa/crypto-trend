#!/usr/bin/env python3
"""ATR趋势跟踪策略 — EMA30日线 + ATR突破, BTC/ETH, 无杠杆"""

import os, sys, json, math
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_engine import fetch_daily, SYMBOLS
from indicators import atr, ema, sma
from config import get_config

WORKSPACE = os.path.expanduser("~/.crypto-trend/workspace")
os.makedirs(WORKSPACE, exist_ok=True)


def get_ma(data, cfg):
    """根据配置返回EMA或SMA序列"""
    if cfg.get("ma_type") == "ema":
        return ema(data, cfg["ma_period"])
    return sma(data, cfg["ma_period"])


def generate_signal(data, cfg):
    n = len(data)
    ma_p = cfg["ma_period"]
    if n < ma_p:
        return {"signal": 0, "reason": "数据不足"}

    ma_vals = get_ma(data, cfg)
    a = atr(data, cfg["atr_period"])
    current = data[-1]
    current_ma = ma_vals[-1] if ma_vals[-1] is not None else current["c"]
    current_atr = a[-1] if a[-1] is not None else current["c"] * 0.03

    buy_trigger = current_ma + cfg["buy_atr_mult"] * current_atr
    price_ok = current["c"] > buy_trigger

    vol_ok = True
    if len(data) > cfg["vol_lookback"]:
        avg_vol = sum(d["v"] for d in data[-cfg["vol_lookback"]-1:-1]) / cfg["vol_lookback"]
        if data[-1]["v"] < avg_vol * cfg["vol_threshold"]:
            vol_ok = False

    if price_ok and vol_ok:
        stop_loss = current_ma
        trail_stop = current["h"] - cfg["trail_atr_mult"] * current_atr
        return {
            "signal": 1,
            "action": "buy",
            "entry_price": round(current["c"], 2),
            "stop_loss": round(stop_loss, 2),
            "trail_stop": round(trail_stop, 2),
            "atr": round(current_atr, 2),
            "atr_pct": round(current_atr / current["c"] * 100, 2),
            "ma": round(current_ma, 2),
            "date": current["date_str"],
            "vol_ok": vol_ok,
        }

    return {
        "signal": 0,
        "action": "wait",
        "price": round(current["c"], 2),
        "ma": round(current_ma, 2),
        "buy_trigger": round(buy_trigger, 2),
        "atr": round(current_atr, 2),
        "date": current["date_str"],
        "vol_ok": vol_ok,
    }


def check_exit(data, entry_price, cfg, entry_date=None, stored_highest=0):
    n = len(data)
    ma_p = cfg["ma_period"]
    if n < ma_p:
        return {"exit": False, "reason": "数据不足"}

    ma_vals = get_ma(data, cfg)
    current_ma = ma_vals[-1] if ma_vals[-1] is not None else data[-1]["c"]
    a = atr(data, cfg["atr_period"])
    current_atr = a[-1] if a[-1] is not None else data[-1]["c"] * 0.03
    current = data[-1]

    if entry_date:
        if entry_date >= data[0]["date_str"]:
            candidates = [d["h"] for d in data if d["date_str"] >= entry_date]
            window_high = max(candidates) if candidates else max(d["h"] for d in data[-ma_p:])
            highest = max(window_high, stored_highest)
        else:
            highest = max(stored_highest, max(d["h"] for d in data[-ma_p:]))
    else:
        highest = max(d["h"] for d in data[-ma_p:])

    trail_stop = highest - cfg["trail_atr_mult"] * current_atr

    reasons = []
    ma_type = cfg.get("ma_type", "MA").upper()
    if current["c"] < current_ma:
        reasons.append(f"跌破{ma_type}{ma_p} ({current['c']:.1f} < {current_ma:.1f})")
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
        "ma": round(current_ma, 2),
        "current": round(current["c"], 2),
        "date": current["date_str"],
    }


def run():
    results = {}
    for name, sym in SYMBOLS.items():
        cfg = get_config(name)
        data = fetch_daily(sym, 200)
        if len(data) < 60:
            results[name] = {"error": f"数据不足({len(data)}条)"}
            continue

        pos_file = os.path.join(WORKSPACE, f"position_{name}.json")
        has_position = False
        entry_price = 0
        entry_date = None
        stored_highest = 0
        if os.path.exists(pos_file):
            try:
                with open(pos_file) as f:
                    pos = json.load(f)
                if not pos.get("exited"):
                    has_position = True
                    entry_price = pos.get("entry_price", 0)
                    entry_date = pos.get("entry_date")
                    stored_highest = pos.get("highest", 0)
            except:
                pass

        if has_position and entry_price > 0:
            exit_r = check_exit(data, entry_price, cfg, entry_date, stored_highest)
            results[name] = exit_r
            if exit_r.get("exit"):
                try:
                    os.remove(pos_file)
                except:
                    pass
        elif has_position:
            results[name] = {"error": f"仓位文件损坏(entry_price=0), 跳过, 请手动检查OKX持仓"}
        else:
            sig = generate_signal(data, cfg)
            results[name] = sig
            if sig.get("signal") == 1:
                pos = {
                    "entry_date": data[-1]["date_str"],
                    "entry_price": sig["entry_price"],
                    "stop_loss": sig["stop_loss"],
                    "trail_stop": sig["trail_stop"],
                    "highest": data[-1]["h"],
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
        cfg = get_config(name)
        ma_label = f"{cfg['ma_type'].upper()}{cfg['ma_period']}"
        print(f"\n[{name}] {ma_label} buy={cfg['buy_atr_mult']} trail={cfg['trail_atr_mult']}")
        for k, v in r.items():
            print(f"  {k}: {v}")
