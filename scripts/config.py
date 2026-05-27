"""策略参数配置 — 统一管理, 策略和回测共享"""

STRATEGY = {
    "ma_period": 50,          # 趋势均线周期
    "atr_period": 14,         # ATR周期
    "buy_atr_mult": 2.0,      # 买入: 价格突破 MA + N×ATR
    "trail_atr_mult": 3.0,    # 跟踪止损: 最高价 - N×ATR
    "vol_lookback": 20,       # 成交量均值回看天数
    "vol_threshold": 1.2,     # 成交量确认: 当日量 > 均量×N
    "fee_rate": 0.001,        # 手续费率 (0.1%)
    "initial_capital": 10000,  # 回测初始资金
}

BACKTEST = {
    "start_date": "2022-01-01",
}
