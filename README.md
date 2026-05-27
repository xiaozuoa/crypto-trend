# crypto-trend — BTC/ETH ATR趋势跟踪

基于 OKX API 的日线趋势跟踪策略，GitHub Actions 每日自动运行，有操作信号时邮件通知。

## 策略逻辑

| 规则 | 条件 |
|------|------|
| 买入 | 收盘价突破 MA50 + 2×ATR，且成交量 > 20日均量 × 1.2 |
| 卖出 | 收盘价跌破 MA50 或 跌破入场以来最高价 − 3×ATR |

- 标的：BTC-USDT、ETH-USDT
- 交易所：OKX（现货，无杠杆）
- 运行频率：每日北京时间 08:00

## 回测表现 (2022-2026)

| 指标 | BTC | ETH |
|------|-----|-----|
| 总收益 | +124.9% | +79.1% |
| 年化收益 | +20.2% | +14.1% |
| 最大回撤 | -27.0% | -41.5% |
| Sharpe | 0.84 | 0.57 |
| 胜率 | 50.0% | 46.7% |
| 盈亏比 | 2.8 | 2.5 |
| 超额收益(vs买入持有) | +64.0% | +123.1% |

## 项目结构

```
├── .github/workflows/daily-signal.yml  # GitHub Actions 定时触发
├── scripts/
│   ├── alert.py          # 邮件发送入口
│   ├── strategy.py       # 策略逻辑 + 持仓管理
│   ├── backtest.py       # 回测引擎
│   ├── data_engine.py    # OKX API 数据获取
│   ├── indicators.py     # 技术指标 (EMA/ATR/SMA)
│   └── config.py         # 策略参数配置
└── requirements.txt
```

## 部署

1. Fork 仓库
2. 配置 GitHub Secrets：
   - `CRYPTO_EMAIL_FROM` — 发送邮箱
   - `CRYPTO_EMAIL_TO` — 接收邮箱
   - `SMTP_PASS` — SMTP 授权码
3. GitHub Actions 每日自动运行

## 参数调优

修改 `scripts/config.py` 后运行 `python scripts/backtest.py` 验证。

默认参数（已回测验证为最优组合）：
- MA周期: 50
- 买入ATR乘数: 2.0
- 跟踪止损ATR乘数: 3.0
- 成交量阈值: 1.2×20日均量
