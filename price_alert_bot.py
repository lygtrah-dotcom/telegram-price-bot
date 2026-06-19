"""
Telegram Price Alert Bot
"""

import json
import os
import time
import requests
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATA_FILE = "alerts.json"
CHECK_INTERVAL = 30

def load_alerts():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_alerts(alerts):
    with open(DATA_FILE, "w") as f:
        json.dump(alerts, f)

def get_price(symbol: str):
    symbol = symbol.upper()
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if "price" in data:
            return float(data["price"])
        return None
    except Exception:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Price Alert Bot\n\n"
        "/price BTCUSDT\n"
        "/setalert BTCUSDT 65000\n"
        "/myalerts\n"
        "/clearalerts"
    )

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /price BTCUSDT")
        return
    symbol = context.args[0].upper()
    price = get_price(symbol)
    if price is None:
        await update.message.reply_text(f"Symbol not found: {symbol}")
    else:
        await update.message.reply_text(f"{symbol}: ${price:,.4f}")

async def setalert_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Use: /setalert BTCUSDT 65000")
        return
    symbol = context.args[0].upper()
    try:
        target = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Target must be a number")
        return
    current = get_price(symbol)
    if current is None:
        await update.message.reply_text(f"Symbol not found: {symbol}")
        return
    direction = "above" if target > current else "below"
    alerts = load_alerts()
    alerts.append({
        "chat_id": update.effective_chat.id,
        "symbol": symbol,
        "target": target,
        "direction": direction,
        "triggered": False,
    })
    save_alerts(alerts)
    await update.message.reply_text(
        f"Alert set! {symbol} {direction} ${target:,.4f}\n"
        f"(current: ${current:,.4f})"
    )

async def myalerts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alerts = load_alerts()
    my = [a for a in alerts if a["chat_id"] == update.effective_chat.id and not a["triggered"]]
    if not my:
        await update.message.reply_text("No alerts set.")
        return
    lines = ["Your alerts:"]
    for a in my:
        lines.append(f"{a['symbol']} -> ${a['target']:,.4f} ({a['direction']})")
    await update.message.reply_text("\n".join(lines))

async def clearalerts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alerts = load_alerts()
    alerts = [a for a in alerts if a["chat_id"] != update.effective_chat.id]
    save_alerts(alerts)
    await update.message.reply_text("All alerts cleared.")

def check_alerts_loop(application):
    while True:
        time.sleep(CHECK_INTERVAL)
        alerts = load_alerts()
        changed = False
        for a in alerts:
            if a["triggered"]:
                continue
            price = get_price(a["symbol"])
            if price is None:
                continue
            hit = (a["direction"] == "above" and price >= a["target"]) or \
                  (a["direction"] == "below" and price <= a["target"])
            if hit:
                a["triggered"] = True
                changed = True
                text = f"ALERT! {a['symbol']} reached ${a['target']:,.4f}\nCurrent: ${price:,.4f}"
                try:
                    application.bot.send_message(chat_id=a["chat_id"], text=text)
                except Exception as e:
                    print("Send failed:", e)
        if changed:
            save_alerts(alerts)

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Set BOT_TOKEN env variable first")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("setalert", setalert_cmd))
    app.add_handler(CommandHandler("myalerts", myalerts_cmd))
    app.add_handler(CommandHandler("clearalerts", clearalerts_cmd))
    checker = Thread(target=check_alerts_loop, args=(app,), daemon=True)
    checker.start()
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
