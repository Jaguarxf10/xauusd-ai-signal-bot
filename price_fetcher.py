"""
Binance bepul API orqali narx va OHLCV ma'lumotlari
API key kerak emas — to'liq bepul
"""
import httpx, logging, json
from datetime import datetime

logger = logging.getLogger(__name__)

BASE = "https://api.binance.com/api/v3"
# XAU/USD yo'q Binance da — PAXG/USDT yoki Yahoo Finance ishlatamiz
# Yahoo Finance bepul va XAU/USD ni qo'llab-quvvatlaydi

YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

SYMBOLS = {
    "XAU/USD": "GC=F",        # Gold Futures (Yahoo)
    "BTC/USDT": "BTC-USD",    # Bitcoin (Yahoo)
    "EUR/USD": "EURUSD=X",    # Euro/USD (Yahoo)
}


async def get_ohlcv(symbol: str = "XAU/USD", interval: str = "5m", limit: int = 50) -> dict | None:
    """Yahoo Finance dan OHLCV ma'lumotlarini oladi — BEPUL."""
    ticker = SYMBOLS.get(symbol, "GC=F")
    
    # interval mapping
    yf_interval = {
        "1m": "1m", "5m": "5m", "15m": "15m",
        "1h": "1h", "4h": "1h", "1d": "1d"
    }.get(interval, "5m")
    
    range_map = {
        "1m": "1d", "5m": "5d", "15m": "5d",
        "1h": "1mo", "1d": "3mo"
    }
    
    url = f"{YAHOO_BASE}/{ticker}"
    params = {
        "interval": yf_interval,
        "range": range_map.get(interval, "5d"),
        "includePrePost": "false"
    }
    
    try:
        async with httpx.AsyncClient(timeout=15, headers={
            "User-Agent": "Mozilla/5.0"
        }) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            
        result = data["chart"]["result"][0]
        meta   = result["meta"]
        quotes = result["indicators"]["quote"][0]
        ts     = result["timestamp"]
        
        closes  = quotes.get("close", [])
        highs   = quotes.get("high", [])
        lows    = quotes.get("low", [])
        opens   = quotes.get("open", [])
        volumes = quotes.get("volume", [])
        
        # None larni tozalash
        candles = []
        for i in range(len(closes)):
            if closes[i] is not None:
                candles.append({
                    "time":   ts[i],
                    "open":   opens[i] or closes[i],
                    "high":   highs[i] or closes[i],
                    "low":    lows[i] or closes[i],
                    "close":  closes[i],
                    "volume": volumes[i] or 0
                })
        
        current_price = meta.get("regularMarketPrice") or (closes[-1] if closes else 0)
        
        return {
            "symbol":        symbol,
            "current_price": float(current_price),
            "candles":       candles[-limit:],
            "interval":      interval
        }
    except Exception as e:
        logger.error(f"Yahoo Finance xatosi ({symbol}): {e}")
        return None


def calc_indicators(candles: list) -> dict:
    """Asosiy indikatorlarni hisoblaydi — Claude siz."""
    if len(candles) < 20:
        return {}
    
    closes = [c["close"] for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    
    # EMA hisoblash
    def ema(data, period):
        k = 2 / (period + 1)
        e = data[0]
        for d in data[1:]:
            e = d * k + e * (1 - k)
        return round(e, 2)
    
    # RSI
    def rsi(data, period=14):
        if len(data) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(data)):
            diff = data[i] - data[i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - 100 / (1 + rs), 1)
    
    # MACD
    def macd(data):
        e12 = ema(data, 12)
        e26 = ema(data, 26)
        return round(e12 - e26, 2)
    
    # Bollinger Bands
    def bollinger(data, period=20):
        if len(data) < period:
            return None, None, None
        sma = sum(data[-period:]) / period
        std = (sum((x - sma)**2 for x in data[-period:]) / period) ** 0.5
        return round(sma - 2*std, 2), round(sma, 2), round(sma + 2*std, 2)
    
    # Support / Resistance
    recent_lows  = sorted(lows[-20:])[:3]
    recent_highs = sorted(highs[-20:], reverse=True)[:3]
    support    = round(sum(recent_lows) / 3, 2)
    resistance = round(sum(recent_highs) / 3, 2)
    
    # Trend (EMA 9 vs EMA 21)
    ema9  = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, min(50, len(closes)))
    price = closes[-1]
    
    if price > ema9 > ema21:
        trend = "BULLISH"
    elif price < ema9 < ema21:
        trend = "BEARISH"
    else:
        trend = "SIDEWAYS"
    
    bb_lo, bb_mid, bb_hi = bollinger(closes)
    rsi_val  = rsi(closes)
    macd_val = macd(closes)
    
    # FVG topish (Fair Value Gap)
    fvg_zones = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        # Bullish FVG: c1.high < c3.low
        if c1["high"] < c3["low"]:
            fvg_zones.append({
                "type": "BULLISH",
                "lo": round(c1["high"], 2),
                "hi": round(c3["low"], 2)
            })
        # Bearish FVG: c1.low > c3.high
        if c1["low"] > c3["high"]:
            fvg_zones.append({
                "type": "BEARISH",
                "lo": round(c3["high"], 2),
                "hi": round(c1["low"], 2)
            })
    
    # Eng yaqin FVG
    latest_fvg = fvg_zones[-3:] if fvg_zones else []
    
    # Order Block (so'nggi kuchli harakat oldidagi candle)
    ob_zones = []
    for i in range(3, len(candles)):
        c_prev = candles[i-1]
        c_curr = candles[i]
        body_size = abs(c_curr["close"] - c_curr["open"])
        avg_body  = sum(abs(c["close"]-c["open"]) for c in candles[-20:]) / 20
        
        if body_size > avg_body * 1.5:  # Katta candle = displacement
            # Bearish OB: yuqoridan tushgan
            if c_curr["close"] < c_curr["open"]:
                ob_zones.append({
                    "type": "BEARISH_OB",
                    "lo": round(c_prev["low"], 2),
                    "hi": round(c_prev["high"], 2)
                })
            # Bullish OB: pastdan ko'tarilgan
            else:
                ob_zones.append({
                    "type": "BULLISH_OB",
                    "lo": round(c_prev["low"], 2),
                    "hi": round(c_prev["high"], 2)
                })
    
    latest_ob = ob_zones[-2:] if ob_zones else []
    
    # Trend kuchi (ADX o'rniga sodda)
    price_change = (closes[-1] - closes[-20]) / closes[-20] * 100
    
    return {
        "price":      round(price, 2),
        "ema9":       ema9,
        "ema21":      ema21,
        "ema50":      ema50,
        "rsi":        rsi_val,
        "macd":       macd_val,
        "bb_lo":      bb_lo,
        "bb_mid":     bb_mid,
        "bb_hi":      bb_hi,
        "support":    support,
        "resistance": resistance,
        "trend":      trend,
        "price_change_pct": round(price_change, 2),
        "fvg_zones":  latest_fvg,
        "ob_zones":   latest_ob,
    }
