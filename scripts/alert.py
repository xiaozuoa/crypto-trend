#!/usr/bin/env python3
"""每日邮件: BTC/ETH ATR趋势信号"""

import os, sys, io, smtplib, json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategy import run

WORKSPACE = os.path.expanduser("~/.crypto-trend/workspace")
CONFIG_FILE = os.path.join(WORKSPACE, "alert_config.json")
os.makedirs(WORKSPACE, exist_ok=True)


def load_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except:
            pass
    return {
        "email_from": os.environ.get("CRYPTO_EMAIL_FROM") or cfg.get("email_from", ""),
        "email_to": os.environ.get("CRYPTO_EMAIL_TO") or cfg.get("email_to", ""),
        "smtp_pass": os.environ.get("SMTP_PASS") or cfg.get("smtp_pass", ""),
        "smtp_host": os.environ.get("CRYPTO_SMTP_HOST") or cfg.get("smtp_host", "smtp.qq.com"),
        "smtp_port": int(os.environ.get("CRYPTO_SMTP_PORT") or cfg.get("smtp_port", "465")),
    }


CFG = load_config()


def send_email(results):
    if not CFG["smtp_pass"]:
        print("未配置SMTP")
        return False

    now = datetime.now()
    lines = []
    lines.append(f"⏰ {now.strftime('%Y年%m月%d日 %H:%M')}")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("  ATR趋势跟踪 — 每日信号")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("策略: 价格突破MA50+2×ATR买入, 跌破MA50或跟踪止损卖出")
    lines.append("标的: BTC/USDT + ETH/USDT")
    lines.append("")

    has_action = False
    for name, r in results.items():
        lines.append(f"━━━ {name} ━━━")
        if r.get("error"):
            lines.append(f"  ⚠️ {r['error']}")
        elif r.get("signal") == 1:
            has_action = True
            lines.append(f"  🔥 买入信号!")
            lines.append(f"     入场价: ${r['entry_price']:.1f}")
            lines.append(f"     止损:   ${r['stop_loss']:.1f} (MA50)")
            lines.append(f"     跟踪止损: ${r['trail_stop']:.1f} (最高价-3×ATR)")
            lines.append(f"     ATR:    ${r['atr']:.1f} ({r['atr_pct']:.1f}%)")
        elif r.get("exit"):
            has_action = True
            lines.append(f"  🔔 卖出信号!")
            lines.append(f"     原因: {r['reason']}")
            lines.append(f"     卖出价: ${r['exit_price']:.1f}")
            lines.append(f"     盈亏: {r['profit_pct']:+.2f}%")
        elif r.get("action") == "wait":
            lines.append(f"  ⏸️ 等待中")
            lines.append(f"     现价: ${r['price']:.1f}")
            lines.append(f"     MA50: ${r['ma50']:.1f}")
            lines.append(f"     买入触发价: ${r['buy_trigger']:.1f}")
        else:
            lines.append(f"  📊 持仓中 (止损${r.get('trail_stop', '?')})")
        lines.append("")

    if not has_action:
        lines.append("📭 今日无操作信号")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("风险提示")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("  ⚠ 加密波动极大, 历史最大回撤30%+")
    lines.append("  ⚠ 做好连续亏损5-8次的心理准备(胜率约40%)")
    lines.append("  ⚠ 严格止损, 不要扛单")
    lines.append("")
    lines.append("📬 每日自动发送 | 交易所: OKX")

    body = "\n".join(lines)
    subject = "BTC/ETH ATR趋势"
    if has_action:
        subject = "🔥 " + subject + " — 有操作!"

    try:
        msg = MIMEMultipart()
        msg["From"] = CFG["email_from"]
        msg["To"] = CFG["email_to"]
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP_SSL(CFG["smtp_host"], CFG["smtp_port"], timeout=30)
        server.login(CFG["email_from"], CFG["smtp_pass"])
        server.sendmail(CFG["email_from"], CFG["email_to"], msg.as_string())
        server.quit()
        print(f"✅ 已发送 → {CFG['email_to']}")
        return True
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("ATR趋势跟踪 — 每日信号")
    print("=" * 60)
    results = run()
    for name, r in results.items():
        print(f"\n[{name}]")
        for k, v in r.items():
            print(f"  {k}: {v}")
    send_email(results)
