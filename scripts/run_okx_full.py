#!/usr/bin/env python3
"""OKX 全量数据 — 修复后回测 + WF 优化器完整版"""
import sys, os, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest import backtest
from optimizer import backtest_range, walk_forward_optimize
from data_engine import fetch_daily_full, SYMBOLS
from config import get_config


def main():
    print("=" * 70)
    print(f"OKX 全量回测 + WF优化 (修复后) — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    for name, sym in SYMBOLS.items():
        print(f"\n{'─' * 70}")
        print(f"[{name}] {sym}")
        print(f"{'─' * 70}")

        print("  拉取全量数据...")
        data = fetch_daily_full(sym)
        if not data or len(data) < 200:
            print(f"  ❌ 数据不足 ({len(data) if data else 0}条)")
            continue
        print(f"  数据: {data[0]['date_str']} ~ {data[-1]['date_str']} ({len(data)}天)")

        cfg = get_config(name)
        ma_label = f"{cfg['ma_type'].upper()}{cfg['ma_period']}"

        # ── 当前参数回测 ──
        print(f"\n  ── 当前参数回测 ({ma_label} buy={cfg['buy_atr_mult']} trail={cfg['trail_atr_mult']}) ──")
        r = backtest(data, cfg, verbose=False)
        if not r:
            print("  ❌ 回测失败")
            continue
        print(f"  收益: {r['total_return']:+.1f}%  年化: {r['annual_return']:+.1f}%  回撤: {r['max_drawdown']:+.1f}%")
        print(f"  夏普: {r['sharpe']:.2f}  胜率: {r['win_rate']:.1f}%  交易: {r['trades']}笔")
        print(f"  均盈: {r['avg_win']:+.1f}%  均亏: {r['avg_loss']:+.1f}%  盈亏比: ", end="")
        if r.get('avg_loss') and r['avg_loss'] != 0:
            print(f"{r['avg_win']/abs(r['avg_loss']):.1f}")
        else:
            print("N/A")
        print(f"  买持: {r['buy_hold']:+.1f}%  超额: {r['excess']:+.1f}%")

        # ── 交易明细 ──
        if r['trades'] > 0:
            print(f"\n  📋 交易明细 ({r['trades']}笔):")
            print(f"  {'入场':>10} {'出场':>12} {'入场价':>10} {'出场价':>10} {'盈亏':>8}  原因")
            print(f"  {'─'*10} {'─'*12} {'─'*10} {'─'*10} {'─'*8}  {'─'*30}")
            for t in r['trades_list']:
                print(f"  {t['entry_date']:>10} {t['exit_date']:>12} ${t['entry_price']:>9.1f} ${t['exit_price']:>9.1f} {t['profit_pct']:>+7.2f}%  {t['reason']}")

        # ── Walk-Forward 优化 ──
        print(f"\n  ── Walk-Forward 网格搜索 (7×5×5=175组合/窗口) ──")
        t0 = time.time()
        windows = walk_forward_optimize(data, cfg=cfg)
        elapsed = time.time() - t0
        if not windows:
            print("  ❌ WF 优化失败")
            continue

        print(f"  耗时: {elapsed:.0f}s, 窗口数: {len(windows)}")
        compound = 1.0
        for w in windows:
            print(f"    {w['train_start']}~{w['train_end']} → {w['test_start']}~{w['test_end']}: "
                  f"EMA{w['period']} buy={w['buy_atr']} trail={w['trail_atr']} "
                  f"train={w['train_return']:+.1f}% test={w['test_return']:+.1f}%")
            compound *= (1 + w['test_return'] / 100)
        total_test = (compound - 1) * 100
        print(f"  WF累计(复利): {total_test:+.1f}%")

        last = windows[-1]
        print(f"\n  ── 当前 vs WF最优 全量回测对比 ──")

        # 用最优参数跑全量回测
        cfg_opt = dict(cfg)
        cfg_opt["ma_period"] = last['period']
        cfg_opt["buy_atr_mult"] = last['buy_atr']
        cfg_opt["trail_atr_mult"] = last['trail_atr']
        r_opt = backtest(data, cfg_opt, verbose=False)

        ma_opt = f"EMA{last['period']}"
        sep = "-" * 25 + " " + "-" * 8 + " " + "-" * 8 + " " + "-" * 8 + " " + "-" * 6 + " " + "-" * 6 + " " + "-" * 4
        header = "{0:<25} {1:>8} {2:>8} {3:>8} {4:>6} {5:>6} {6:>4}".format(
            "参数", "收益", "年化", "回撤", "夏普", "胜率", "交易")
        print("  " + header)
        print("  " + sep)
        curr_label = "当前 {}/{}/{}".format(ma_label, cfg["buy_atr_mult"], cfg["trail_atr_mult"])
        print("  {0:<25} {1:>+7.1f}% {2:>+7.1f}% {3:>+7.1f}% {4:>5.2f} {5:>5.1f}% {6:>4}".format(
            curr_label, r['total_return'], r['annual_return'], r['max_drawdown'],
            r['sharpe'], r['win_rate'], r['trades']))
        if r_opt:
            opt_label = "WF最优 {}/{}/{}".format(ma_opt, last["buy_atr"], last["trail_atr"])
            print("  {0:<25} {1:>+7.1f}% {2:>+7.1f}% {3:>+7.1f}% {4:>5.2f} {5:>5.1f}% {6:>4}".format(
                opt_label, r_opt['total_return'], r_opt['annual_return'], r_opt['max_drawdown'],
                r_opt['sharpe'], r_opt['win_rate'], r_opt['trades']))

        # ── 各参数稳定性检查 ──
        print(f"\n  ── WF 窗口参数稳定性 ──")
        periods = [w['period'] for w in windows]
        buys = [w['buy_atr'] for w in windows]
        trails = [w['trail_atr'] for w in windows]
        print(f"  period:   {periods} (唯一值: {len(set(periods))})")
        print(f"  buy_atr:  {buys} (唯一值: {len(set(buys))})")
        print(f"  trail_atr: {trails} (唯一值: {len(set(trails))})")

    print(f"\n{'=' * 70}")
    print("数据源: OKX API (全量)")
    print("代码版本: 修复后 (pending_entry + trail_stop cap + 更新顺序)")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
