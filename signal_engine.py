"""
Signal Engine — Haiku model, arzon, tez
"""
import json, re, httpx, logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# Arzon model — Haiku (Sonnet dan 10x arzon)
MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """Sen XAU/USD M5 texnik tahlilchisan. Web search bilan hozirgi narx va indikatorlarni topib, FAQAT JSON qaytargin.

Signal mezonlari (barchasi kerak):
- RSI, MACD, EMA, Bollinger, Stochastic bir yo'nalishda
- Faqat 75%+ kuchli signal bering
- Trend yo'nalishiga mos bo'lsin

Kuchli signal topilsa:
{"signal_found":true,"direction":"BUY","strength":82,"strength_stars":4,"entry_zone":"3320.00-3322.00","tp1":"3330.00","tp1_pips":30,"tp2":"3342.00","tp2_pips":60,"tp3":"3358.00","tp3_pips":110,"stop_loss":"3308.00","sl_pips":24,"risk_level":"PAST","rr_ratio":"2.5","analysis_summary":"RSI 28 oversold, MACD bullish cross, EMA50 support","invalidation":"3308 dan past tushsa"}

Signal yo'q bo'lsa:
{"signal_found":false,"reason":"Sabab"}

FAQAT JSON, hech qanday matn yo'q."""


class SignalEngine:
    def __init__(self, api_key: str):
        self.api_key  = api_key
        self.open_trades = []
        self.tz = pytz.timezone("Asia/Tashkent")

    def _hdrs(self):
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

    def _parse(self, text: str) -> dict | None:
        clean = re.sub(r'```json|```', '', text).strip()
        m = re.search(r'\{.*\}', clean, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group())
        except Exception:
            return None

    async def analyze(self) -> dict | None:
        try:
            now = datetime.now(self.tz)
            h   = now.hour
            session = (
                "London ochilishi" if 5 <= h < 10 else
                "London+NY overlap (eng faol)" if 10 <= h < 15 else
                "New York" if 15 <= h < 19 else
                "NY/Osiyo"
            )
            user_msg = (
                f"Vaqt: {now.strftime('%d.%m.%Y %H:%M')} Toshkent | Sessiya: {session}\n"
                f"Web search bilan hozirgi XAU/USD M5 narxi va indikatorlarni topib tahlil qil. FAQAT JSON."
            )
            async with httpx.AsyncClient(timeout=50) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._hdrs(),
                    json={
                        "model": MODEL,
                        "max_tokens": 600,
                        "system": SYSTEM_PROMPT,
                        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages": [{"role": "user", "content": user_msg}]
                    }
                )
                r.raise_for_status()
                data = r.json()

            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            result = self._parse(text)

            if not result or not result.get("signal_found"):
                logger.info(f"Signal yo'q: {result.get('reason','') if result else 'parse xatosi'}")
                return None
            if result.get("strength", 0) < 75:
                return None

            result["timestamp"] = now.strftime("%d.%m.%Y %H:%M")
            result["status"]    = "OPEN"
            self.open_trades.append(result.copy())
            return result

        except Exception as e:
            logger.error(f"Tahlil xatosi: {e}")
            return None

    async def check_open_trades(self) -> list[str]:
        """Ochiq sdelkalarni narx bilan tekshiradi (arzon: faqat narx so'raydi)."""
        if not self.open_trades:
            return []

        # Hozirgi narxni olish (1 ta kichik so'rov)
        current_price = await self._get_current_price()
        if not current_price:
            return []

        messages = []
        closed   = []

        for trade in self.open_trades:
            msg = self._check_price(trade, current_price)
            if msg:
                messages.append(msg)
                closed.append(trade)

        for t in closed:
            self.open_trades.remove(t)

        return messages

    async def _get_current_price(self) -> float | None:
        """Web search bilan hozirgi XAU/USD narxini oladi."""
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._hdrs(),
                    json={
                        "model": MODEL,
                        "max_tokens": 50,
                        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages": [{"role": "user", "content":
                            "XAU/USD current price right now. Reply ONLY with the number, e.g.: 3325.50"}]
                    }
                )
                data = r.json()
                text = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
                m = re.search(r'\d{3,4}\.?\d{0,2}', text)
                return float(m.group()) if m else None
        except Exception as e:
            logger.error(f"Narx olish xatosi: {e}")
            return None

    def _check_price(self, trade: dict, price: float) -> str | None:
        """Narxni TP/SL bilan solishtiradi — AI siz."""
        try:
            direction = trade["direction"]
            tp1 = float(trade["tp1"])
            tp2 = float(trade["tp2"])
            sl  = float(trade["stop_loss"])
            entry_str = trade["entry_zone"].split("-")[0]
            entry = float(entry_str)

            now = datetime.now(self.tz).strftime("%H:%M")

            if direction == "BUY":
                if price >= tp2:
                    trade["status"] = "TP2"
                    return self._fmt_update(trade, "tp2_hit", price, now)
                if price >= tp1:
                    trade["status"] = "TP1"
                    return self._fmt_update(trade, "tp1_hit", price, now)
                if price <= sl:
                    trade["status"] = "SL"
                    return self._fmt_update(trade, "sl_hit", price, now)
            else:  # SELL
                if price <= tp2:
                    trade["status"] = "TP2"
                    return self._fmt_update(trade, "tp2_hit", price, now)
                if price <= tp1:
                    trade["status"] = "TP1"
                    return self._fmt_update(trade, "tp1_hit", price, now)
                if price >= sl:
                    trade["status"] = "SL"
                    return self._fmt_update(trade, "sl_hit", price, now)
        except Exception as e:
            logger.error(f"Narx tekshirish xatosi: {e}")
        return None

    def _fmt_update(self, trade: dict, status: str, price: float, now: str) -> str:
        d = "🟢 BUY" if trade["direction"] == "BUY" else "🔴 SELL"
        if status == "tp1_hit":
            return (
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>✅ TP1 OLINDI!</b>  {d}\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                f"Narx: <code>{price}</code>  →  TP1: <code>{trade['tp1']}</code>\n\n"
                f"💡 <b>TAVSIYA:</b>\n"
                f"✔️ SL ni kirish nuqtasiga (BEZ UBYTOK) oling!\n"
                f"✔️ Qolgan pozitsiyani TP2/TP3 ga qoldiring.\n\n"
                f"<i>🕐 {now}</i>"
            )
        elif status == "tp2_hit":
            return (
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>✅✅ TP2 OLINDI!</b>  {d}\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                f"Narx: <code>{price}</code>  →  TP2: <code>{trade['tp2']}</code>\n\n"
                f"💡 <b>TAVSIYA:</b>\n"
                f"✔️ Pozitsiyaning yarmi yopilsin!\n"
                f"✔️ SL ni TP1 darajasiga ko'taring.\n"
                f"✔️ Qolganini TP3 ga qoldiring.\n\n"
                f"<i>🕐 {now}</i>"
            )
        else:  # sl_hit
            return (
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>🛑 STOP LOSS URILDI!</b>  {d}\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                f"Narx: <code>{price}</code>  →  SL: <code>{trade['stop_loss']}</code>\n\n"
                f"<i>Risk menejment to'g'ri ishladi. Keyingi signal kuting.</i>\n\n"
                f"<i>🕐 {now}</i>"
            )
