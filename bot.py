#!/usr/bin/env python3
"""
XAU/USD AI Signal Telegram Bot — To'liq versiya
"""
import asyncio
import logging
import os
from datetime import datetime
from io import BytesIO

import pytz
from dotenv import load_dotenv
load_dotenv()

from telegram import Bot, InputFile
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from signal_engine import SignalEngine
from daily_report import DailyReport
from news_engine import NewsEngine, MessageFormatter

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Sozlamalar ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8649043259:AAEpCO9rnT-wcSoxcaUkKdhw0qZcwy-X8qs")
# Kanal ID — private kanal: 🥇 XAU/USD AI Signal
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "-1003514927706")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
TIMEZONE           = "Asia/Tashkent"
MARKET_OPEN        = 5
MARKET_CLOSE       = 23
# ───────────────────────────────────────────────────────

# Chat ID ni int ga o'tkazish (muhim!)
try:
    CHAT_ID = int(TELEGRAM_CHAT_ID)
except:
    CHAT_ID = -1003514927706

logger.info(f"Bot sozlamalari: CHAT_ID={CHAT_ID}")

bot           = Bot(token=TELEGRAM_BOT_TOKEN)
signal_engine = SignalEngine(api_key=ANTHROPIC_API_KEY)
news_engine   = NewsEngine(api_key=ANTHROPIC_API_KEY)
daily_report  = DailyReport()
formatter     = MessageFormatter()
tz            = pytz.timezone(TIMEZONE)


def is_market_open() -> bool:
    now = datetime.now(tz)
    return MARKET_OPEN <= now.hour < MARKET_CLOSE


async def send_text(text: str):
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Xabar yuborildi (chat_id={CHAT_ID})")
    except Exception as e:
        logger.error(f"Xabar yuborishda xato (chat_id={CHAT_ID}): {e}")


async def send_with_image(text: str, svg_data: bytes | None):
    try:
        if svg_data:
            buf = BytesIO(svg_data)
            buf.name = "xauusd_analysis.svg"
            await bot.send_document(
                chat_id=CHAT_ID,
                document=InputFile(buf, filename="xauusd_analysis.svg"),
                caption=text[:1020],
                parse_mode=ParseMode.HTML
            )
        else:
            await send_text(text)
    except Exception as e:
        logger.error(f"Rasm yuborishda xato: {e}")
        await send_text(text)


def format_signal(r: dict) -> str:
    d_emoji = "🟢 BUY" if r["direction"] == "BUY" else "🔴 SELL"
    stars   = "⭐" * r.get("strength_stars", 4)
    return (
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>🥇 XAU/USD · 5M SIGNAL</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"<b>Yo'nalish:</b>  {d_emoji}\n"
        f"<b>Signal kuchi:</b>  {stars} ({r['strength']}%)\n\n"
        f"<b>📍 Kirish zonasi:</b>  <code>{r['entry_zone']}</code>\n\n"
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


# ── Scheduler joblar ────────────────────────────────────

async def job_signal():
    if not is_market_open():
        return
    logger.info("Signal tekshirilmoqda...")
    result = await signal_engine.analyze()
    if result:
        daily_report.add_signal(result)
        await send_text(format_signal(result))
        logger.info(f"✅ Signal: {result['direction']} {result['strength']}%")


async def job_tp_sl():
    updates = await signal_engine.check_open_trades()
    for upd in updates:
        await send_text(upd)


async def job_news():
    if not is_market_open():
        return
    logger.info("Yangilik olinmoqda...")
    try:
        news = await news_engine.get_gold_news()
        if news:
            text = formatter.format_news(news)
            img  = await news_engine.generate_image(news.get('image_prompt',''))
            await send_with_image(text, img)
            logger.info("✅ Yangilik yuborildi")
    except Exception as e:
        logger.error(f"Yangilik xatosi: {e}")


async def job_technical():
    if not is_market_open():
        return
    logger.info("Texnik tahlil bajarilmoqda...")
    try:
        ta = await news_engine.get_technical_analysis()
        if ta:
            text = formatter.format_technical(ta)
            img  = await news_engine.generate_image(ta.get('image_prompt','gold chart'))
            await send_with_image(text, img)
            logger.info("✅ Texnik tahlil yuborildi")
    except Exception as e:
        logger.error(f"Texnik tahlil xatosi: {e}")


async def job_fact():
    if not is_market_open():
        return
    logger.info("Fakt olinmoqda...")
    try:
        fact = await news_engine.get_gold_fact()
        if fact:
            text = formatter.format_fact(fact)
            img  = await news_engine.generate_image(fact.get('image_prompt','gold bars'))
            await send_with_image(text, img)
            logger.info("✅ Fakt yuborildi")
    except Exception as e:
        logger.error(f"Fakt xatosi: {e}")


async def job_daily_report():
    report = daily_report.generate_report()
    await send_text(report)
    daily_report.reset()


# ── Main ────────────────────────────────────────────────

async def main():
    logger.info(f"Bot ishga tushmoqda... CHAT_ID={CHAT_ID}")

    # Yoqilish xabari
    await send_text(
        "🤖 <b>XAU/USD AI Signal Bot — FAOL!</b>\n\n"
        "📋 <b>Jadval:</b>\n"
        "🎯 Signallar — har 5 daqiqada\n"
        "📰 Oltin yangiliklari — har 2 soatda\n"
        "📊 Texnik tahlil — har 3 soatda\n"
        "🎓 Qiziqarli faktlar — har 4 soatda\n"
        "📈 Kunlik hisobot — 23:00\n\n"
        "⏰ Ish vaqti: 05:00–23:00 (Toshkent)\n"
        "🔒 Kanal: Private | Kommentlar: Yopiq\n"
        "✅ <b>Hamma narsa tayyor!</b>"
    )

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(job_signal,       "interval", minutes=5)
    scheduler.add_job(job_tp_sl,        "interval", minutes=1)
    scheduler.add_job(job_news,         "cron", hour="6,8,10,12,14,16,18,20,22", minute=0)
    scheduler.add_job(job_technical,    "cron", hour="7,10,13,16,19,22", minute=15)
    scheduler.add_job(job_fact,         "cron", hour="9,13,17,21", minute=30)
    scheduler.add_job(job_daily_report, "cron", hour=23, minute=0)
    scheduler.start()

    logger.info("✅ Scheduler ishga tushdi")

    # Darhol birinchi texnik tahlil
    await asyncio.sleep(5)
    await job_technical()

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
