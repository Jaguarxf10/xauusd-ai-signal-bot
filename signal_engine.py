"""
Multi-Pair Signal Engine
- Juftlar: XAU/USD, BTC/USD, EUR/USD
- Kotta TF tahlil: 1D → 4H → 1H → 30M (trend filtri)
- Kirish TF: 15M, 5M, 1M
- Filtr: 75%+ va barcha TF mos kelishi kerak
"""
import json, re, httpx, logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
MODEL  = "claude-haiku-4-5"

PAIRS = ["XAU/USD", "BTC/USDT", "EUR/USD"]

SYSTEM = """Sen professional multi-timeframe texnik tahlilchisan.
Web search bilan HOZIRGI narxlar va indikatorlarni topib tahlil qil.

TAHLIL TARTIBI:
1. Kotta TF (1D, 4H, 1H, 30M) — asosiy trend yo'nalishini aniqlash
2. Kirish TF (15M, 5M, 1M) — aniq kirish nuqtasini topish
3. Faqat kotta va kirish TF bir yo'nalishda bo'lsa signal ber

SIGNAL MEZONLARI (barchasi kerak):
- RSI (oversold/overbought)
- MACD cross
- EMA 9/21/50/200 alignment
- Bollinger Bands
- Support/Resistance
- Volume confirmation
- Kotta TF trend tasdiqlashi

MUHIM: Faqat 75%+ kuchli, barcha TFda mos signal bering!

FAQAT JSON qaytargin (kod bloki yo'q):

Kuchli signal:
{"signal_found":true,"pair":"XAU/USD","direction":"BUY","strength":85,"strength_stars":4,"entry_tf":"5M","entry_price":"3320.50","entry_zone":"3318.00-3322.00","tp1":"3335.00","tp1_pips":45,"tp2":"3352.00","tp2_pips":95,"tp3":"3375.00","tp3_pips":165,"stop_loss":"3308.00","sl_pips":37,"risk_level":"PAST","rr_ratio":"2.5","trend_1d":"BULLISH","trend_4h":"BULLISH","trend_1h":"BULLISH","trend_30m":"BULLISH","analysis":"RSI 28 oversold 5M, MACD bullish cross, EMA21 support, 4H uptrend intact","invalidation":"3308 yorilsa signal bekor","tp1_exit_hint":"TP1 olgandan so'ng: SL bez ubitkaga, bozor yo'nalishi o'zgarsa yoping"}

Signal yo'q:
{"signal_found":false,"pair":"XAU/USD","reason":"Sabab"}"""


