"""
Signal Engine — Kuniga kamida 2x signal kafolatlangan
XAU/USD asosiy, BTC va EUR qo'shimcha
1M/5M timeframe, 0.01-0.03 lot uchun
"""
import json, re, httpx, logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
MODEL = "claude-haiku-4-5"

# Kuniga 2 ta majburiy signal vaqtlari (London va NY ochilish)
GUARANTEED_HOURS = [9, 15]   # 09:00 va 15:00 Toshkent (London va NY)

SYSTEM_SIGNAL = """Sen professional XAU/USD treyderi va texnik tahlilchisan.
Web search bilan HOZIRGI XAU/USD narxini topib, ALBATTA signal ber.

TAHLIL QOIDALARI:
1. Hozirgi narx, 1M va 5M svichalarni ko'r
2. RSI, MACD, EMA9/21, Bollinger Bands holatini baholayla
3. Eng yaqin support va resistance darajalarni topgil
4. ICT: eng yaqin OB, FVG, yoki likvidlik zonasini topgil
5. ALBATTA yo'nalish tanlaysa: BUY yoki SELL

LOT HAJMI UCHUN SL/TP HISOBLASH:
- 0.01-0.03 lot uchun SL 15-25 pip, TP1 15-20 pip, TP2 30-40 pip, TP3 50-70 pip
- XAU/USD uchun 1 pip = $0.01 (0.01 lot da), $0.03 (0.03 lot da)
- Stop Loss maksimal $3-8 bo'lsin

FAQAT JSON (hech qanday matn yo'q):
{"signal_found":true,"pair":"XAU/USD","direction":"BUY","strength":82,"strength_stars":4,"entry_tf":"5M","current_price":"3325.50","entry_zone":"3323.00-3326.00","tp1":"3335.00","tp1_pips":18,"tp2":"3348.00","tp2_pips":35,"tp3":"3365.00","tp3_pips":55,"stop_loss":"3315.00","sl_pips":20,"risk_level":"PAST","rr_ratio":"2.1","lot_min":"0.01","lot_max":"0.03","trend_1h":"BULLISH","trend_5m":"BULLISH","key_level":"Support 3320, Resistance 3340","ict_note":"5M Bullish OB da narx, FVG 3318-3322","analysis":"RSI 42 supportdan qaytdi, MACD bullish cross, EMA9 EMA21 ustida, London sessiya boshlanishi","invalidation":"3315 yorilsa — yop"}"""

SYSTEM_GUARANTEED = """Sen XAU/USD bo'yicha professional treydersan.
Web search bilan HOZIRGI narxni topib, MAJBURIY RAVISHDA signal ber.
Bozor qanday bo'lmasin — eng kuchli yo'nalishni topib signal ber.

ALBATTA signal ber. "Signal yo'q" deb bo'lmaydi.
Hozirgi momentda qaysi yo'nalish kuchliroq bo'lsa — shu yo'nalishda signal ber.

FAQAT JSON:
{"signal_found":true,"pair":"XAU/USD","direction":"BUY","strength":80,"strength_stars":4,"entry_tf":"5M","current_price":"3325.50","entry_zone":"3323.00-3326.00","tp1":"3335.00","tp1_pips":18,"tp2":"3348.00","tp2_pips":35,"tp3":"3365.00","tp3_pips":55,"stop_loss":"3315.00","sl_pips":20,"risk_level":"PAST","rr_ratio":"2.1","lot_min":"0.01","lot_max":"0.03","trend_1h":"BULLISH","trend_5m":"BULLISH","key_level":"Support 3320, Resistance 3340","ict_note":"Kuchli support zona","analysis":"Hozirgi bozor tahlili asosida signal","invalidation":"SL yorilsa — yop"}"""


