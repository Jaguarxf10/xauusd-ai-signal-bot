"""
ICT + Multi-TF Signal Engine
- ICT concepts: Order Blocks, FVG, Liquidity, BOS/CHoCH, MSS
- Multi-TF: 1D/4H/1H/30M trend + 15M/5M/1M entry
- Pairs: XAU/USD, BTC/USDT, EUR/USD
"""
import json, re, httpx, logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
MODEL  = "claude-haiku-4-5"
PAIRS  = ["XAU/USD", "BTC/USDT", "EUR/USD"]

SYSTEM = """Sen ICT (Inner Circle Trader) metodologiyasi bo'yicha mutaxassis professional treydersan.
Web search bilan hozirgi narxlar va bozor ma'lumotlarini topib, chuqur ICT tahlili qil.

═══════════════════════════════════════
ICT TAHLIL TARTIBI (majburiy):
═══════════════════════════════════════

1. KOTTA TIMEFRAME TAHLIL (1D, 4H, 1H):
   • Market Structure: HH/HL (bullish) yoki LH/LL (bearish)
   • BOS (Break of Structure) — trendni tasdiqlash
   • CHoCH (Change of Character) — trend o'zgarishi signali
   • Premium/Discount zones (Fibonacci 50% level)
   • Institutional order flow yo'nalishi

2. ICT ASOSIY KONTSEPTLAR:
   • ORDER BLOCKS (OB): So'nggi bearish/bullish candle before BOS
     - Bullish OB: Narx pastdan kelayotgan so'nggi bearish candle
     - Bearish OB: Narx yuqoridan kelayotgan so'nggi bullish candle
     - Mitigation tekshirish: OB hali ishlatilganmi?
   
   • FAIR VALUE GAPS (FVG/IFVG):
     - 3-candle pattern: gap between candle 1 high and candle 3 low
     - Bullish FVG: kirish uchun support
     - Bearish FVG: kirish uchun resistance
     - Inverted FVG (IFVG): qarama-qarshi ishlatiladi
   
   • LIQUIDITY ZONES:
     - BSL (Buy Side Liquidity): Yuqori swing highs, equal highs
     - SSL (Sell Side Liquidity): Past swing lows, equal lows
     - Liquidity sweep: Stop hunt yakunlangan zona
     - Narx likvid zonani sweep qilganmi?
   
   • DISPLACEMENT: Kuchli impulsiv harakat (institutional)
   • MITIGATION BLOCKS: Qaytib kelgan OB/FVG
   • BREAKER BLOCKS: Buzilgan OB qarama-qarshi ishlatiladi

3. KIRISH TIMEFRAME (15M, 5M, 1M):
   • MSS (Market Structure Shift) kichik TFda
   • OB yoki FVG ichida narx
   • Liquidity sweep + reversal
   • Optimal Trade Entry (OTE): 62-79% Fibonacci

4. SIGNAL SHARTLARI (BARCHASI kerak):
   ✅ Kotta TF trend yo'nalishi (1D/4H/1H bir xil)
   ✅ Narx premium/discount zonada
   ✅ Kuchli OB yoki FVG tasdiqlangan
   ✅ Liquidity sweep yakunlangan
   ✅ Kirish TFda MSS yoki CHoCH
   ✅ 75%+ umumiy ishonchlilik
   ✅ R:R kamida 1:2

FAQAT bitta JSON qaytargin (markdown yoki kod bloki YO'Q):

Kuchli ICT signal:
{"signal_found":true,"pair":"XAU/USD","direction":"BUY","strength":88,"strength_stars":4,"entry_tf":"5M","entry_price":"3318.50","entry_zone":"3315.00-3320.00","tp1":"3335.00","tp1_pips":50,"tp2":"3355.00","tp2_pips":120,"tp3":"3380.00","tp3_pips":215,"stop_loss":"3308.00","sl_pips":35,"risk_level":"PAST","rr_ratio":"3.1","trend_1d":"BULLISH","trend_4h":"BULLISH","trend_1h":"BULLISH","trend_30m":"BULLISH","ict_setup":"Bullish OB mitigation + SSL sweep + 5M MSS","ob_zone":"3312.00-3320.00","fvg_zone":"3318.00-3323.00","liquidity":"SSL swept at 3310.50","bos_choch":"4H BOS confirmed at 3325","premium_discount":"Discount zone (below 50% FIB)","analysis":"4H bullish OB da narx kirib keldi, SSL sweep yakunlandi, 5M MSS tasdiqlandi, FVG support bor","invalidation":"3308 yorilsa — setup bekor","tp1_action":"TP1 olgach: SL bez ubytokka, bozor zaiflashsa — yoping","tp2_action":"TP2 olgach: 50-70% yopish, SL TP1ga, qolganini TP3ga"}

Signal yo'q:
{"signal_found":false,"pair":"XAU/USD","reason":"Sabab — qaysi shart bajarilmadi"}"""


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
        now = datetime.now(self.tz)
        h = now.hour
        session = (
            "London (likvidlik yuqori)" if 5 <= h < 10 else
            "London+NY (eng faol, institutional)" if 10 <= h < 15 else
            "New York" if 15 <= h < 19 else
            "Osiyo (kam likvidlik)"
        )
        msg = (
            f"Vaqt: {now.strftime('%d.%m.%Y %H:%M')} | Sessiya: {session}\n"
            f"Juft: {pair}\n\n"
            f"Web search bilan hozirgi narx, 1D/4H/1H/30M/15M/5M ma'lumotlarini topib "
            f"ICT metodologiyasi asosida to'liq tahlil qil:\n"
            f"- Order Blocks (bullish/bearish OB)\n"
            f"- Fair Value Gaps (FVG/IFVG)\n"
            f"- Liquidity zones (BSL/SSL) va sweep\n"
            f"- BOS/CHoCH/MSS market structure\n"
            f"- Premium/Discount zones\n"
            f"Faqat JSON."
        )
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._hdrs(),
                    json={
                        "model": MODEL,
                        "max_tokens": 900,
                        "system": SYSTEM,
                        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages": [{"role": "user", "content": msg}]
                    }
                )
                r.raise_for_status()
                data = r.json()

            text = "".join(
                b.get("text", "") for b in data.get("content", [])
                if b.get("type") == "text"
            )
            result = self._parse(text)

            if not result or not result.get("signal_found"):
                logger.info(f"{pair} signal yo'q: {(result or {}).get('reason','')[:80]}")
                return None
            if result.get("strength", 0) < 75:
                logger.info(f"{pair} kuchsiz: {result.get('strength')}%")
                return None

            result["timestamp"] = now.strftime("%d.%m.%Y %H:%M")
            result["status"] = "OPEN"
            return result

        except Exception as e:
            logger.error(f"{pair} xatosi: {e}")
            return None

    async def analyze(self) -> list[dict]:
        signals = []
        for pair in PAIRS:
            logger.info(f"{pair} ICT tahlil...")
            res = await self._analyze_pair(pair)
            if res:
                self.open_trades.append(res.copy())
                signals.append(res)
                logger.info(f"✅ {pair}: {res['direction']} {res['strength']}% | {res.get('ict_setup','')[:50]}")
        return signals

    async def check_open_trades(self) -> list[str]:
        if not self.open_trades:
            return []
        prices = await self._get_prices()
        messages, still_open = [], []
        for trade in self.open_trades:
            price = prices.get(trade.get("pair", "XAU/USD"))
            if price is None:
                still_open.append(trade)
                continue
            msg = self._check_price(trade, price)
            if msg:
                messages.append(msg)
                if trade.get("status") in ("TP1",):
                    still_open.append(trade)
            else:
                still_open.append(trade)
        self.open_trades = still_open
        return messages

    async def _get_prices(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._hdrs(),
                    json={
                        "model": MODEL,
                        "max_tokens": 80,
                        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages": [{"role": "user", "content":
                            "Current live prices XAU/USD gold, BTC/USDT, EUR/USD. "
                            "JSON only: {\"XAU/USD\":3320.5,\"BTC/USDT\":67500.0,\"EUR/USD\":1.0850}"}]
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

    def _check_price(self, trade: dict, price: float) -> str | None:
        try:
            d      = trade["direction"]
            tp1    = float(trade["tp1"])
            tp2    = float(trade["tp2"])
            tp3    = float(trade["tp3"])
            sl     = float(trade["stop_loss"])
            status = trade.get("status", "OPEN")
            now    = datetime.now(self.tz).strftime("%H:%M")

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
            else:
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
            logger.error(f"Narx tekshirish: {e}")
        return None

    def _fmt(self, status: str, trade: dict, price: float, now: str) -> str:
        d    = "🟢 BUY" if trade["direction"] == "BUY" else "🔴 SELL"
        pair = trade.get("pair", "XAU/USD")
        pe   = {"XAU/USD": "🥇", "BTC/USDT": "₿", "EUR/USD": "💶"}.get(pair, "📊")

        if status == "tp1_hit":
            return (
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>✅ TP1 OLINDI!</b>  {pe} {pair}  {d}\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                f"Narx: <code>{price}</code>  →  TP1: <code>{trade['tp1']}</code>\n\n"
                f"⚡ <b>DARHOL BAJARING:</b>\n"
                f"✔️ SL ni kirish narxiga <b>BEZ UBYTOKKA</b> oling!\n"
                f"✔️ {trade.get('tp1_action','Bozor zaiflashsa — darhol yoping!')}\n"
                f"✔️ Qolganini TP2 <code>{trade['tp2']}</code> ga qoldiring\n\n"
                f"⚠️ <i>Bozor yo'nalishi qarshiga o'zgarsa — DARHOL yoping!</i>\n\n"
                f"<i>🕐 {now}</i>"
            )
        elif status == "tp2_hit":
            return (
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>✅✅ TP2 OLINDI!</b>  {pe} {pair}  {d}\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                f"Narx: <code>{price}</code>  →  TP2: <code>{trade['tp2']}</code>\n\n"
                f"⚡ <b>DARHOL BAJARING:</b>\n"
                f"✔️ {trade.get('tp2_action','Pozitsiyaning 50-70% ini yoping!')}\n"
                f"✔️ SL ni TP1 <code>{trade['tp1']}</code> ga ko'taring\n"
                f"✔️ Qolganini TP3 <code>{trade['tp3']}</code> ga qoldiring\n\n"
                f"⚠️ <i>Bozor teskari chegaraga yetsa — hammasini yoping!</i>\n\n"
                f"<i>🕐 {now}</i>"
            )
        elif status == "tp3_hit":
            return (
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>🏆 TP3 OLINDI!</b>  {pe} {pair}  {d}\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                f"Narx: <code>{price}</code>  →  TP3: <code>{trade['tp3']}</code>\n\n"
                f"✅ <b>Barcha pozitsiyani yoping!</b>\n"
                f"🎉 Mukammal ICT savdo yakunlandi!\n\n"
                f"<i>🕐 {now}</i>"
            )
        else:
            return (
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>🛑 STOP LOSS URILDI</b>  {pe} {pair}  {d}\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                f"Narx: <code>{price}</code>  →  SL: <code>{trade['stop_loss']}</code>\n\n"
                f"<i>Risk menejment ishladi. Setup bekor — keyingi signalni kuting.</i>\n\n"
                f"<i>🕐 {now}</i>"
            )