class SignalEngine:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.open_trades: list[dict] = []
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

    async def _analyze_pair(self, pair: str) -> dict | None:
        """Bitta juftni tahlil qiladi."""
        now = datetime.now(self.tz)
        h = now.hour
        session = (
            "London" if 5 <= h < 10 else
            "London+NY" if 10 <= h < 15 else
            "New York" if 15 <= h < 19 else "Osiyo"
        )
        msg = (
            f"Vaqt: {now.strftime('%d.%m.%Y %H:%M')} Toshkent | Sessiya: {session}\n"
            f"Juft: {pair}\n"
            f"Web search bilan hozirgi narx, 1D/4H/1H/30M/15M/5M/1M indikatorlarni topib "
            f"multi-timeframe tahlil qil. Faqat JSON."
        )
        try:
            async with httpx.AsyncClient(timeout=55) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._hdrs(),
                    json={
                        "model": MODEL,
                        "max_tokens": 700,
                        "system": SYSTEM,
                        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages": [{"role": "user", "content": msg}]
                    }
                )
                r.raise_for_status()
                data = r.json()
            text = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
            result = self._parse(text)
            if not result or not result.get("signal_found"):
                reason = result.get("reason","") if result else "parse xatosi"
                logger.info(f"{pair} signal yo'q: {reason[:80]}")
                return None
            if result.get("strength", 0) < 75:
                logger.info(f"{pair} kuchsiz signal: {result.get('strength')}%")
                return None
            result["timestamp"] = now.strftime("%d.%m.%Y %H:%M")
            result["status"] = "OPEN"
            return result
        except Exception as e:
            logger.error(f"{pair} tahlil xatosi: {e}")
            return None

    async def analyze(self) -> list[dict]:
        """Barcha juftlarni tahlil qiladi, kuchli signallarni qaytaradi."""
        signals = []
        for pair in PAIRS:
            logger.info(f"{pair} tahlil qilinmoqda...")
            result = await self._analyze_pair(pair)
            if result:
                self.open_trades.append(result.copy())
                signals.append(result)
                logger.info(f"✅ {pair} signal: {result['direction']} {result['strength']}%")
        return signals

    async def check_open_trades(self) -> list[str]:
        """Ochiq sdelkalarni tekshiradi."""
        if not self.open_trades:
            return []
        prices = await self._get_prices()
        messages = []
        still_open = []
        for trade in self.open_trades:
            pair = trade.get("pair", "XAU/USD")
            price = prices.get(pair)
            if price is None:
                still_open.append(trade)
                continue
            msg = self._check_price(trade, price)
            if msg:
                messages.append(msg)
                # TP1 olindi — trade hali ochiq, SL bez ubitkaga
                if trade.get("status") == "TP1":
                    still_open.append(trade)
                # TP2, TP3, SL — yopildi
            else:
                still_open.append(trade)
        self.open_trades = still_open
        return messages

    async def _get_prices(self) -> dict:
        """Barcha juftlar narxini oladi."""
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._hdrs(),
                    json={
                        "model": MODEL,
                        "max_tokens": 100,
                        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages": [{"role": "user", "content":
                            "Current prices: XAU/USD gold, BTC/USDT bitcoin, EUR/USD. "
                            "Reply ONLY JSON: {\"XAU/USD\":3320.50,\"BTC/USDT\":67500.0,\"EUR/USD\":1.0850}"}]
                    }
                )
                data = r.json()
                text = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
                m = re.search(r'\{[^{}]*\}', text)
                if m:
                    return json.loads(m.group())
        except Exception as e:
            logger.error(f"Narx olish xatosi: {e}")
        return {}

    def _check_price(self, trade: dict, price: float) -> str | None:
        """Narxni TP/SL bilan solishtiradi va bozor o'zgarishini ham tekshiradi."""
        try:
            d   = trade["direction"]
            tp1 = float(trade["tp1"])
            tp2 = float(trade["tp2"])
            tp3 = float(trade["tp3"])
            sl  = float(trade["stop_loss"])
            now = datetime.now(self.tz).strftime("%H:%M")
            pair = trade.get("pair","XAU/USD")
            status = trade.get("status","OPEN")

            if d == "BUY":
                if price >= tp3:
                    trade["status"] = "TP3"
                    return self._fmt("tp3_hit", trade, price, now)
                if price >= tp2 and status == "TP1":
                    trade["status"] = "TP2"
                    return self._fmt("tp2_hit", trade, price, now)
                if price >= tp1 and status == "OPEN":
                    trade["status"] = "TP1"
                    return self._fmt("tp1_hit", trade, price, now)
                if price <= sl:
                    trade["status"] = "SL"
                    return self._fmt("sl_hit", trade, price, now)
            else:  # SELL
                if price <= tp3:
                    trade["status"] = "TP3"
                    return self._fmt("tp3_hit", trade, price, now)
                if price <= tp2 and status == "TP1":
                    trade["status"] = "TP2"
                    return self._fmt("tp2_hit", trade, price, now)
                if price <= tp1 and status == "OPEN":
                    trade["status"] = "TP1"
                    return self._fmt("tp1_hit", trade, price, now)
                if price >= sl:
                    trade["status"] = "SL"
                    return self._fmt("sl_hit", trade, price, now)
        except Exception as e:
            logger.error(f"Narx tekshirish xatosi: {e}")
        return None

    def _fmt(self, status: str, trade: dict, price: float, now: str) -> str:
        d    = "🟢 BUY" if trade["direction"] == "BUY" else "🔴 SELL"
        pair = trade.get("pair", "XAU/USD")
        pair_emoji = {"XAU/USD":"🥇","BTC/USDT":"₿","EUR/USD":"💶"}.get(pair,"📊")

        if status == "tp1_hit":
            return (
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>✅ TP1 OLINDI!</b> {pair_emoji} {pair} {d}\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                f"Narx <code>{price}</code> → TP1 <code>{trade['tp1']}</code>\n\n"
                f"⚡ <b>DARHOL BAJARING:</b>\n"
                f"✔️ SL ni kirish narxiga (BEZ UBYTOK) oling!\n"
                f"✔️ Bozor yo'nalishi o'zgarsa — YOPING!\n"
                f"✔️ Qolgan pozitsiyani TP2 <code>{trade['tp2']}</code> ga qoldiring\n\n"
                f"<i>🕐 {now}</i>"
            )
        elif status == "tp2_hit":
            return (
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>✅✅ TP2 OLINDI!</b> {pair_emoji} {pair} {d}\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                f"Narx <code>{price}</code> → TP2 <code>{trade['tp2']}</code>\n\n"
                f"⚡ <b>DARHOL BAJARING:</b>\n"
                f"✔️ Pozitsiyaning 50-70% ini yoping!\n"
                f"✔️ SL ni TP1 <code>{trade['tp1']}</code> ga ko'taring\n"
                f"✔️ Qolganini TP3 <code>{trade['tp3']}</code> ga qoldiring\n"
                f"⚠️ Bozor zaiflashsa — hammasini yoping!\n\n"
                f"<i>🕐 {now}</i>"
            )
        elif status == "tp3_hit":
            return (
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>🏆 TP3 OLINDI!</b> {pair_emoji} {pair} {d}\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                f"Narx <code>{price}</code> → TP3 <code>{trade['tp3']}</code>\n\n"
                f"✅ <b>Pozitsiyani to'liq yoping!</b>\n"
                f"🎉 Mukammal savdo! Keyingi signalni kuting.\n\n"
                f"<i>🕐 {now}</i>"
            )
        else:  # sl_hit
            return (
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>🛑 STOP LOSS URILDI</b> {pair_emoji} {pair} {d}\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                f"Narx <code>{price}</code> → SL <code>{trade['stop_loss']}</code>\n\n"
                f"<i>Risk menejment ishladi. Keyingi signalni kuting.</i>\n\n"
                f"<i>🕐 {now}</i>"
            )
