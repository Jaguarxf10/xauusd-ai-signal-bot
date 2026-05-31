#!/usr/bin/env python3
"""
XAU/USD AI Signal Telegram Bot
- Signallar (M5 texnik tahlil)
- Oltin yangiliklari (AI rasm bilan)
- Texnik tahlil hisobotlari
- Qiziqarli faktlar
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

# ── Sozlamalar ──────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
TIMEZONE           = "Asia/Tashkent"
MARKET_OPEN        = 5
MARKET_CLOSE       = 23
# ────────────────────────────────────────────────────────

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
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Xabar yuborishda xato: {e}")


async def send_with_image(text: str, svg_data: bytes | None):
    """SVG yoki matn yuboradi."""
    try:
        if svg_data:
            # SVG ni to'g'ridan-to'g'ri document sifatida yuborish
            buf = BytesIO(svg_data)
            buf.name = "xauusd_analysis.svg"
            await bot.send_document(
                chat_id=TELEGRAM_CHAT_ID,
                document=InputFile(buf, filename="xauusd_analysis.svg"),
                caption=text,
                parse_mode=ParseMode.HTML
            )
        else:
            await send_text(text)
    except Exception as e:
        logger.error(f"Rasm yuborishda xato: {e}")
        await send_text(text)


def format_signal(result: dict) -> str:
    d_emoji = "🟢 BUY" if result["direction"] == "BUY" else "🔴 SELL"
    stars   = "⭐" * result.get("strength_stars", 4)
    return (
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>🥇 XAU/USD · 5M SIGNAL</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"<b>Yo'nalish:</b>  {d_emoji}\n"
        f"<b>Signal kuchi:</b>  {stars} ({result['strength']}%)\n\n"
        f"<b>📍 Kirish zonasi:</b>  <code>{result['entry_zone']}</code>\n\n"
        f"<b>🎯 Take Profit:</b>\n"
        f"   TP1 → <code>{result['tp1']}</code>  (+{result['tp1_pips']} pip)\n"
        f"   TP2 → <code>{result['tp2']}</code>  (+{result['tp2_pips']} pip)\n"
        f"   TP3 → <code>{result['tp3']}</code>  (+{result['tp3_pips']} pip)\n\n"
        f"<b>🛑 Stop Loss:</b>  <code>{result['stop_loss']}</code>  (-{result['sl_pips']} pip)\n\n"
        f"<b>⚠️ Risk darajasi:</b>  {result['risk_level']}\n"
        f"<b>📊 R:R nisbat:</b>  1:{result['rr_ratio']}\n\n"
        f"<b>🔍 Tahlil asosi:</b>\n<i>{result['analysis_summary']}</i>\n\n"
        f"<b>⏰ Vaqt:</b>  {result['timestamp']}\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<i>⚡ TP1/TP2 olganda SL ni bez ubitkaga oling!</i>"
    )


# ─────────────────────────────────────────────
# SCHEDULER JOBLAR
# ─────────────────────────────────────────────

async def job_signal():
    """Har 5 daqiqada signal tekshirish."""
    if not is_market_open():
        return
    logger.info("Signal tekshirilmoqda...")
    result = await signal_engine.analyze()
    if result:
        daily_report.add_signal(result)
        await send_text(format_signal(result))
        logger.info(f"Signal: {result['direction']} {result['strength']}%")


async def job_tp_sl():
    """Har 1 daqiqada TP/SL holat tekshirish."""
    updates = await signal_engine.check_open_trades()
    for upd in updates:
        await send_text(upd)


async def job_news():
    """Har 2 soatda oltin yangiligi (bozor vaqtida)."""
    if not is_market_open():
        return
    logger.info("Yangilik olinmoqda...")
    try:
        news = await news_engine.get_gold_news()
        if news:
            text = formatter.format_news(news)
            img_prompt = news.get('image_prompt', '')
            img = await news_engine.generate_image(img_prompt) if img_prompt else None
            await send_with_image(text, img)
            logger.info("Yangilik yuborildi")
    except Exception as e:
        logger.error(f"Yangilik xatosi: {e}")


async def job_technical():
    """Har 3 soatda texnik tahlil."""
    if not is_market_open():
        return
    logger.info("Texnik tahlil bajarilmoqda...")
    try:
        ta = await news_engine.get_technical_analysis()
        if ta:
            text = formatter.format_technical(ta)
            img = await news_engine.generate_image(ta.get('image_prompt', 'gold chart'))
            await send_with_image(text, img)
            logger.info("Texnik tahlil yuborildi")
    except Exception as e:
        logger.error(f"Texnik tahlil xatosi: {e}")


async def job_fact():
    """Har 4 soatda qiziqarli oltin fakti."""
    if not is_market_open():
        return
    logger.info("Fakt olinmoqda...")
    try:
        fact = await news_engine.get_gold_fact()
        if fact:
            text = formatter.format_fact(fact)
            img = await news_engine.generate_image(fact.get('image_prompt', 'gold bars'))
            await send_with_image(text, img)
            logger.info("Fakt yuborildi")
    except Exception as e:
        logger.error(f"Fakt xatosi: {e}")


async def job_daily_report():
    """Har kuni 23:00 da kunlik hisobot."""
    report = daily_report.generate_report()
    await send_text(report)
    daily_report.reset()


# ─────────────────────────────────────────────
# ASOSIY FUNKSIYA
# ─────────────────────────────────────────────

async def main():
    logger.info("XAU/USD AI Signal Bot ishga tushmoqda...")

    # Yoqilish xabari
    await send_text(
        "🤖 <b>XAU/USD AI Signal Bot yoqildi!</b>\n\n"
        "📋 <b>Nima beriladi:</b>\n"
        "🎯 M5 savdo signallari (har 5 daqiqada)\n"
        "📰 Oltin yangiliklari + rasm (har 2 soatda)\n"
        "📊 Texnik tahlil hisoboti (har 3 soatda)\n"
        "🎓 Qiziqarli faktlar (har 4 soatda)\n"
        "📈 Kunlik hisobot (har kuni 23:00)\n\n"
        "⏰ <b>Ish vaqti:</b> 05:00–23:00 (Toshkent)\n"
        "🔒 <b>Kirish:</b> Faqat taklif bilan\n"
        "✅ <b>Bot tayyor!</b>"
    )

    # Scheduler
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Har 5 daqiqada signal
    scheduler.add_job(job_signal,       "interval", minutes=5,  id="signal")
    # Har 1 daqiqada TP/SL
    scheduler.add_job(job_tp_sl,        "interval", minutes=1,  id="tp_sl")
    # Har 2 soatda yangilik (bozor vaqtida: 6, 8, 10, 12, 14, 16, 18, 20, 22)
    scheduler.add_job(job_news,         "cron",     hour="6,8,10,12,14,16,18,20,22", minute=0, id="news")
    # Har 3 soatda texnik tahlil (7, 10, 13, 16, 19, 22)
    scheduler.add_job(job_technical,    "cron",     hour="7,10,13,16,19,22", minute=15, id="technical")
    # Har 4 soatda fakt (9, 13, 17, 21)
    scheduler.add_job(job_fact,         "cron",     hour="9,13,17,21", minute=30, id="fact")
    # Har kuni 23:00 hisobot
    scheduler.add_job(job_daily_report, "cron",     hour=23, minute=0, id="daily_report")

    scheduler.start()
    logger.info("✅ Scheduler ishga tushdi. Bot tayyor.")

    # Birinchi texnik tahlilni darhol yuborish
    await asyncio.sleep(10)
    await job_technical()

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    asyncio.run(main())
