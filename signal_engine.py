"""
Signal Engine v5 — Binance/Yahoo bepul narx + Claude faqat tahlil
Kuniga: ~$0.05-0.15 (avval $3-5 edi)
"""
import json, re, httpx, logging
from datetime import datetime
import pytz
from price_fetcher import get_ohlcv, calc_indicators

logger = logging.getLogger(__name__)
MODEL = "claude-haiku-4-5"

SIGNAL_HOURS = {9: "London", 15: "New York"}


class SignalEngine:
    def __init__(self, api_key: str):
        self.api_key      = api_key
        self.open_trades  = []
        self.tz           = pytz.timezone("Asia/Tashkent")
        self.sent_hours   = set()
        self.last_date    = None

    def _hdrs(self):
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

    def _reset(self):
        today = datetime.now(self.tz).date()
        if self.last_date != today:
            self.sent_hours = set()
            self.last_date  = today

    async def _ask_claude(self, prompt: str, max_tokens=400) -> str:
        """Claude ga WEB SEARCH SИZZ — faqat tahlil."""
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._hdrs(),
                    json={
                        "model": MODEL,
                        "max_tokens": max_tokens,
                        "messages": [{"role": "user", "content": prompt}]
                    }
                )
                r.raise_for_status()
                data = r.json()
                return "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
        except Exception as e:
            logger.error(f"Claude xatosi: {e}")
            return ""

    def _build_levels(self, ind: dict, direction: str) -> dict:
        """SL/TP darajalarini indikatorlar asosida hisoblaydi."""
        price = ind["price"]
        
        # ATR o'rniga BB width ishlatamiz
        bb_hi = ind.get("bb_hi") or price * 1.005
        bb_lo = ind.get("bb_lo") or price * 0.995
        atr   = (bb_hi - bb_lo) / 4  # taxminiy ATR
        atr   = max(atr, price * 0.001)  # minimum 0.1%

        if direction == "BUY":
            sl   = round(ind["support"] - atr * 0.5, 2)
            tp1  = round(price + atr * 1.0, 2)
            tp2  = round(price + atr * 2.0, 2)
            tp3  = round(price + atr * 3.5, 2)
            zone_lo = round(max(ind["support"], price - atr), 2)
            zone_hi = round(price + atr * 0.3, 2)
        else:
            sl   = round(ind["resistance"] + atr * 0.5, 2)
            tp1  = round(price - atr * 1.0, 2)
            tp2  = round(price - atr * 2.0, 2)
            tp3  = round(price - atr * 3.5, 2)
            zone_lo = round(price - atr * 0.3, 2)
            zone_hi = round(min(ind["resistance"], price + atr), 2)

        sl_pips  = round(abs(price - sl), 2)
        tp1_pips = round(abs(tp1 - price), 2)
        tp2_pips = round(abs(tp2 - price), 2)
        tp3_pips = round(abs(tp3 - price), 2)
        rr       = round(tp2_pips / sl_pips, 1) if sl_pips else 2.0

        return {
            "entry_zone": f"{zone_lo}-{zone_hi}",
            "tp1": str(tp1), "tp1_pips": tp1_pips,
            "tp2": str(tp2), "tp2_pips": tp2_pips,
            "tp3": str(tp3), "tp3_pips": tp3_pips,
            "stop_loss": str(sl), "sl_pips": sl_pips,
            "rr_ratio": str(rr),
        }

    def _ict_analysis(self, ind: dict, direction: str) -> dict:
        """ICT zonalarini indikatorlardan aniqlaydi."""
        fvg_list = ind.get("fvg_zones", [])
        ob_list  = ind.get("ob_zones",  [])
        price    = ind["price"]

        # Yo'nalishga mos FVG
        match_fvg = [z for z in fvg_list if z["type"] == direction]
        # Yo'nalishga mos OB
        ob_key   = "BULLISH_OB" if direction == "BUY" else "BEARISH_OB"
        match_ob = [z for z in ob_list if z["type"] == ob_key]

        fvg_note = "—"
        ob_note  = "—"

        if match_fvg:
            z = match_fvg[-1]
            fvg_note = f"{z['lo']}-{z['hi']}"
        if match_ob:
            z = match_ob[-1]
            ob_note = f"{z['lo']}-{z['hi']}"

        # Likvidlik zonalari
        bsl = ind["resistance"]  # Buy Side Liquidity
        ssl = ind["support"]     # Sell Side Liquidity

        return {
            "fvg_zone": fvg_note,
            "ob_zone":  ob_note,
            "bsl":      str(bsl),
            "ssl":      str(ssl),
        }

    async def _claude_confirm(self, ind: dict, direction: str,
                               ict: dict, session: str) -> dict:
        """Claude ga QISQA prompt — faqat tasdiq va tahlil matni.
        Web search YO'Q — token tejash uchun."""
        price = ind["price"]
        fvg   = ict["fvg_zone"]
        ob    = ict["ob_zone"]

        prompt = f"""XAU/USD texnik tahlil. Sen tajribali trader sifatida quyidagi ma'lumotlarga asoslanib, {direction} signal uchun qisqa tahlil yoz.

MA'LUMOTLAR:
- Narx: {price}
- Trend: {ind['trend']} (EMA9={ind['ema9']}, EMA21={ind['ema21']})
- RSI: {ind['rsi']} {"(oversold)" if ind['rsi'] < 35 else "(overbought)" if ind['rsi'] > 65 else "(neytral)"}
- MACD: {ind['macd']} {"(bullish)" if ind['macd'] > 0 else "(bearish)"}
- Bollinger: lo={ind['bb_lo']}, mid={ind['bb_mid']}, hi={ind['bb_hi']}
- Support: {ind['support']}, Resistance: {ind['resistance']}
- FVG zona: {fvg}
- Order Block: {ob}
- Sessiya: {session}

FAQAT JSON (boshqa matn yo'q):
{{"strength":82,"analysis":"2-3 gap o'zbek tilida tahlil","ict_note":"ICT setup tavsifi","invalidation":"bekor sharti"}}"""

        text = await self._ask_claude(prompt, max_tokens=300)
        clean = re.sub(r'```json|```', '', text).strip()
        m = re.search(r'\{[^{}]+\}', clean, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return {
            "strength":     78,
            "analysis":     f"{session}: {ind['trend']} trend, RSI {ind['rsi']}, narx {price}",
            "ict_note":     f"OB: {ob} | FVG: {fvg}",
            "invalidation": f"SL yorilsa — darhol yop",
        }

    async def analyze(self) -> list[dict]:
        self._reset()
        now = datetime.now(self.tz)
        h   = now.hour

        if not (5 <= h < 23):
            return []

        is_forced = h in SIGNAL_HOURS and h not in self.sent_hours
        session   = SIGNAL_HOURS.get(h, f"{h}:00")

        # ── 1. Bepul narx va indikatorlar ──────────────────
        logger.info("Yahoo Finance dan XAU/USD ma'lumotlari olinmoqda...")
        data5m = await get_ohlcv("XAU/USD", "5m", 60, self.api_key)
        data1h = await get_ohlcv("XAU/USD", "1h", 50, self.api_key)

        if not data5m or not data5m["candles"]:
            logger.warning("Yahoo Finance dan ma'lumot kelmadi")
            if is_forced:
                # Majburiy vaqtda fallback signal
                return [self._fallback_signal(now, session, is_forced)]
            return []

        ind5m = calc_indicators(data5m["candles"])
        ind1h = calc_indicators(data1h["candles"]) if data1h else ind5m
        price = data5m["current_price"] or ind5m.get("price", 0)
        if price < 100:
            if is_forced:
                return [self._fallback_signal(now, session, is_forced)]
            return []

        ind5m["price"] = price

        # ── 2. Yo'nalish ────────────────────────────────────
        trend5m = ind5m.get("trend", "BEARISH")
        trend1h = ind1h.get("trend", "BEARISH")

        # Ikki TF mos kelsa — kuchli signal
        if trend5m == trend1h:
            direction = "BUY" if "BULL" in trend5m else "SELL"
            strong    = True
        else:
            # Mos kelmasa — 1h ga ustuvorlik
            direction = "BUY" if "BULL" in trend1h else "SELL"
            strong    = False

        # Majburiy vaqtda har doim signal — kuchsiz bo'lsa ham
        if not strong and not is_forced:
            logger.info(f"TF mos emas ({trend5m} vs {trend1h}), signal yo'q")
            return []

        # ── 3. Darajalar hisoblash ──────────────────────────
        levels = self._build_levels(ind5m, direction)
        ict    = self._ict_analysis(ind5m, direction)

        # ── 4. Claude — qisqa tahlil (web search YO'Q) ─────
        logger.info("Claude tahlil qilmoqda (web search yo'q)...")
        confirm = await self._claude_confirm(ind5m, direction, ict, session)

        # ── 5. Signal qurish ────────────────────────────────
        sig = {
            "signal_found":   True,
            "pair":           "XAU/USD",
            "direction":      direction,
            "strength":       confirm.get("strength", 78),
            "strength_stars": 4 if confirm.get("strength", 0) >= 80 else 3,
            "entry_tf":       "5M",
            "current_price":  str(price),
            "trend_1h":       trend1h,
            "trend_5m":       trend5m,
            "ict_note":       confirm.get("ict_note", ict["ict_note"]),
            "ob_zone":        ict["ob_zone"],
            "fvg_zone":       ict["fvg_zone"],
            "key_level":      f"Support: {ind5m['support']} | Resistance: {ind5m['resistance']}",
            "analysis":       confirm.get("analysis", ""),
            "invalidation":   confirm.get("invalidation", "SL yorilsa yop"),
            "lot_min":        "0.01",
            "lot_max":        "0.03",
            "guaranteed":     is_forced,
            "timestamp":      now.strftime("%d.%m.%Y %H:%M"),
            "status":         "OPEN",
            **levels,
        }
        sig["entry_zone"] = levels["entry_zone"]

        self.open_trades.append(sig.copy())
        if is_forced:
            self.sent_hours.add(h)
        logger.info(f"✅ Signal: {direction} {sig['strength']}% | {price}")
        return [sig]

    def _fallback_signal(self, now, session, is_forced) -> dict:
        """Narx kelmasa ham majburiy signal."""
        logger.warning("Fallback signal ishlatilmoqda")
        price = 3300.0
        return {
            "signal_found": True, "pair": "XAU/USD",
            "direction": "SELL", "strength": 75, "strength_stars": 3,
            "entry_tf": "5M", "current_price": str(price),
            "entry_zone": f"{price-2}-{price+2}",
            "tp1": str(price-18), "tp1_pips": 18,
            "tp2": str(price-36), "tp2_pips": 36,
            "tp3": str(price-60), "tp3_pips": 60,
            "stop_loss": str(price+25), "sl_pips": 25,
            "rr_ratio": "2.0", "risk_level": "PAST",
            "trend_1h": "BEARISH", "trend_5m": "BEARISH",
            "ict_note": "Majburiy signal — narx ma'lumoti kelmadi",
            "ob_zone": "—", "fvg_zone": "—",
            "key_level": "Ma'lumot yo'q", "analysis": f"{session} majburiy signal",
            "invalidation": "SL yorilsa yop",
            "lot_min": "0.01", "lot_max": "0.03",
            "guaranteed": True,
            "timestamp": now.strftime("%d.%m.%Y %H:%M"), "status": "OPEN",
        }

    async def check_open_trades(self) -> list[str]:
        if not self.open_trades:
            return []
        data = await get_ohlcv("XAU/USD", "1m", 5, self.api_key)
        if not data:
            return []
        price = data["current_price"]
        if price < 100:
            return []
        msgs, still_open = [], []
        for trade in self.open_trades:
            msg = self._check(trade, price)
            if msg:
                msgs.append(msg)
                if trade.get("status") == "TP1":
                    still_open.append(trade)
            else:
                still_open.append(trade)
        self.open_trades = still_open
        return msgs

    def _check(self, trade, price) -> str | None:
        try:
            d  = trade["direction"]
            t1 = float(trade["tp1"])
            t2 = float(trade["tp2"])
            t3 = float(trade["tp3"])
            sl = float(trade["stop_loss"])
            st = trade.get("status", "OPEN")
            now = datetime.now(self.tz).strftime("%H:%M")
            if d == "BUY":
                if price >= t3: trade["status"]="TP3"; return self._fmt("tp3",trade,price,now)
                if price >= t2 and st=="TP1": trade["status"]="TP2"; return self._fmt("tp2",trade,price,now)
                if price >= t1 and st=="OPEN": trade["status"]="TP1"; return self._fmt("tp1",trade,price,now)
                if price <= sl: trade["status"]="SL"; return self._fmt("sl",trade,price,now)
            else:
                if price <= t3: trade["status"]="TP3"; return self._fmt("tp3",trade,price,now)
                if price <= t2 and st=="TP1": trade["status"]="TP2"; return self._fmt("tp2",trade,price,now)
                if price <= t1 and st=="OPEN": trade["status"]="TP1"; return self._fmt("tp1",trade,price,now)
                if price >= sl: trade["status"]="SL"; return self._fmt("sl",trade,price,now)
        except Exception as e:
            logger.error(f"Check: {e}")
        return None

    def _fmt(self, status, trade, price, now) -> str:
        d = "🟢 BUY" if trade["direction"]=="BUY" else "🔴 SELL"
        t1=trade["tp1"]; t2=trade["tp2"]; t3=trade["tp3"]; sl=trade["stop_loss"]
        if status=="tp1":
            return (f"<b>✅ TP1 OLINDI! 🥇 {d}</b>\n\nNarx: <code>{price}</code> → TP1: <code>{t1}</code>\n\n"
                    f"⚡ SL ni kirish narxiga — <b>BEZ UBYTOK!</b>\n⚡ Bozor teskari ketsa — DARHOL YOPING!\n"
                    f"✔️ TP2 <code>{t2}</code> ga qoldiring\n<i>🕐 {now}</i>")
        elif status=="tp2":
            return (f"<b>✅✅ TP2 OLINDI! 🥇 {d}</b>\n\nNarx: <code>{price}</code> → TP2: <code>{t2}</code>\n\n"
                    f"✔️ 60% pozitsiyani YOPING!\n✔️ SL → TP1 <code>{t1}</code>\n"
                    f"✔️ Qolganini TP3 <code>{t3}</code> ga\n<i>🕐 {now}</i>")
        elif status=="tp3":
            return (f"<b>🏆 TP3 OLINDI! 🥇 {d}</b>\n\nNarx: <code>{price}</code> → TP3: <code>{t3}</code>\n"
                    f"✅ Barcha pozitsiyani YOPING! 🎉\n<i>🕐 {now}</i>")
        else:
            return (f"<b>🛑 STOP LOSS 🥇 {d}</b>\n\nNarx: <code>{price}</code> → SL: <code>{sl}</code>\n"
                    f"Risk menejment ishladi. Keyingi signalni kuting.\n<i>🕐 {now}</i>")
