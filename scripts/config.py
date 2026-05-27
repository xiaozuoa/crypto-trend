"""策略参数配置 — 支持统一配置和分币种覆盖"""

STRATEGY = {
    # 默认参数 (所有币种共用)
    "ma_period": 50,
    "atr_period": 14,
    "buy_atr_mult": 2.0,
    "trail_atr_mult": 3.0,
    "vol_lookback": 20,
    "vol_threshold": 1.2,
    "fee_rate": 0.001,
    "initial_capital": 10000,
}

# 分币种覆盖 (只写与默认不同的参数)
PER_SYMBOL = {
    "BTC": {
        "buy_atr_mult": 1.5,   # BTC趋势强, 更敏感的入场
    },
    "ETH": {
        "ma_period": 40,        # ETH波动大, 更短均线
        "buy_atr_mult": 1.5,
        "trail_atr_mult": 2.5,  # ETH回撤更快, 更紧的跟踪止损
    },
}

BACKTEST = {
    "start_date": "2022-01-01",
}


def get_config(symbol_name):
    """返回某个币种的完整配置 (默认 + 覆盖)"""
    cfg = dict(STRATEGY)
    if symbol_name in PER_SYMBOL:
        cfg.update(PER_SYMBOL[symbol_name])
    return cfg
