#!/usr/bin/env python3
"""用 Yahoo Finance 数据跑回测和优化器 — OKX 不可达时的备用方案"""
import sys, os, json, time, requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest import backtest
from optimizer import backtest_range, walk_forward_optimize, grid_search
from config import get_config, STRATEGY

YAHOO_SYMBOLS = {"BTC": "BTC-USD", "ETH": "ETH-USD"}


def fetch_yahoo(symbol, start_ts=1640995200):
    """从 Yahoo Finance 获取日线，返回 [dict] 格式与 data_engine 一致"""
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    params = {'period1': start_ts, 'period2': int(time.time()), 'interval': '1d'}
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    data = r.json()
    result = data['chart']['result'][0]
    quotes = result['indicators']['quote'][0]
    timestamps = result['timestamp']

    bars = []
    for i, ts in enumerate(timestamps):
        o, h, l, c, v = (quotes['open'][i], quotes['high'][i],
                         quotes['low'][i], quotes['close'][i], quotes['volume'][i])
        if o is None or h is None or l is None or c is None or v is None:
            continue
        if h < l:
            continue
        dt = datetime.fromtimestamp(ts)
        bars.append({
            "date": ts, "date_str": dt.strftime("%Y-%m-%d"),
            "o": o, "h": h, "l": l, "c": c, "v": v,
        })
    return bars


def main():
    print("=" * 70)
    print(f"Yahoo Finance 回测 + WF优化 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    for name, sym in YAHOO_SYMBOLS.items():
        print(f"\n[{name}] 获取 Yahoo 数据...")
        data = fetch_yahoo(sym)
        if not data:
            print("  获取失败")
            continue
        print(f"  数据: {data[0]['date_str']} ~ {data[-1]['date_str']} ({len(data)}天)")

        cfg = get_config(name)
        ma_label = f"{cfg['ma_type'].upper()}{cfg['ma_period']}"

        # ── 回测 ──
        print(f"\n  ── 回测 ({ma_label} buy={cfg['buy_atr_mult']} trail={cfg['trail_atr_mult']}) ──")
        r = backtest(data, cfg, verbose=False)
        if r:
            print(f"  总收益: {r['total_return']:+.1f}%  年化: {r['annual_return']:+.1f}%")
            print(f"  回撤: {r['max_drawdown']:+.1f}%  夏普: {r['sharpe']:.2f}")
            print(f"  交易: {r['trades']}笔  胜率: {r['win_rate']:.1f}%")
            print(f"  均盈: {r['avg_win']:+.1f}%  均亏: {r['avg_loss']:+.1f}%")
            print(f"  买持: {r['buy_hold']:+.1f}%  超额: {r['excess']:+.1f}%")
            if r['avg_loss'] and r['avg_loss'] != 0:
                print(f"  盈亏比: {r['avg_win']/abs(r['avg_loss']):.1f}")

        # ── WF 优化 ──
        print(f"\n  ── Walk-Forward 优化 ──")
        windows = walk_forward_optimize(data, cfg=cfg)
        if windows:
            compound = 1.0
            for w in windows:
                print(f"    {w['train_start']}~{w['train_end']} -> {w['test_start']}~{w['test_end']}: "
                      f"EMA{w['period']} buy={w['buy_atr']} trail={w['trail_atr']} test={w['test_return']:+.1f}%")
                compound *= (1 + w['test_return'] / 100)
            total_test = (compound - 1) * 100
            print(f"  WF累计(复利): {total_test:+.1f}%")
            last = windows[-1]
            print(f"  当前最优: EMA{last['period']} buy={last['buy_atr']} trail={last['trail_atr']}")

        # ── 当前 vs WF 最优 对比 ──
        if windows:
            last = windows[-1]
            print(f"\n  ── 当前参数 vs WF最优 对比 ──")
            curr_ret = backtest_range(data, None, None,
                                      cfg["ma_period"], cfg["buy_atr_mult"], cfg["trail_atr_mult"],
                                      cfg=cfg)
            opt_ret = backtest_range(data, None, None,
                                     last['period'], last['buy_atr'], last['trail_atr'],
                                     cfg=cfg)
            print(f"  当前 {ma_label} buy={cfg['buy_atr_mult']} trail={cfg['trail_atr_mult']}: {curr_ret:+.1f}%")
            print(f"  WF最优 EMA{last['period']} buy={last['buy_atr']} trail={last['trail_atr']}: {opt_ret:+.1f}%")

    print(f"\n{'=' * 70}")
    print("数据源: Yahoo Finance (备用), OKX 不可达时使用")
    print("注意: Yahoo Finance 数据可能与 OKX 有细微差异")


if __name__ == "__main__":
    main()
