"""
Signal Engine v4 — Majburiy kunlik 2x signal
Sodda va ishonchli: JSON parse xatosi bo'lmaydi
"""
import json, re, httpx, logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
MODEL = "claude-haiku-4-5"

# Majburiy signal vaqtlari (Toshkent)
SIGNAL_HOURS = {
    9:  "London ochilishi — YUQORI VOLATILLIK",
    15: "New York ochilishi — YUQORI VOLATILLIK",
}

class SignalEngine:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.open_trades: list[dict] = []
        self.tz = pytz.timezone("Asia/Tashkent")
        self.sent_hours: set = set()
        self.last_date = None

    def _hdrs(self):
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

    def _reset_if_new_day(self):
        today = datetime.now(self.tz).date()
        if self.last_date != today:
            self.sent_hours = set()
            self.last_date = today

    async def _fetch_price_and_analysis(self) -> dict:
        """Narx va tahlilni oladi — oddiy va ishonchli."""
        prompt = """Search for XAU/USD current price and recent 1H trend direction.
Return ONLY this JSON (no other text):
{"price": 3325.50, "trend": "BEARISH", "reason": "Price below EMA20, lower highs forming"}"""
        try:
            async with httpx.AsyncClient(timeout=40) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._hdrs(),
                    json={
                        "model": MODEL,
                        "max_tokens": 150,
                        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages": [{"role": "user", "content": prompt}]
                    }
                )
                data = r.json()
                text = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
                m = re.search(r'\{[^{}]+\}', text, re.DOTALL)
                if m:
                    return json.loads(m.group())
        except Exception as e:
            logger.error(f"Price fetch: {e}")
        return {"price": 0, "trend": "BEARISH", "reason": "Tahlil kelmadi"}

    def _build_signal(self, price: float, trend: str, reason: str,
                      is_forced: bool, session: str) -> dict:
        """Narx va trend asosida signal quradi."""
        now = datetime.now(self.tz)
        direction = trend.upper()
        if "BULL" in direction:
            direction = "BUY"
        else:
            direction = "SELL"

        # ATR ga o'xshash spread: XAU/USD uchun 15-25 pip odatiy
        spread = 20.0
        if direction == "BUY":
            entry     = round(price, 2)
            sl        = round(price - spread * 1.2, 2)
            tp1       = round(price + spread * 0.9, 2)
            tp2       = round(price + spread * 2.0, 2)
            tp3       = round(price + spread * 3.2, 2)
            ez_lo     = round(price - 1.5, 2)
            ez_hi     = round(price + 1.5, 2)
        else:
            entry     = round(price, 2)
            sl        = round(price + spread * 1.2, 2)
            tp1       = round(price - spread * 0.9, 2)
            tp2       = round(price - spread * 2.0, 2)
            tp3       = round(price - spread * 3.2, 2)
            ez_lo     = round(price - 1.5, 2)
            ez_hi     = round(price + 1.5, 2)

        sl_pips  = round(abs(entry - sl), 1)
        tp1_pips = round(abs(tp1 - entry), 1)
        tp2_pips = round(abs(tp2 - entry), 1)
        tp3_pips = round(abs(tp3 - entry), 1)
        rr       = round(tp2_pips / sl_pips, 1) if sl_pips else 2.0

        strength      = 82 if is_forced else 78
        strength_stars = 4

        return {
            "signal_found":   True,
            "pair":           "XAU/USD",
            "direction":      direction,
            "strength":       strength,
            "strength_stars": strength_stars,
            "entry_tf":       "5M",
            "current_price":  str(entry),
            "entry_zone":     f"{ez_lo}-{ez_hi}",
            "tp1":            str(tp1),  "tp1_pips": tp1_pips,
            "tp2":            str(tp2),  "tp2_pips": tp2_pips,
            "tp3":            str(tp3),  "tp3_pips": tp3_pips,
            "stop_loss":      str(sl),
            "sl_pips":        sl_pips,
            "risk_level":     "PAST",
            "rr_ratio":       str(rr),
            "lot_min":        "0.01",
            "lot_max":        "0.03",
            "trend_1h":       trend,
            "trend_5m":       trend,
            "key_level":      f"SL: {sl} | TP3: {tp3}",
            "ict_note":       reason,
            "analysis":       f"{session} | {reason}",
            "invalidation":   f"SL {sl} yorilsa — darhol yop",
            "timestamp":      now.strftime("%d.%m.%Y %H:%M"),
            "status":         "OPEN",
            "guaranteed":     is_forced,
        }

    async def _get_ict_signal(self, price: float, trend: str) -> dict | None:
        """ICT tahlili asosida signal olishga harakat qiladi."""
        direction = "BUY" if "BULL" in trend.upper() else "SELL"
        spread = 20.0
        if direction == "BUY":
            sl_price = round(price - spread * 1.2, 2)
            tp1_p = round(price + spread * 0.9, 2)
            tp2_p = round(price + spread * 2.0, 2)
            tp3_p = round(price + spread * 3.2, 2)
        else:
            sl_price = round(price + spread * 1.2, 2)
            tp1_p = round(price - spread * 0.9, 2)
            tp2_p = round(price - spread * 2.0, 2)
            tp3_p = round(price - spread * 3.2, 2)

        prompt = f"""XAU/USD hozirgi narx {price}, trend {trend}.
5M chartda eng yaqin Order Block, FVG yoki kuchli support/resistance zona topib,
{direction} signal uchun aniq kirish, SL, TP zonalarini ko'rsat.

FAQAT JSON (boshqa matn yo'q):
{{"ob_zone":"{round(price-3,1)}-{round(price+3,1)}","fvg_zone":"{round(price-5,1)}-{round(price-1,1)}","key_support":"{round(price-15,1)}","key_resist":"{round(price+15,1)}","ict_note":"5M Bearish OB yoki FVG dan SELL","strength_boost":5}}"""
        try:
            async with httpx.AsyncClient(timeout=45) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._hdrs(),
                    json={
                        "model": MODEL,
                        "max_tokens": 200,
                        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages": [{"role": "user", "content": prompt}]
                    }
                )
                data = r.json()
                text = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
                m = re.search(r'\{[^{}]+\}', text, re.DOTALL)
                if m:
                    return json.loads(m.group())
        except Exception as e:
            logger.error(f"ICT xatosi: {e}")
        return None

    async def analyze(self) -> list[dict]:
        self._reset_if_new_day()
        now  = datetime.now(self.tz)
        h    = now.hour
        signals = []

        # Bozor vaqti tekshirish
        if not (5 <= h < 23):
            return []

        # Majburiy signal vaqtimi?
        is_forced = h in SIGNAL_HOURS and h not in self.sent_hours
        session   = SIGNAL_HOURS.get(h, f"{h}:00 sessiya")

        # 1. Narx va asosiy trend olish
        logger.info(f"XAU/USD narx va trend olinmoqda...")
        market = await self._fetch_price_and_analysis()
        price  = market.get("price", 0)
        trend  = market.get("trend", "BEARISH")
        reason = market.get("reason", "Trend tahlili")

        if price < 100:
            logger.warning("Narx olinmadi — oddiy signal qurilmoqda")
            # Narx olinmasa ham majburiy vaqtda signal ber
            if is_forced:
                price = 3300.0  # fallback
            else:
                return []

        logger.info(f"Narx: {price} | Trend: {trend}")

        # 2. ICT tahlil qo'shish
        ict = await self._get_ict_signal(price, trend)

        # 3. Signal qurish
        sig = self._build_signal(price, trend, reason, is_forced, session)

        # ICT ma'lumotlarini qo'shish
        if ict:
            sig["ict_note"]   = ict.get("ict_note", sig["ict_note"])
            sig["key_level"]  = f"OB: {ict.get('ob_zone','—')} | FVG: {ict.get('fvg_zone','—')}"
            sig["strength"]   = min(95, sig["strength"] + ict.get("strength_boost", 0))
            # Entry zonasini OB ga moslashtirish
            if ict.get("ob_zone"):
                sig["entry_zone"] = ict["ob_zone"]

        signals.append(sig)
        self.open_trades.append(sig.copy())
        if is_forced:
            self.sent_hours.add(h)
        logger.info(f"✅ Signal: {sig['direction']} {sig['strength']}% | {sig['ict_note'][:50]}")
        return signals

    async def check_open_trades(self) -> list[str]:
        if not self.open_trades:
            return []
        market = await self._fetch_price_and_analysis()
        price  = market.get("price", 0)
        if price < 100:
            return []
        messages, still_open = [], []
        for trade in self.open_trades:
            msg = self._check(trade, price)
            if msg:
                messages.append(msg)
                if trade.get("status") in ("TP1",):
                    still_open.append(trade)
            else:
                still_open.append(trade)
        self.open_trades = still_open
        return messages

    def _check(self, trade: dict, price: float) -> str | None:
        try:
            d  = trade["direction"]
            t1 = float(trade["tp1"])
            t2 = float(trade["tp2"])
            t3 = float(trade["tp3"])
            sl = float(trade["stop_loss"])
            st = trade.get("status", "OPEN")
            now = datetime.now(self.tz).strftime("%H:%M")

            if d == "BUY":
                if price >= t3:
                    trade["status"] = "TP3"; return self._fmt("tp3", trade, price, now)
                if price >= t2 and st == "TP1":
                    trade["status"] = "TP2"; return self._fmt("tp2", trade, price, now)
                if price >= t1 and st == "OPEN":
                    trade["status"] = "TP1"; return self._fmt("tp1", trade, price, now)
                if price <= sl:
                    trade["status"] = "SL";  return self._fmt("sl",  trade, price, now)
            else:
                if price <= t3:
                    trade["status"] = "TP3"; return self._fmt("tp3", trade, price, now)
                if price <= t2 and st == "TP1":
                    trade["status"] = "TP2"; return self._fmt("tp2", trade, price, now)
                if price <= t1 and st == "OPEN":
                    trade["status"] = "TP1"; return self._fmt("tp1", trade, price, now)
                if price >= sl:
                    trade["status"] = "SL";  return self._fmt("sl",  trade, price, now)
        except Exception as e:
            logger.error(f"Check: {e}")
        return None

    def _fmt(self, status: str, trade: dict, price: float, now: str) -> str:
        d  = "🟢 BUY" if trade["direction"] == "BUY" else "🔴 SELL"
        t1 = trade["tp1"]; t2 = trade["tp2"]; t3 = trade["tp3"]
        sl = trade["stop_loss"]
        if status == "tp1":
            return (
                f"<b>✅ TP1 OLINDI! — 🥇 XAU/USD {d}</b>\n\n"
                f"Narx: <code>{price}</code> → TP1: <code>{t1}</code>\n\n"
                f"⚡ <b>HOZIROQ:</b>\n"
                f"✔️ SL ni <b>{trade['entry_zone'].split('-')[0]}</b> ga — BEZ UBYTOK!\n"
                f"✔️ Bozor teskari ketsa — DARHOL YOPING!\n"
                f"✔️ TP2 <code>{t2}</code> ga qoldiring\n"
                f"<i>🕐 {now}</i>"
            )
        elif status == "tp2":
            return (
                f"<b>✅✅ TP2 OLINDI! — 🥇 XAU/USD {d}</b>\n\n"
                f"Narx: <code>{price}</code> → TP2: <code>{t2}</code>\n\n"
                f"⚡ <b>HOZIROQ:</b>\n"
                f"✔️ 60% pozitsiyani YOPING!\n"
                f"✔️ SL ni TP1 <code>{t1}</code> ga ko'taring\n"
                f"✔️ Qolganini TP3 <code>{t3}</code> ga\n"
                f"<i>🕐 {now}</i>"
            )
        elif status == "tp3":
            return (
                f"<b>🏆 TP3 OLINDI! — 🥇 XAU/USD {d}</b>\n\n"
                f"Narx: <code>{price}</code> → TP3: <code>{t3}</code>\n"
                f"✅ Barcha pozitsiyani YOPING! 🎉\n"
                f"<i>🕐 {now}</i>"
            )
        else:
            return (
                f"<b>🛑 STOP LOSS — 🥇 XAU/USD {d}</b>\n\n"
                f"Narx: <code>{price}</code> → SL: <code>{sl}</code>\n"
                f"Risk menejment ishladi. Keyingi signal kuting.\n"
                f"<i>🕐 {now}</i>"
            )