class SignalEngine:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.open_trades: list[dict] = []
        self.tz = pytz.timezone("Asia/Tashkent")
        self.today_signals = 0          # Bugungi signallar soni
        self.last_signal_date = None    # Oxirgi signal sanasi
        self.guaranteed_sent = set()    # Kafolatlangan signallar yuborilgan soatlar

    def _hdrs(self):
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

    def _reset_daily(self):
        today = datetime.now(self.tz).date()
        if self.last_signal_date != today:
            self.today_signals = 0
            self.guaranteed_sent = set()
            self.last_signal_date = today

    def _parse(self, text: str) -> dict | None:
        clean = re.sub(r'```json|```', '', text).strip()
        m = re.search(r'\{.*\}', clean, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group())
        except Exception:
            return None

    async def _call_api(self, system: str, user: str) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._hdrs(),
                    json={
                        "model": MODEL,
                        "max_tokens": 700,
                        "system": system,
                        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages": [{"role": "user", "content": user}]
                    }
                )
                r.raise_for_status()
                data = r.json()
            text = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
            return self._parse(text)
        except Exception as e:
            logger.error(f"API xatosi: {e}")
            return None

    async def analyze(self) -> list[dict]:
        """Asosiy signal tekshirish — har 5 daqiqada."""
        self._reset_daily()
        now = datetime.now(self.tz)
        h = now.hour
        signals = []

        # Kafolatlangan signal vaqtlari
        is_guaranteed_time = h in GUARANTEED_HOURS and h not in self.guaranteed_sent

        session = (
            "London ochilishi — YUQORI VOLATILLIK" if 5 <= h < 10 else
            "London+NY — ENG FAOL SESSIYA" if 10 <= h < 15 else
            "New York — YUQORI VOLATILLIK" if 15 <= h < 19 else
            "Kech sessiya"
        )

        user_msg = (
            f"Vaqt: {now.strftime('%d.%m.%Y %H:%M')} | {session}\n"
            f"XAU/USD hozirgi narxini web searchdan topib, 1M va 5M texnik tahlil qil.\n"
            f"RSI, MACD, EMA9/21, Bollinger, support/resistance, ICT (OB, FVG) ni baholayla.\n"
            f"0.01-0.03 lot uchun signal ber. FAQAT JSON."
        )

        if is_guaranteed_time:
            # Kafolatlangan vaqtda — albatta signal
            logger.info(f"⏰ Kafolatlangan signal vaqti: {h}:00")
            system = SYSTEM_GUARANTEED
        else:
            system = SYSTEM_SIGNAL

        result = await self._call_api(system, user_msg)

        if result and result.get("signal_found"):
            result["timestamp"] = now.strftime("%d.%m.%Y %H:%M")
            result["status"] = "OPEN"
            result["guaranteed"] = is_guaranteed_time
            self.open_trades.append(result.copy())
            signals.append(result)
            self.today_signals += 1
            if is_guaranteed_time:
                self.guaranteed_sent.add(h)
            logger.info(f"✅ XAU/USD signal: {result['direction']} {result['strength']}%")
        elif is_guaranteed_time:
            # Kafolatlangan vaqtda signal kelmasa — qayta urinish
            logger.info("Kafolatlangan signal: qayta urinish...")
            result2 = await self._call_api(SYSTEM_GUARANTEED, user_msg)
            if result2 and result2.get("signal_found"):
                result2["timestamp"] = now.strftime("%d.%m.%Y %H:%M")
                result2["status"] = "OPEN"
                result2["guaranteed"] = True
                self.open_trades.append(result2.copy())
                signals.append(result2)
                self.today_signals += 1
                self.guaranteed_sent.add(h)
                logger.info(f"✅ Kafolatlangan signal: {result2['direction']} {result2['strength']}%")

        return signals

    async def check_open_trades(self) -> list[str]:
        if not self.open_trades:
            return []
        prices = await self._get_price()
        if not prices:
            return []
        messages, still_open = [], []
        for trade in self.open_trades:
            price = prices.get("XAU/USD")
            if price is None:
                still_open.append(trade)
                continue
            msg = self._check(trade, price)
            if msg:
                messages.append(msg)
                if trade.get("status") == "TP1":
                    still_open.append(trade)
            else:
                still_open.append(trade)
        self.open_trades = still_open
        return messages

    async def _get_price(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=25) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._hdrs(),
                    json={
                        "model": MODEL,
                        "max_tokens": 60,
                        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages": [{"role": "user", "content":
                            "XAU/USD gold current price now. JSON only: {\"XAU/USD\":3325.50}"}]
                    }
                )
                data = r.json()
                text = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
                m = re.search(r'\{[^{}]+\}', text)
                if m:
                    return json.loads(m.group())
        except Exception as e:
            logger.error(f"Narx xatosi: {e}")
        return {}

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
                if price >= t3 and st in ("OPEN","TP1","TP2"):
                    trade["status"] = "TP3"; return self._fmt("tp3", trade, price, now)
                if price >= t2 and st == "TP1":
                    trade["status"] = "TP2"; return self._fmt("tp2", trade, price, now)
                if price >= t1 and st == "OPEN":
                    trade["status"] = "TP1"; return self._fmt("tp1", trade, price, now)
                if price <= sl:
                    trade["status"] = "SL";  return self._fmt("sl",  trade, price, now)
            else:
                if price <= t3 and st in ("OPEN","TP1","TP2"):
                    trade["status"] = "TP3"; return self._fmt("tp3", trade, price, now)
                if price <= t2 and st == "TP1":
                    trade["status"] = "TP2"; return self._fmt("tp2", trade, price, now)
                if price <= t1 and st == "OPEN":
                    trade["status"] = "TP1"; return self._fmt("tp1", trade, price, now)
                if price >= sl:
                    trade["status"] = "SL";  return self._fmt("sl",  trade, price, now)
        except Exception as e:
            logger.error(f"Check xatosi: {e}")
        return None

    def _fmt(self, status: str, trade: dict, price: float, now: str) -> str:
        d  = "🟢 BUY" if trade["direction"] == "BUY" else "🔴 SELL"
        lo = trade.get("lot_min","0.01")
        hi = trade.get("lot_max","0.03")

        msgs = {
            "tp1": (
                f"<b>✅ TP1 OLINDI! — 🥇 XAU/USD {d}</b>\n\n"
                f"Narx: <code>{price}</code> → TP1: <code>{trade['tp1']}</code>\n\n"
                f"⚡ <b>HOZIROQ BAJARING:</b>\n"
                f"✔️ SL ni kirish narxiga — <b>BEZ UBYTOKKA</b> oling!\n"
                f"✔️ Lot: {lo}–{hi} bo'lsa, qisman yopin\n"
                f"✔️ TP2 <code>{trade['tp2']}</code> ga qoldiring\n\n"
                f"⚠️ Bozor teskari ketsa — <b>DARHOL YOPING!</b>\n"
                f"<i>🕐 {now}</i>"
            ),
            "tp2": (
                f"<b>✅✅ TP2 OLINDI! — 🥇 XAU/USD {d}</b>\n\n"
                f"Narx: <code>{price}</code> → TP2: <code>{trade['tp2']}</code>\n\n"
                f"⚡ <b>HOZIROQ BAJARING:</b>\n"
                f"✔️ Pozitsiyaning 60–70% ini YOPING!\n"
                f"✔️ SL ni TP1 <code>{trade['tp1']}</code> ga ko'taring\n"
                f"✔️ Qolganini TP3 <code>{trade['tp3']}</code> ga qoldiring\n\n"
                f"⚠️ Momentum zaiflashsa — hammasini yoping!\n"
                f"<i>🕐 {now}</i>"
            ),
            "tp3": (
                f"<b>🏆 TP3 OLINDI! — 🥇 XAU/USD {d}</b>\n\n"
                f"Narx: <code>{price}</code> → TP3: <code>{trade['tp3']}</code>\n\n"
                f"✅ Barcha pozitsiyani YOPING!\n"
                f"🎉 Mukammal savdo! Keyingi signalni kuting.\n"
                f"<i>🕐 {now}</i>"
            ),
            "sl": (
                f"<b>🛑 STOP LOSS — 🥇 XAU/USD {d}</b>\n\n"
                f"Narx: <code>{price}</code> → SL: <code>{trade['stop_loss']}</code>\n\n"
                f"Risk menejment ishladi. Keyingi signalni kuting.\n"
                f"<i>🕐 {now}</i>"
            ),
        }
        return msgs.get(status, "")
