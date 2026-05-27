#!/usr/bin/env python3
"""数据引擎 — OKX API, 日线BTC/ETH"""

import json, urllib.request, ssl, os, sys, io, time
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8') if hasattr(sys.stdout, 'buffer') else sys.stdout

ssl_ctx = ssl.create_default_context()

SYMBOLS = {"BTC": "BTC-USDT", "ETH": "ETH-USDT"}

def fetch_daily(symbol, limit=300):
    """获取日线K线, 返回 [{date_ts, o, h, l, c, v}, ...] 按时间升序"""
    url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}&bar=1D&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as r:
            data = json.loads(r.read())
        if data.get("code") != "0" or not data.get("data"):
            return []
        candles = data["data"]
        result = []
        for c in reversed(candles):  # OKX返回最新在前, 反转
            ts = int(c[0])
            result.append({
                "date": ts,
                "date_str": datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d"),
                "o": float(c[1]), "h": float(c[2]), "l": float(c[3]),
                "c": float(c[4]), "v": float(c[5]),
            })
        return result
    except Exception as e:
        print(f"  fetch error: {e}")
        return []

def fetch_daily_full(symbol, start_date="2022-01-01"):
    """获取从start_date至今的所有日线数据"""
    all_data = []
    after = ""
    for batch in range(30):
        url = f"https://www.okx.com/api/v5/market/history-candles?instId={symbol}&bar=1D&limit=300"
        if after:
            url += f"&after={after}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as r:
                data = json.loads(r.read())
            if data.get("code") != "0" or not data.get("data"):
                break
            candles = data["data"]
            if len(candles) < 2:
                break
            all_data = candles + all_data
            after = candles[-1][0]
            oldest = datetime.fromtimestamp(int(after) / 1000).strftime("%Y-%m-%d")
            if oldest <= start_date:
                break
            time.sleep(0.3)
        except Exception as e:
            print(f"  batch {batch} error: {e}")
            time.sleep(3)

    seen = set()
    unique = []
    for c in all_data:
        if c[0] not in seen:
            seen.add(c[0])
            unique.append(c)
    unique.sort(key=lambda x: int(x[0]))

    result = []
    for c in unique:
        ts = int(c[0])
        result.append({
            "date": ts,
            "date_str": datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d"),
            "o": float(c[1]), "h": float(c[2]), "l": float(c[3]),
            "c": float(c[4]), "v": float(c[5]),
        })
    return result

if __name__ == "__main__":
    for name, sym in SYMBOLS.items():
        data = fetch_daily(sym, 10)
        print(f"{name}: {len(data)} candles")
        if data:
            print(f"  {data[0]['date_str']} ~ {data[-1]['date_str']}")
            print(f"  latest: ${data[-1]['c']:.1f}")
