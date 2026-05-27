"""共享技术指标 — EMA, ATR, SMA, MACD"""


def ema(data, period):
    """指数移动平均, 返回与data等长的列表"""
    result = [None] * len(data)
    if len(data) < period:
        return result
    mult = 2 / (period + 1)
    result[period - 1] = sum(d["c"] for d in data[:period]) / period
    for i in range(period, len(data)):
        result[i] = (data[i]["c"] - result[i - 1]) * mult + result[i - 1]
    return result


def atr(data, period=14):
    """平均真实波幅, 返回与data等长的列表"""
    result = [None] * len(data)
    trs = []
    for i in range(1, len(data)):
        h, l, pc = data[i]["h"], data[i]["l"], data[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    for i in range(period, len(data)):
        result[i] = sum(trs[i - period:i]) / period
    return result


def sma(data, period):
    """简单移动平均, 返回列表"""
    result = [None] * len(data)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = sum(d["c"] for d in data[i - period + 1:i + 1]) / period
    return result


def macd(data, fast=12, slow=26, signal=9):
    """
    MACD指标, 返回 (macd_line, signal_line, histogram) 三个等长列表
    MACD线 = EMA(fast) - EMA(slow)
    信号线 = EMA(MACD线, signal)
    柱状图 = MACD线 - 信号线
    """
    n = len(data)
    fast_ema = ema(data, fast)
    slow_ema = ema(data, slow)

    # MACD line = fast EMA - slow EMA
    macd_line = [None] * n
    for i in range(n):
        if fast_ema[i] is not None and slow_ema[i] is not None:
            macd_line[i] = fast_ema[i] - slow_ema[i]

    # Signal line = EMA of MACD line
    signal_line = [None] * n
    # Find first valid MACD value
    valid_macd = [(i, v) for i, v in enumerate(macd_line) if v is not None]
    if len(valid_macd) >= signal:
        start = valid_macd[signal - 1][0]
        # SMA for first signal value
        vals = [macd_line[j] for j in range(start - signal + 1, start + 1) if macd_line[j] is not None]
        if len(vals) == signal:
            signal_line[start] = sum(vals) / signal
        mult = 2 / (signal + 1)
        for i in range(start + 1, n):
            if macd_line[i] is not None and signal_line[i - 1] is not None:
                signal_line[i] = (macd_line[i] - signal_line[i - 1]) * mult + signal_line[i - 1]

    # Histogram = MACD - Signal
    histogram = [None] * n
    for i in range(n):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram[i] = macd_line[i] - signal_line[i]

    return macd_line, signal_line, histogram
