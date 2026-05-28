"""策略参数配置 — 支持Walk-Forward优化"""

STRATEGY = {
    "ma_type": "ema",
    "ma_period": 30,
    "atr_period": 14,
    "buy_atr_mult": 2.0,
    "trail_atr_mult": 2.0,
    "vol_lookback": 20,
    "vol_threshold": 1.2,
    "fee_rate": 0.001,
    "initial_capital": 10000,
}

# 分币种覆盖
PER_SYMBOL = {
    "BTC": {
        # EMA30 buy=2.0 trail=2.0
    },
    "ETH": {
        "ma_period": 28,         # Walk-Forward最优: EMA28 vs BTC EMA30
        "buy_atr_mult": 2.2,     # 稍宽的入场过滤ETH高波动
    },
}

# Walk-Forward优化记录
# 运行 python scripts/optimizer.py 每季度重新优化
# 2026-05-28: BTC(EMA30/2.0/2.0) ETH(EMA28/2.2/2.0)

BACKTEST = {
    "start_date": "2022-01-01",
}


def get_config(symbol_name):
    cfg = dict(STRATEGY)
    if symbol_name in PER_SYMBOL:
        cfg.update(PER_SYMBOL[symbol_name])
    return cfg
