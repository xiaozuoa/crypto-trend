# crypto-trend — BTC/ETH ATR趋势跟踪

基于 OKX API 的日线趋势跟踪策略，GitHub Actions 每日自动运行，有操作信号时邮件通知。

## 策略逻辑

| 规则 | BTC | ETH |
|------|-----|-----|
| 趋势线 | EMA30 | EMA28 |
| 买入 | 价格 > 趋势线 + 2.0×ATR | 价格 > 趋势线 + 2.2×ATR |
| 卖出 | 跌破趋势线 或 最高价−2.0×ATR | 跌破趋势线 或 最高价−2.0×ATR |
| 确认 | 成交量 > 20日均量×1.2 | 成交量 > 20日均量×1.2 |

## 回测表现 (2022-2026)

| 指标 | BTC | ETH |
|------|-----|-----|
| 总收益 | +180.7% | +220.9% |
| 年化收益 | +26.4% | +30.3% |
| 最大回撤 | -23.8% | -25.0% |
| Sharpe | 1.10 | 1.00 |
| 胜率 | 50.0% | 57.1% |
| 盈亏比 | 3.9 | 3.4 |

## 参数优化

策略参数通过 Walk-Forward 滚动优化选定，每季度运行一次：

```bash
cd scripts && python optimizer.py
```

优化器会：
1. 用过去2年数据网格搜索最优参数
2. 在后续6个月验证
3. 输出全局最优和近2年最优参数
4. 手动将结果更新到 `config.py`

## 项目结构

```
├── .github/workflows/daily-signal.yml
├── scripts/
│   ├── alert.py          # 邮件发送
│   ├── strategy.py       # 策略逻辑
│   ├── backtest.py       # 回测引擎
│   ├── optimizer.py      # Walk-Forward参数优化
│   ├── data_engine.py    # OKX API
│   ├── indicators.py     # EMA/ATR/SMA/MACD
│   └── config.py         # 策略参数
└── requirements.txt
```

## 部署

1. Fork 仓库
2. 配置 GitHub Secrets：`CRYPTO_EMAIL_FROM`, `CRYPTO_EMAIL_TO`, `SMTP_PASS`
3. Actions 每日 UTC 00:00 (北京时间 08:00) 自动运行
