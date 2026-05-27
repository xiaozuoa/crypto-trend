#!/usr/bin/env python3
"""Walk-Forward参数优化器 — 每季度运行, 更新config.py"""

import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_engine import fetch_daily_full, SYMBOLS
from indicators import ema, atr
from datetime import datetime, timedelta


def backtest_range(data, start_date, end_date, period, buy_m, trail_m):
    """在指定日期范围内回测, 返回总收益%"""
    n = len(data)
    if n < period + 14:
        return None
    t = ema(data, period)
    a = atr(data, 14)
    cash, pos, ep, hi = 10000.0, 0.0, 0.0, 0.0
    for i in range(period + 14, n):
        if start_date and data[i]['date_str'] < start_date:
            continue
        if end_date and data[i]['date_str'] >= end_date:
            continue
        p = data[i]['c']
        av = a[i] if a[i] else p * 0.03
        tv = t[i] if t[i] else p
        if pos > 0:
            hi = max(hi, p)
            if p < tv or p < hi - trail_m * av:
                cash += pos * p * 0.999
                pos = 0.0
        else:
            if p > tv + buy_m * av:
                vo = True
                if i >= 20:
                    avg_vol = sum(d['v'] for d in data[i-20:i]) / 20
                    if data[i]['v'] < avg_vol * 1.2:
                        vo = False
                if vo:
                    alloc = cash * 0.999
                    pos, ep, hi = alloc / p, p, p
                    cash -= alloc
    if pos > 0:
        cash += pos * data[-1]['c'] * 0.999
    return (cash / 10000 - 1) * 100


def grid_search(data, start_date=None, end_date=None):
    """网格搜索最优 (period, buy_atr, trail_atr)"""
    best = -999
    best_params = (30, 2.0, 2.0)

    for period in [20, 24, 28, 30, 35, 40, 50]:
        for buy_m in [1.5, 1.8, 2.0, 2.2, 2.5]:
            for trail_m in [1.8, 2.0, 2.2, 2.5, 3.0]:
                r = backtest_range(data, start_date, end_date, period, buy_m, trail_m)
                if r is not None and r > best:
                    best = r
                    best_params = (period, buy_m, trail_m)
    return best_params, best


def walk_forward_optimize(data, train_years=2, test_months=6):
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
            params, train_ret = grid_search(train_data)
            test_ret = backtest_range(data, tss_str, tse_str, *params)
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
        static_ret = backtest_range(data, None, None, 30, 2.0, 2.0)
        print(f'  Static EMA30: {static_ret:+.1f}%')

        # Walk-forward
        windows = walk_forward_optimize(data)
        print(f'  Walk-Forward windows: {len(windows)}')
        total_test_ret = 0
        for w in windows:
            print(f'    {w["train_start"]}~{w["train_end"]} -> {w["test_start"]}~{w["test_end"]}: EMA{w["period"]} buy={w["buy_atr"]} trail={w["trail_atr"]} test={w["test_return"]:+.1f}%')
            total_test_ret += w['test_return']

        # Best params from last window (for current use)
        if windows:
            last = windows[-1]
            print(f'  当前最优: EMA{last["period"]} buy={last["buy_atr"]} trail={last["trail_atr"]}')

        # Also run full grid on all data to find global best
        print(f'  全局最优搜索...')
        global_params, global_ret = grid_search(data)
        print(f'  全局最优: EMA{global_params[0]} buy={global_params[1]} trail={global_params[2]} ({global_ret:+.1f}%)')

        # Also run grid on last 2 years to find recent best
        two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
        recent_params, recent_ret = grid_search(data, start_date=two_years_ago)
        print(f'  近2年最优: EMA{recent_params[0]} buy={recent_params[1]} trail={recent_params[2]} ({recent_ret:+.1f}%)')

    print()
    print('=' * 70)
    print('提示: 每季度运行本脚本, 将结果更新到 config.py 的 PER_SYMBOL')


if __name__ == '__main__':
    main()
