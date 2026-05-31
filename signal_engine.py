"""
Signal Engine - Claude AI + Web Search orqali real XAU/USD tahlil
"""
import json
import re
import httpx
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Sen professional XAU/USD (Oltin/Dollar) savdo eksperti va texnik tahlilchisan.
Web search orqali HOZIRGI real vaqtdagi XAU/USD narxini, indikatorlarni topib tahlil qil.

TAHLIL (barchasi birga baholansin):
RSI(14), MACD(12,26,9), Bollinger Bands, EMA 9/21/50, Stochastic, ATR,
Support/Resistance darajalari, Candle patterns, Market struktura, Volume

SIGNAL MEZONLARI:
- Faqat 75%+ kuchli signallarda signal_found: true ber
- Kamida 6-7 indikator bir yo'nalishni ko'rsatishi kerak
- Agar bozor neytral yoki aralash bo'lsa signal_found: false ber

MUHIM: Javobingning oxirida FAQAT quyidagi formatda bitta JSON blok bo'lsin (boshqa hech narsa yo'q):

Signal bo'lsa:
{"signal_found": true, "direction": "BUY", "strength": 82, "strength_stars": 4, "entry_zone": "4535.00-4537.00", "tp1": "4545.00", "tp1_pips": 20, "tp2": "4558.00", "tp2_pips": 45, "tp3": "4575.00", "tp3_pips": 80, "stop_loss": "4523.00", "sl_pips": 25, "risk_level": "PAST", "rr_ratio": "1:3.2", "analysis_summary": "RSI 28 oversold, MACD bullish cross, EMA21 support", "invalidation": "4523 dan past tushsa bekor"}

Signal bo'lmasa:
{"signal_found": false, "reason": "Indikatorlar aralash/neytral"}"""


class SignalEngine:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.open_trades = []
        self.tz = pytz.timezone("Asia/Tashkent")

    def _headers(self):
        return {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }

    async def analyze(self) -> dict | None:
        try:
            now = datetime.now(self.tz)
            user_msg = f"""Vaqt: {now.strftime('%Y-%m-%d %H:%M')} (Toshkent).
XAU/USD M5 texnik tahlil qil. Web search bilan hozirgi narx va indikatorlarni top.
Tahlildan so'ng oxirida faqat JSON ber."""

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=self._headers(),
                    json={
                        'model': 'claude-sonnet-4-6',
                        'max_tokens': 2000,
                        'system': SYSTEM_PROMPT,
                        'tools': [{'type': 'web_search_20250305', 'name': 'web_search'}],
                        'messages': [{'role': 'user', 'content': user_msg}]
                    }
                )
                resp.raise_for_status()
                data = resp.json()

            # Barcha text bloklarni birlashtirish
            full_text = ''.join(
                block.get('text', '')
                for block in data.get('content', [])
                if block.get('type') == 'text'
            )

            if not full_text.strip():
                return None

            # Oxirgi JSON blokni topish
            matches = re.findall(r'\{[^{}]*"signal_found"[^{}]*\}', full_text, re.DOTALL)
            if not matches:
                # Katta JSON bloklarni ham qidirish
                matches = re.findall(r'\{.*?"signal_found".*?\}', full_text, re.DOTALL)

            if not matches:
                logger.info(f"JSON topilmadi. Javob: {full_text[-300:]}")
                return None

            result = json.loads(matches[-1])  # Oxirgi JSON ni ol

            if not result.get('signal_found'):
                logger.info(f"Signal yo'q: {result.get('reason', '—')}")
                return None

            if result.get('strength', 0) < 75:
                return None

            result['timestamp'] = now.strftime('%d.%m.%Y %H:%M')
            result['status'] = 'OPEN'
            self.open_trades.append(result.copy())
            return result

        except Exception as e:
            logger.error(f"Tahlil xatosi: {e}")
            return None

    async def check_open_trades(self) -> list:
        if not self.open_trades:
            return []
        messages = []
        closed = []
        for trade in self.open_trades:
            upd = await self._check_trade_status(trade)
            if upd:
                messages.append(upd)
                closed.append(trade)
        for t in closed:
            if t in self.open_trades:
                self.open_trades.remove(t)
        return messages

    async def _check_trade_status(self, trade: dict) -> str | None:
        try:
            prompt = f"""Ochiq sdelka: {trade['direction']} XAU/USD
Kirish: {trade['entry_zone']}, TP1:{trade['tp1']}, TP2:{trade['tp2']}, TP3:{trade['tp3']}, SL:{trade['stop_loss']}

Hozirgi XAU/USD narxini web search bilan tekshirib, holat baho:
Faqat JSON: {{"status": "no_update"}} yoki {{"status": "tp1_hit|tp2_hit|tp1_near|sl_risk|close_now", "message": "o'zbek tilida xabar"}}"""

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=self._headers(),
                    json={
                        'model': 'claude-sonnet-4-6',
                        'max_tokens': 400,
                        'tools': [{'type': 'web_search_20250305', 'name': 'web_search'}],
                        'messages': [{'role': 'user', 'content': prompt}]
                    }
                )
                data = resp.json()

            text = ''.join(b.get('text', '') for b in data.get('content', []) if b.get('type') == 'text')
            match = re.search(r'\{[^{}]*"status"[^{}]*\}', text, re.DOTALL)
            if not match:
                return None
            result = json.loads(match.group())
            status = result.get('status', 'no_update')
            if status == 'no_update':
                return None
            return self._format_trade_update(trade, status, result.get('message', ''))
        except Exception as e:
            logger.error(f"Sdelka tekshirish xatosi: {e}")
            return None

    def _format_trade_update(self, trade: dict, status: str, message: str) -> str:
        direction = "🟢 BUY" if trade["direction"] == "BUY" else "🔴 SELL"
        status_map = {
            "tp1_near":  ("🎯", "TP1 yaqinlashmoqda!"),
            "tp1_hit":   ("✅", "TP1 OLINDI!"),
            "tp2_hit":   ("✅✅", "TP2 OLINDI!"),
            "sl_risk":   ("⚠️", "SL xavfi bor!"),
            "close_now": ("🔔", "Sdelkani YOPING!"),
        }
        emoji, title = status_map.get(status, ("ℹ️", "Yangilik"))
        msg = (
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>{emoji} {title}</b>\n"
            f"<b>XAU/USD · {direction}</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
            f"{message}\n\n"
        )
        if status == "tp1_hit":
            msg += "💡 <b>TAVSIYA:</b>\n✔️ SL ni kirish nuqtasiga (bez ubitkaga) olib boring!\n✔️ Qolganini TP2/TP3 ga qoldiring.\n"
        elif status == "tp2_hit":
            msg += "💡 <b>TAVSIYA:</b>\n✔️ Pozitsiyaning bir qismini yopin!\n✔️ SL ni TP1 ga ko'taring.\n"
        elif status == "close_now":
            msg += "⚡ <b>Bozor holati o'zgardi — sdelkani yopin!</b>\n"
        msg += f"\n<i>🕐 {datetime.now(pytz.timezone('Asia/Tashkent')).strftime('%H:%M')}</i>"
        return msg
