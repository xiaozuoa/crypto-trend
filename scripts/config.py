"""策略参数配置 — 支持统一配置和分币种覆盖"""

STRATEGY = {
    # 核心参数
    "ma_type": "ema",          # 均线类型: sma 或 ema
    "ma_period": 30,           # 均线周期 (EMA30 ≈ 1.5月趋势)
    "atr_period": 14,          # ATR周期
    "buy_atr_mult": 2.0,       # 买入: 价格突破 MA + N×ATR
    "trail_atr_mult": 2.0,     # 跟踪止损: 最高价 - N×ATR
    "vol_lookback": 20,        # 成交量均值回看天数
    "vol_threshold": 1.2,      # 成交量确认: 当日量 > 均量×N
    "fee_rate": 0.001,         # 手续费率 (0.1%)
    "initial_capital": 10000,  # 回测初始资金
}

# 分币种覆盖 (只写与默认不同的参数, 当前EMA30已是最优统一配置)
PER_SYMBOL = {
    # BTC和ETH都使用EMA30, 无需覆盖
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
