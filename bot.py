#!/usr/bin/env python3
"""XAU/USD Signal Bot — Kuniga kamida 2x signal kafolatlangan"""
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

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8649043259:AAEpCO9rnT-wcSoxcaUkKdhw0qZcwy-X8qs")
CHAT_ID   = int(os.getenv("TELEGRAM_CHAT_ID", "-1003514927706"))
API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
TIMEZONE  = "Asia/Tashkent"
tz        = pytz.timezone(TIMEZONE)

bot        = Bot(token=BOT_TOKEN)
signal_eng = SignalEngine(api_key=API_KEY)
daily_rep  = DailyReport()


def is_open() -> bool:
    return 5 <= datetime.now(tz).hour < 23


async def send(text: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Xabar: {e}")


def tf_icon(t: str) -> str:
    return "🟢" if "BULL" in t.upper() else "🔴" if "BEAR" in t.upper() else "🟡"


def fmt_signal(r: dict) -> str:
    emoji = "🟢 BUY" if r["direction"] == "BUY" else "🔴 SELL"
    stars = "⭐" * r.get("strength_stars", 4)
    tf    = r.get("entry_tf", "5M")
    t1h   = r.get("trend_1h", "—")
    t5m   = r.get("trend_5m", "—")
    guar  = "🔔 <b>KAFOLATLANGAN SIGNAL</b>\n" if r.get("guaranteed") else ""

    return (
        f"{guar}"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>🥇 XAU/USD · {tf} · SIGNAL</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"<b>Yo'nalish:</b> {emoji}\n"
        f"<b>Kuch:</b> {stars} {r['strength']}%\n\n"
        f"<b>📊 Trend:</b>\n"
        f"  1H: {tf_icon(t1h)} {t1h}  ·  5M: {tf_icon(t5m)} {t5m}\n\n"
        f"<b>📍 Hozirgi narx:</b> <code>{r.get('current_price','—')}</code>\n"
        f"<b>📍 Kirish zonasi:</b> <code>{r['entry_zone']}</code>\n\n"
        f"<b>🎯 Take Profit:</b>\n"
        f"   TP1 → <code>{r['tp1']}</code>  (+{r['tp1_pips']} pip)\n"
        f"   TP2 → <code>{r['tp2']}</code>  (+{r['tp2_pips']} pip)\n"
        f"   TP3 → <code>{r['tp3']}</code>  (+{r['tp3_pips']} pip)\n\n"
        f"<b>🛑 Stop Loss:</b> <code>{r['stop_loss']}</code>  (-{r['sl_pips']} pip)\n"
        f"<b>⚖️ R:R:</b> 1:{r['rr_ratio']}  ·  Risk: {r['risk_level']}\n\n"
        f"<b>📦 Lot hajmi:</b> {r.get('lot_min','0.01')} – {r.get('lot_max','0.03')} lot\n\n"
        f"<b>🏦 ICT:</b> <i>{r.get('ict_note','—')}</i>\n"
        f"<b>🔑 Kalit daraja:</b> <i>{r.get('key_level','—')}</i>\n\n"
        f"<b>🔍 Tahlil:</b>\n<i>{r.get('analysis','—')}</i>\n\n"
        f"<b>❌ Bekor:</b> <i>{r.get('invalidation','—')}</i>\n\n"
        f"<b>⏰</b> {r['timestamp']}\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<i>⚡ TP1 olgach — SL BEZ UBYTOKKA!\n"
        f"⚡ Bozor teskari ketsa — DARHOL YOPING!</i>"
    )


async def job_signal():
    if not is_open():
        return
    logger.info("Signal tekshirilmoqda...")
    signals = await signal_eng.analyze()
    for r in signals:
        daily_rep.add_signal(r)
        await send(fmt_signal(r))


async def job_tp_sl():
    for msg in await signal_eng.check_open_trades():
        await send(msg)


async def job_daily():
    await send(daily_rep.generate_report())
    daily_rep.reset()


async def main():
    logger.info(f"Bot ishga tushdi. CHAT_ID={CHAT_ID}")
    await send(
        "🤖 <b>XAU/USD Signal Bot — YANGILANDI!</b>\n\n"
        "📊 Juft: 🥇 XAU/USD\n"
        "⏱ Taymfreym: 1M / 5M\n"
        "📦 Lot: 0.01 – 0.03\n\n"
        "✅ <b>Kuniga KAMIDA 2 signal kafolatlangan:</b>\n"
        "   🔔 09:00 — London sessiyasi\n"
        "   🔔 15:00 — New York sessiyasi\n\n"
        "🔍 Har 5 daqiqada tahlil\n"
        "⚡ TP/SL hit xabarlari darhol\n"
        "⏰ 05:00–23:00 Toshkent"
    )
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(job_signal, "interval", minutes=5)
    scheduler.add_job(job_tp_sl,  "interval", minutes=2)
    scheduler.add_job(job_daily,  "cron", hour=23, minute=0)
    scheduler.start()
    logger.info("✅ Scheduler ishga tushdi")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
