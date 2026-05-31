"""策略参数配置 — 支持Walk-Forward优化"""

STRATEGY = {
    "ma_type": "ema",
    "ma_period": 30,
    "atr_period": 14,
    "buy_atr_mult": 2.0,
    "trail_atr_mult": 1.8,
    "vol_lookback": 20,
    "vol_threshold": 1.2,
    "fee_rate": 0.001,
    "initial_capital": 10000,
}

# 分币种覆盖
PER_SYMBOL = {
    "BTC": {
        "ma_period": 35,         # WF最优: EMA35 (5窗口: 24/40/40/24/35), 最近窗口选35
    },
    "ETH": {
        "ma_period": 24,         # WF最优: EMA24 (5窗口: 28/28/24/24/24), 后3窗口一致选24
        "buy_atr_mult": 1.5,     # WF最优: 1.5 (修复后optimizer, 5窗口: 1.5/2.2/2.0/2.0/1.5)
    },
}

# Walk-Forward优化记录
# 运行 python scripts/optimizer.py 每季度重新优化
# 2026-05-31: 修复未来函数后重新WF — BTC(EMA35/2.0/1.8) ETH(EMA24/1.5/1.8)
#   trail_atr 两个品种统一为1.8 (BTC 5/5窗口, ETH 3/5窗口一致)
# 2026-05-28: BTC(EMA30/2.0/2.0) ETH(EMA28/2.2/2.6) — ETH trail从2.0上调至2.6, 收益+13%→+234%

BACKTEST = {
    "start_date": "2022-01-01",
}


def get_config(symbol_name):
    cfg = dict(STRATEGY)
    if symbol_name in PER_SYMBOL:
        cfg.update(PER_SYMBOL[symbol_name])
    return cfg
