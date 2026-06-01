#!/usr/bin/env python3
"""XAU/USD AI Signal Bot — Faqat signallar, haiku model"""
import asyncio, logging, os
from datetime import datetime
import pytz
from dotenv import load_dotenv
load_dotenv()

from telegram import Bot
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from signal_engine import SignalEngine
from daily_report import DailyReport

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "8649043259:AAEpCO9rnT-wcSoxcaUkKdhw0qZcwy-X8qs")
CHAT_ID    = int(os.getenv("TELEGRAM_CHAT_ID", "-1003514927706"))
API_KEY    = os.getenv("ANTHROPIC_API_KEY", "")
TIMEZONE   = "Asia/Tashkent"
tz         = pytz.timezone(TIMEZONE)

bot          = Bot(token=BOT_TOKEN)
signal_eng   = SignalEngine(api_key=API_KEY)
daily_rep    = DailyReport()


def is_market_open():
    h = datetime.now(tz).hour
    return 5 <= h < 23


async def send(text: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Xabar xatosi: {e}")


def fmt_signal(r: dict) -> str:
    emoji = "🟢 BUY" if r["direction"] == "BUY" else "🔴 SELL"
    stars = "⭐" * r.get("strength_stars", 4)
    return (
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>🥇 XAU/USD · 5M SIGNAL</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"<b>Yo'nalish:</b>  {emoji}\n"
        f"<b>Kuch:</b>  {stars} ({r['strength']}%)\n\n"
        f"<b>📍 Kirish:</b>  <code>{r['entry_zone']}</code>\n\n"
        f"<b>🎯 Take Profit:</b>\n"
        f"   TP1 → <code>{r['tp1']}</code>  (+{r['tp1_pips']} pip)\n"
        f"   TP2 → <code>{r['tp2']}</code>  (+{r['tp2_pips']} pip)\n"
        f"   TP3 → <code>{r['tp3']}</code>  (+{r['tp3_pips']} pip)\n\n"
        f"<b>🛑 Stop Loss:</b>  <code>{r['stop_loss']}</code>  (-{r['sl_pips']} pip)\n\n"
        f"<b>⚠️ Risk:</b> {r['risk_level']}  |  <b>R:R</b> 1:{r['rr_ratio']}\n\n"
        f"<b>🔍 Tahlil:</b>\n<i>{r['analysis_summary']}</i>\n\n"
        f"<b>⏰</b> {r['timestamp']}\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<i>⚡ TP1/TP2 olganda SL ni bez ubitkaga oling!</i>"
    )


async def job_signal():
    if not is_market_open():
        return
    logger.info("Signal tekshirilmoqda...")
    result = await signal_eng.analyze()
    if result:
        daily_rep.add_signal(result)
        await send(fmt_signal(result))
        logger.info(f"✅ Signal: {result['direction']} {result['strength']}%")


async def job_tp_sl():
    updates = await signal_eng.check_open_trades()
    for upd in updates:
        await send(upd)


async def job_daily_report():
    await send(daily_rep.generate_report())
    daily_rep.reset()


async def main():
    logger.info(f"Bot ishga tushdi. CHAT_ID={CHAT_ID}")
    await send(
        "🤖 <b>XAU/USD AI Signal Bot — FAOL!</b>\n\n"
        "🎯 Har 5 daqiqada M5 signal tahlili\n"
        "⚡ Faqat ≥75% kuchli signallar\n"
        "⏰ Ish vaqti: 05:00–23:00 (Toshkent)\n"
        "📈 Kunlik hisobot: 23:00\n"
        "🔒 Private kanal | Kommentlar yopiq"
    )
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(job_signal,       "interval", minutes=5)
    scheduler.add_job(job_tp_sl,        "interval", minutes=2)
    scheduler.add_job(job_daily_report, "cron",     hour=23, minute=0)
    scheduler.start()
    logger.info("✅ Scheduler ishga tushdi")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
