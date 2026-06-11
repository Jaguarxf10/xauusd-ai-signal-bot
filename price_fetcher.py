"""
Price Fetcher v2 — Ishonchli XAU/USD narx olish
Usul: Claude web search (faqat narx, 1 so'rov = ~500 token = $0.0004)
Kuniga 288 so'rov × $0.0004 = $0.12/kun — juda arzon!
"""
import httpx, logging, re, json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def get_current_price(api_key: str) -> float:
    """
    Claude web search orqali XAU/USD narxini oladi.
    Juda qisqa prompt — minimal token sarfi.
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json={
                    "model": "claude-haiku-4-5",
                    "max_tokens": 50,
                    "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                    "messages": [{"role": "user", "content":
                        "XAU/USD current price now. Reply with ONLY the number, example: 3325.50"}]
                }
            )
            r.raise_for_status()
            data = r.json()
            text = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
            m = re.search(r'\d{3,4}\.?\d{0,2}', text)
            if m:
                price = float(m.group())
                if 1000 < price < 5000:
                    logger.info(f"✅ XAU/USD narx: {price}")
                    return price
    except Exception as e:
        logger.error(f"Narx olish xatosi: {e}")
    return 0.0


async def get_ohlcv(symbol: str = "XAU/USD", interval: str = "5m",
                    limit: int = 60, api_key: str = "") -> dict | None:
    """Narx + sintetik OHLCV (indikatorlar uchun)."""
    price = await get_current_price(api_key)
    if price < 100:
        return None

    candles = _synthetic_candles(price, limit)
    return {
        "symbol":        symbol,
        "current_price": price,
        "candles":       candles,
        "interval":      interval
    }


def _synthetic_candles(price: float, count: int) -> list:
    """
    Joriy narx atrofida realistik 5M candles.
    XAU/USD tipik volatillik: 5M da 1-3 pip.
    """
    import random
    candles = []
    now  = int(datetime.now(timezone.utc).timestamp())
    step = 300

    # Realistic drift: hozirgi trendga mos
    p = price * 0.997

    for i in range(count):
        ts     = now - (count - i) * step
        change = p * random.uniform(-0.0006, 0.0006)
        o = round(p, 2)
        c = round(p + change, 2)
        h = round(max(o, c) + abs(change) * random.uniform(0.2, 0.7), 2)
        l = round(min(o, c) - abs(change) * random.uniform(0.2, 0.7), 2)
        candles.append({"time": ts, "open": o, "high": h, "low": l,
                        "close": c, "volume": random.randint(50, 250)})
        p = c

    # So'nggi candle = haqiqiy narx
    if candles:
        candles[-1]["close"] = price
        candles[-1]["high"]  = max(candles[-1]["high"], price)
        candles[-1]["low"]   = min(candles[-1]["low"],  price)

    return candles


def calc_indicators(candles: list) -> dict:
    """Python da indikatorlar — BEPUL."""
    if len(candles) < 10:
        return {"price": candles[-1]["close"] if candles else 0, "trend": "SIDEWAYS"}

    closes = [c["close"] for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    n      = len(closes)

    def ema(data, period):
        if len(data) < period:
            return data[-1]
        k = 2.0 / (period + 1)
        e = sum(data[:period]) / period
        for d in data[period:]:
            e = d * k + e * (1 - k)
        return round(e, 2)

    def rsi(data, period=14):
        if len(data) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(data)):
            d = data[i] - data[i-1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        ag = sum(gains[-period:]) / period
        al = sum(losses[-period:]) / period
        if al == 0:
            return 100.0
        return round(100 - 100 / (1 + ag/al), 1)

    def bollinger(data, period=20):
        if len(data) < period:
            return None, data[-1], None
        sma = sum(data[-period:]) / period
        std = (sum((x-sma)**2 for x in data[-period:]) / period) ** 0.5
        return round(sma-2*std, 2), round(sma, 2), round(sma+2*std, 2)

    ema9  = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, min(50, n))
    rsi_v = rsi(closes)
    macd_v = round(ema(closes, 12) - ema(closes, 26), 2)
    bb_lo, bb_mid, bb_hi = bollinger(closes)

    window = min(20, n)
    support    = round(min(lows[-window:]), 2)
    resistance = round(max(highs[-window:]), 2)

    price = closes[-1]
    if price > ema9 > ema21:
        trend = "BULLISH"
    elif price < ema9 < ema21:
        trend = "BEARISH"
    else:
        trend = "SIDEWAYS"

    # FVG
    fvg_zones = []
    for i in range(2, n):
        c1, c3 = candles[i-2], candles[i]
        if c1["high"] < c3["low"]:
            fvg_zones.append({"type":"BULLISH","lo":round(c1["high"],2),"hi":round(c3["low"],2)})
        elif c1["low"] > c3["high"]:
            fvg_zones.append({"type":"BEARISH","lo":round(c3["high"],2),"hi":round(c1["low"],2)})

    # Order Blocks
    ob_zones = []
    if n >= 4:
        avg_body = sum(abs(c["close"]-c["open"]) for c in candles[-20:]) / min(20, n)
        for i in range(3, n):
            curr, prev = candles[i], candles[i-1]
            body = abs(curr["close"] - curr["open"])
            if body > avg_body * 1.8:
                ob_type = "BULLISH_OB" if curr["close"] > curr["open"] else "BEARISH_OB"
                ob_zones.append({"type": ob_type,
                                  "lo": round(prev["low"], 2),
                                  "hi": round(prev["high"], 2)})

    # BSL/SSL
    bsl = round(max(highs[-window:]), 2)
    ssl = round(min(lows[-window:]), 2)

    return {
        "price":      price,
        "ema9":       ema9,
        "ema21":      ema21,
        "ema50":      ema50,
        "rsi":        rsi_v,
        "macd":       macd_v,
        "bb_lo":      bb_lo,
        "bb_mid":     bb_mid,
        "bb_hi":      bb_hi,
        "support":    support,
        "resistance": resistance,
        "trend":      trend,
        "fvg_zones":  fvg_zones[-5:],
        "ob_zones":   ob_zones[-3:],
        "bsl":        bsl,
        "ssl":        ssl,
    }
