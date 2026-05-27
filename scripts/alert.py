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


def has_action(results):
    for r in results.values():
        if r.get("signal") == 1 or r.get("exit"):
            return True
    return False


def send_email(results):
    if not has_action(results):
        heartbeat_file = os.path.join(WORKSPACE, "last_email.json")
        now = datetime.now()
        send_heartbeat = False
        if os.path.exists(heartbeat_file):
            try:
                with open(heartbeat_file) as f:
                    last = json.load(f)
                last_dt = datetime.fromisoformat(last.get("time", "2000-01-01"))
                if (now - last_dt).days >= 7:
                    send_heartbeat = True
            except:
                send_heartbeat = True
        else:
            send_heartbeat = True

        if not send_heartbeat:
            print("无操作信号, 跳过")
            return False

    if not CFG["smtp_pass"]:
        print("未配置SMTP")
        return False

    now = datetime.now()
    lines = []
    lines.append(f"⏰ {now.strftime('%Y年%m月%d日 %H:%M')}")
    lines.append("")

    buy_count = 0
    sell_count = 0
    for name, r in results.items():
        if r.get("signal") == 1:
            buy_count += 1
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"  🔥 {name} 买入信号!")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"  入场价:   ${r['entry_price']:.1f}")
            lines.append(f"  止损(MA50): ${r['stop_loss']:.1f}")
            lines.append(f"  跟踪止损:  ${r['trail_stop']:.1f}")
            lines.append(f"  ATR:       ${r['atr']:.1f} ({r['atr_pct']:.1f}%)")
            lines.append("")
            lines.append("  操作: OKX交易所 → 买入按钮 → 市价买入")
            lines.append(f"  止损单: 限价${r['stop_loss']:.1f}, 触发即卖")
            lines.append("")
        elif r.get("exit"):
            sell_count += 1
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"  🔔 {name} 卖出信号!")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"  原因:  {r['reason']}")
            lines.append(f"  卖出价: ${r['exit_price']:.1f}")
            lines.append(f"  盈亏:  {r['profit_pct']:+.2f}%")
            lines.append("")
            lines.append("  操作: OKX交易所 → 全部卖出")
            lines.append("")

    action_count = buy_count + sell_count
    if action_count == 0:
        lines.append("📊 持仓状态 (每周确认):")
        for name, r in results.items():
            if not r.get("error") and not r.get("exit"):
                if r.get("action") == "wait":
                    lines.append(f"  {name}: 空仓, 等信号")
                else:
                    lines.append(f"  {name}: 持仓中 (跟踪止损${r.get('trail_stop', '?')})")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("  ATR趋势跟踪 | BTC+ETH | OKX")
    lines.append(f"  策略: EMA30+2×ATR买入, 跌破EMA30或2×ATR跟踪止损卖出")
    lines.append(f"  历史: 2022-2026 BTC+181% ETH+206%")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("📬 有操作才发 | 每7天一次心跳确认")

    body = "\n".join(lines)

    if buy_count > 0 and sell_count > 0:
        subject = f"🔥 买入+🔔 卖出 ({buy_count}买{sell_count}卖)"
    elif buy_count > 0:
        subject = "🔥 买入!"
    elif sell_count > 0:
        subject = "🔔 卖出!"
    else:
        subject = "📊 持仓确认"

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

        with open(os.path.join(WORKSPACE, "last_email.json"), "w") as f:
            json.dump({"time": now.isoformat()}, f)
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
