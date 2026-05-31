#!/usr/bin/env python3
"""
XAU/USD AI Signal Telegram Bot
Har 5 daqiqada XAU/USD texnik tahlil qilib, kuchli signallar yuboradi.
"""

import asyncio
import logging
import os
from datetime import datetime, time as dtime
import pytz
from telegram import Bot
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from signal_engine import SignalEngine
from daily_report import DailyReport

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== SOZLAMALAR =====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY_HERE")
TIMEZONE           = "Asia/Tashkent"   # UTC+5
MARKET_OPEN_HOUR   = 5                 # 05:00
MARKET_CLOSE_HOUR  = 23                # 23:00
SIGNAL_INTERVAL    = 5                 # daqiqa
# ======================================================

bot          = Bot(token=TELEGRAM_BOT_TOKEN)
signal_engine = SignalEngine(api_key=ANTHROPIC_API_KEY)
daily_report  = DailyReport()
tz            = pytz.timezone(TIMEZONE)


def is_market_open() -> bool:
    now = datetime.now(tz)
    return MARKET_OPEN_HOUR <= now.hour < MARKET_CLOSE_HOUR


async def send_message(text: str):
    try:
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Xabar yuborishda xato: {e}")


async def check_and_send_signal():
    """Har 5 daqiqada chaqiriladi."""
    if not is_market_open():
        return

    logger.info("Signal tekshirilmoqda...")
    result = await signal_engine.analyze()

    if result is None:
        logger.info("Signal kuchsiz — o'tkazib yuborildi.")
        return

    # Signalni saqlash (kunlik hisobot uchun)
    daily_report.add_signal(result)

    msg = format_signal_message(result)
    await send_message(msg)
    logger.info(f"Signal yuborildi: {result['direction']} | Kuch: {result['strength']}")


async def check_tp_sl_updates():
    """Ochiq signallarning TP/SL holatini tekshiradi."""
    updates = await signal_engine.check_open_trades()
    for upd in updates:
        await send_message(upd)


async def send_daily_report():
    """Har kuni soat 23:00 da yuboriladi."""
    report = daily_report.generate_report()
    await send_message(report)
    daily_report.reset()


def format_signal_message(signal: dict) -> str:
    direction_emoji = "🟢 BUY" if signal["direction"] == "BUY" else "🔴 SELL"
    strength_bar    = "⭐" * signal["strength_stars"]

    msg = (
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>🥇 XAU/USD · 5M SIGNAL</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"<b>Yo'nalish:</b>  {direction_emoji}\n"
        f"<b>Signal kuchi:</b>  {strength_bar} ({signal['strength']}%)\n\n"
        f"<b>📍 Kirish zonasi:</b>  <code>{signal['entry_zone']}</code>\n\n"
        f"<b>🎯 Take Profit:</b>\n"
        f"   TP1 → <code>{signal['tp1']}</code>  (+{signal['tp1_pips']} pip)\n"
        f"   TP2 → <code>{signal['tp2']}</code>  (+{signal['tp2_pips']} pip)\n"
        f"   TP3 → <code>{signal['tp3']}</code>  (+{signal['tp3_pips']} pip)\n\n"
        f"<b>🛑 Stop Loss:</b>  <code>{signal['stop_loss']}</code>  (-{signal['sl_pips']} pip)\n\n"
        f"<b>⚠️ Risk darajasi:</b>  {signal['risk_level']}\n"
        f"<b>📊 R:R nisbat:</b>  1:{signal['rr_ratio']}\n\n"
        f"<b>🔍 Tahlil asosi:</b>\n"
        f"<i>{signal['analysis_summary']}</i>\n\n"
        f"<b>⏰ Vaqt:</b>  {signal['timestamp']}\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<i>⚡ TP1 yoki TP2 olinganda bez ubitkaga qo'ying!</i>"
    )
    return msg


async def main():
    logger.info("XAU/USD AI Signal Bot ishga tushmoqda...")

    # Boshlang'ich xabar
    start_msg = (
        "🤖 <b>XAU/USD AI Signal Bot yoqildi!</b>\n\n"
        "📋 <b>Sozlamalar:</b>\n"
        f"• Taymfreym: 5 daqiqa\n"
        f"• Bozor vaqti: {MARKET_OPEN_HOUR}:00 – {MARKET_CLOSE_HOUR}:00 (Toshkent vaqti)\n"
        f"• Signal intervali: har {SIGNAL_INTERVAL} daqiqada\n"
        f"• Faqat kuchli signallar (≥75%) yuboriladi\n\n"
        "✅ Bot tayyor. Signallar kutilmoqda..."
    )
    await send_message(start_msg)

    # Scheduler sozlash
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Har 5 daqiqada signal tekshirish
    scheduler.add_job(
        check_and_send_signal,
        "interval",
        minutes=SIGNAL_INTERVAL,
        id="signal_check"
    )

    # Har 1 daqiqada TP/SL holat tekshirish
    scheduler.add_job(
        check_tp_sl_updates,
        "interval",
        minutes=1,
        id="tp_sl_check"
    )

    # Har kuni soat 23:00 da hisobot
    scheduler.add_job(
        send_daily_report,
        "cron",
        hour=23,
        minute=0,
        id="daily_report"
    )

    scheduler.start()
    logger.info("Scheduler ishga tushdi.")

    # Botni doimiy ishlatish
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    asyncio.run(main())
