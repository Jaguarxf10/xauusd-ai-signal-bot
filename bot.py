#!/usr/bin/env python3
"""ICT Multi-Pair Signal Bot — XAU/USD, BTC/USDT, EUR/USD"""
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
PEMOJI     = {"XAU/USD": "🥇", "BTC/USDT": "₿", "EUR/USD": "💶"}


def is_open() -> bool:
    return 5 <= datetime.now(tz).hour < 23


async def send(text: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Xabar: {e}")


def tf_icon(t: str) -> str:
    t = t.upper()
    return "🟢" if "BULL" in t else "🔴" if "BEAR" in t else "🟡"


def fmt_signal(r: dict) -> str:
    emoji = "🟢 BUY" if r["direction"] == "BUY" else "🔴 SELL"
    stars = "⭐" * r.get("strength_stars", 4)
    pair  = r.get("pair", "XAU/USD")
    pe    = PEMOJI.get(pair, "📊")
    tf    = r.get("entry_tf", "5M")

    t1d   = r.get("trend_1d",  "—")
    t4h   = r.get("trend_4h",  "—")
    t1h   = r.get("trend_1h",  "—")
    t30m  = r.get("trend_30m", "—")

    ict   = r.get("ict_setup",        "—")
    ob    = r.get("ob_zone",          "—")
    fvg   = r.get("fvg_zone",         "—")
    liq   = r.get("liquidity",        "—")
    bos   = r.get("bos_choch",        "—")
    pd    = r.get("premium_discount", "—")

    return (
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>{pe} {pair} · {tf} · ICT SIGNAL</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"<b>Yo'nalish:</b> {emoji}\n"
        f"<b>Ishonchlilik:</b> {stars} {r['strength']}%\n\n"
        f"<b>📊 Multi-TF Trend:</b>\n"
        f"  1D {tf_icon(t1d)}{t1d}  ·  4H {tf_icon(t4h)}{t4h}\n"
        f"  1H {tf_icon(t1h)}{t1h}  ·  30M {tf_icon(t30m)}{t30m}\n\n"
        f"<b>🏦 ICT Setup:</b> <i>{ict}</i>\n\n"
        f"<b>📦 Order Block:</b> <code>{ob}</code>\n"
        f"<b>🌀 FVG zona:</b> <code>{fvg}</code>\n"
        f"<b>💧 Likvidlik:</b> <i>{liq}</i>\n"
        f"<b>🔓 BOS/CHoCH:</b> <i>{bos}</i>\n"
        f"<b>📐 Premium/Discount:</b> <i>{pd}</i>\n\n"
        f"<b>📍 Kirish TF:</b> {tf}\n"
        f"<b>📍 Kirish narxi:</b> <code>{r.get('entry_price', r['entry_zone'])}</code>\n"
        f"<b>📍 Kirish zonasi:</b> <code>{r['entry_zone']}</code>\n\n"
        f"<b>🎯 Take Profit:</b>\n"
        f"   TP1 → <code>{r['tp1']}</code>  (+{r['tp1_pips']} pip)\n"
        f"   TP2 → <code>{r['tp2']}</code>  (+{r['tp2_pips']} pip)\n"
        f"   TP3 → <code>{r['tp3']}</code>  (+{r['tp3_pips']} pip)\n\n"
        f"<b>🛑 Stop Loss:</b> <code>{r['stop_loss']}</code>  (-{r['sl_pips']} pip)\n"
        f"<b>⚖️ Risk/Reward:</b> 1:{r['rr_ratio']}  |  {r['risk_level']}\n\n"
        f"<b>🔍 Tahlil:</b>\n<i>{r.get('analysis','—')}</i>\n\n"
        f"<b>❌ Bekor holat:</b> <i>{r.get('invalidation','—')}</i>\n\n"
        f"<b>⏰</b> {r['timestamp']}\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<i>⚡ TP1 olgach → SL BEZ UBYTOKKA!\n"
        f"⚡ Bozor qarshiga o'zgarsa → DARHOL YOPING!</i>"
    )


async def job_signal():
    if not is_open():
        return
    logger.info("ICT tahlil boshlandi (3 juft)...")
    signals = await signal_eng.analyze()
    for r in signals:
        daily_rep.add_signal(r)
        await send(fmt_signal(r))
        logger.info(f"✅ {r.get('pair')} {r['direction']} {r['strength']}%")


async def job_tp_sl():
    for msg in await signal_eng.check_open_trades():
        await send(msg)


async def job_daily():
    await send(daily_rep.generate_report())
    daily_rep.reset()


async def main():
    logger.info(f"Bot ishga tushdi. CHAT_ID={CHAT_ID}")
    await send(
        "🤖 <b>ICT AI Signal Bot — FAOL!</b>\n\n"
        "📊 <b>Juftlar:</b> 🥇 XAU/USD · ₿ BTC/USDT · 💶 EUR/USD\n\n"
        "🏦 <b>ICT Konseptlar:</b>\n"
        "  📦 Order Blocks (OB)\n"
        "  🌀 Fair Value Gaps (FVG/IFVG)\n"
        "  💧 Liquidity Zones (BSL/SSL)\n"
        "  🔓 BOS · CHoCH · MSS\n"
        "  📐 Premium/Discount Zones\n"
        "  🎯 OTE (Optimal Trade Entry)\n\n"
        "🔍 <b>Trend:</b> 1D → 4H → 1H → 30M\n"
        "⚡ <b>Kirish:</b> 15M / 5M / 1M\n"
        "✅ <b>Filtr:</b> 75%+ · Barcha TF mos · R:R ≥ 1:2\n\n"
        "⏰ Har 5 daqiqada · 05:00–23:00 Toshkent"
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
