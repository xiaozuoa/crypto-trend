"""共享技术指标 — EMA, ATR, SMA"""


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


