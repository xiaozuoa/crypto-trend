#!/usr/bin/env python3
"""Walk-Forward参数优化器 — 每季度运行, 更新config.py"""

import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_engine import fetch_daily_full, SYMBOLS
from indicators import ema, atr, sma
from config import STRATEGY, get_config
from datetime import datetime, timedelta


def backtest_range(data, start_date, end_date, period, buy_m, trail_m, cfg=None):
    """在指定日期范围内回测, 返回总收益%"""
    if cfg is None:
        cfg = STRATEGY
    n = len(data)
    atr_p = cfg["atr_period"]
    if n <= max(period, atr_p):
        return None
    ma_fn = ema if cfg.get("ma_type") == "ema" else sma
    t = ma_fn(data, period)
    a = atr(data, atr_p)
    vol_lb = cfg["vol_lookback"]
    vol_th = cfg["vol_threshold"]
    fee = 1 - cfg["fee_rate"]
    cash, pos, hi, last_p = 10000.0, 0.0, 0.0, data[0]['c']
    warmup = max(period, atr_p)
    for i in range(warmup, n):
        if start_date and data[i]['date_str'] < start_date:
            continue
        if end_date and data[i]['date_str'] >= end_date:
            continue
        p = data[i]['c']
        last_p = p
        av = a[i] if a[i] is not None else p * 0.03
        tv = t[i] if t[i] is not None else p
        if pos > 0:
            hi = max(hi, data[i]['h'])
            if p < tv or p < hi - trail_m * av:
                cash = pos * p * fee
                pos = 0.0
        elif p > tv + buy_m * av:
                vo = True
                if i >= vol_lb:
                    avg_vol = sum(d['v'] for d in data[i-vol_lb:i]) / vol_lb
                    if data[i]['v'] < avg_vol * vol_th:
                        vo = False
                if vo:
                    pos = (cash * fee) / p
                    hi = data[i]['h']
                    cash = 0.0
    if pos > 0:
        cash = pos * last_p * fee
    return (cash / 10000 - 1) * 100


def grid_search(data, start_date=None, end_date=None, cfg=None):
    """网格搜索最优 (period, buy_atr, trail_atr)"""
    best = -999
    best_params = (30, 2.0, 2.0)

    for period in [20, 24, 28, 30, 35, 40, 50]:
        for buy_m in [1.5, 1.8, 2.0, 2.2, 2.5]:
            for trail_m in [1.8, 2.0, 2.2, 2.5, 3.0]:
                r = backtest_range(data, start_date, end_date, period, buy_m, trail_m, cfg=cfg)
                if r is not None and r > best:
                    best = r
                    best_params = (period, buy_m, trail_m)
    return best_params, best


def walk_forward_optimize(data, train_years=2, test_months=6, cfg=None):
    """Walk-Forward滚动优化, 返回每窗口的最优参数"""
    n = len(data)
    dates = sorted(set(d['date_str'] for d in data))
    if not dates:
        return []

    windows = []
    train_start_date = dates[0]

    while True:
        ts = datetime.strptime(train_start_date, '%Y-%m-%d')
        te = ts + timedelta(days=int(train_years * 365))
        tss = te
        tse = tss + timedelta(days=int(test_months * 30))

        te_str = te.strftime('%Y-%m-%d')
        tss_str = tss.strftime('%Y-%m-%d')
        tse_str = tse.strftime('%Y-%m-%d')

        if tse_str > dates[-1]:
            break

        train_data = [d for d in data if train_start_date <= d['date_str'] < te_str]
        test_data = [d for d in data if tss_str <= d['date_str'] < tse_str]

        if len(train_data) >= 365 and len(test_data) >= 90:
            params, train_ret = grid_search(train_data, cfg=cfg)
            test_ret = backtest_range(data, tss_str, tse_str, *params, cfg=cfg)
            windows.append({
                'train_start': train_start_date,
                'train_end': te_str,
                'test_start': tss_str,
                'test_end': tse_str,
                'period': params[0],
                'buy_atr': params[1],
                'trail_atr': params[2],
                'train_return': round(train_ret, 1),
                'test_return': round(test_ret, 1) if test_ret else 0,
            })

        train_start_date = (ts + timedelta(days=int(test_months * 30))).strftime('%Y-%m-%d')

    return windows


def main():
    today = datetime.now().strftime('%Y-%m-%d')
    print('=' * 70)
    print(f'Walk-Forward Optimizer — {today}')
    print('=' * 70)

    for name, sym in SYMBOLS.items():
        print(f'\n[{name}] 获取数据...')
        data = fetch_daily_full(sym)
        if not data:
            print('  Failed')
            continue

        print(f'  数据: {data[0]["date_str"]} ~ {data[-1]["date_str"]} ({len(data)}天)')

        # Full backtest with current static params
        cfg = get_config(name)
        ma_label = f"{cfg['ma_type'].upper()}{cfg['ma_period']}"
        static_ret = backtest_range(data, None, None,
                                    cfg["ma_period"], cfg["buy_atr_mult"], cfg["trail_atr_mult"],
                                    cfg=cfg)
        print(f'  Static {ma_label}: {static_ret:+.1f}%')

        # Walk-forward
        windows = walk_forward_optimize(data, cfg=cfg)
        print(f'  Walk-Forward windows: {len(windows)}')
        compound = 1.0
        for w in windows:
            print(f'    {w["train_start"]}~{w["train_end"]} -> {w["test_start"]}~{w["test_end"]}: EMA{w["period"]} buy={w["buy_atr"]} trail={w["trail_atr"]} test={w["test_return"]:+.1f}%')
            compound *= (1 + w['test_return'] / 100)
        total_test_ret = (compound - 1) * 100
        print(f'  WF累计(复利): {total_test_ret:+.1f}%')

        # Best params from last window (for current use)
        if windows:
            last = windows[-1]
            print(f'  当前最优: EMA{last["period"]} buy={last["buy_atr"]} trail={last["trail_atr"]}')

        # Walk-Forward chosen params only; no full-dataset grid search to avoid overfitting

    print()
    print('=' * 70)
    print('提示: 每季度运行本脚本, 将结果更新到 config.py 的 PER_SYMBOL')


if __name__ == '__main__':
    main()
