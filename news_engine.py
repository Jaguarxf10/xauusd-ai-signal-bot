"""
news_engine.py — Oltin yangiliklari, texnik tahlil va AI rasm generatori
"""
import json
import re
import httpx
import logging
import base64
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Tashkent"
tz = pytz.timezone(TIMEZONE)


class NewsEngine:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self):
        return {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }

    async def _call_claude(self, system: str, user: str, model="claude-sonnet-4-6", max_tokens=1500) -> str:
        """Claude API ga so'rov yuboradi."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=self._headers(),
                    json={
                        'model': model,
                        'max_tokens': max_tokens,
                        'system': system,
                        'tools': [{'type': 'web_search_20250305', 'name': 'web_search'}],
                        'messages': [{'role': 'user', 'content': user}]
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                return ''.join(
                    b.get('text', '') for b in data.get('content', [])
                    if b.get('type') == 'text'
                )
        except Exception as e:
            logger.error(f"Claude API xatosi: {e}")
            return ""

    # ─────────────────────────────────────────────
    # 1. OLTIN YANGILIKLARI (har 2 soatda)
    # ─────────────────────────────────────────────
    async def get_gold_news(self) -> dict | None:
        """So'nggi oltin yangiligini oladi."""
        system = """Sen moliyaviy jurnalist va XAU/USD (oltin) mutaxassisissan.
Web search orqali so'nggi 2 soatdagi oltinga oid yangilikllarni topib, o'zbek tilida yoz.

Javobingni FAQAT JSON formatida ber (markdown yoki kod bloki yo'q):
{
  "found": true,
  "headline": "Qisqa sarlavha (emoji bilan, max 80 belgi)",
  "body": "Xabar matni (3-4 gap, o'zbek tilida, qiziqarli va ma'lumotli)",
  "impact": "bullish" yoki "bearish" yoki "neutral",
  "impact_emoji": "📈" yoki "📉" yoki "➡️",
  "source": "Manba nomi",
  "image_prompt": "DALL-E uchun ingliz tilida rasm tavsifi (oltin, bozor, grafik mavzusida, professional)"
}

Agar yangilik bo'lmasa: {"found": false}"""

        now = datetime.now(tz)
        result = await self._call_claude(
            system,
            f"Hozir {now.strftime('%d.%m.%Y %H:%M')} Toshkent. So'nggi XAU/USD oltin yangiligini toping va JSON bering."
        )
        if not result:
            return None
        try:
            clean = re.sub(r'```json|```', '', result).strip()
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group())
            return data if data.get('found') else None
        except Exception as e:
            logger.error(f"Yangilik parse xatosi: {e}")
            return None

    # ─────────────────────────────────────────────
    # 2. TEXNIK TAHLIL (har 3 soatda)
    # ─────────────────────────────────────────────
    async def get_technical_analysis(self) -> dict | None:
        """XAU/USD chuqur texnik tahlili."""
        system = """Sen professional XAU/USD texnik tahlilchisissan.
Web search orqali hozirgi XAU/USD narxi va indikatorlarini topib, chuqur tahlil qil.

Javobni FAQAT JSON formatida ber:
{
  "price": "hozirgi narx ($)",
  "change_24h": "24 soatlik o'zgarish (masalan: +0.5%)",
  "trend": "BULLISH" yoki "BEARISH" yoki "SIDEWAYS",
  "trend_emoji": "🟢" yoki "🔴" yoki "🟡",
  "rsi": {"value": 50, "signal": "Neytral", "emoji": "⚪"},
  "macd": {"signal": "Bullish", "emoji": "📈"},
  "ema": {"signal": "Narx EMA50 ustida", "emoji": "✅"},
  "bollinger": {"signal": "O'rta chiziq yaqinida", "emoji": "📊"},
  "support": "muhim support daraja ($)",
  "resistance": "muhim resistance daraja ($)",
  "summary": "Umumiy baho (2-3 gap, o'zbek tilida, juda qiziqarli va professional)",
  "prediction": "Qisqa muddatli taxmin (1 gap)",
  "image_prompt": "Professional gold price chart analysis visualization, dark theme, technical indicators"
}"""

        now = datetime.now(tz)
        result = await self._call_claude(
            system,
            f"Vaqt: {now.strftime('%d.%m.%Y %H:%M')} Toshkent. XAU/USD texnik tahlilini bajaring."
        )
        if not result:
            return None
        try:
            clean = re.sub(r'```json|```', '', result).strip()
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if not match:
                return None
            return json.loads(match.group())
        except Exception as e:
            logger.error(f"Tahlil parse xatosi: {e}")
            return None

    # ─────────────────────────────────────────────
    # 3. QIZIQARLI OLTIN FAKTI (har 4 soatda)
    # ─────────────────────────────────────────────
    async def get_gold_fact(self) -> dict | None:
        """Oltinga oid qiziqarli ma'lumot."""
        system = """Sen moliyaviy va iqtisodiy ta'lim beruvchi ekspertsan.
XAU/USD (oltin) haqida qiziqarli, foydali, kam odamlar biladigan faktlar, strategiyalar yoki ma'lumotlar ber.

Mavzular (tasodifiy birini tanla):
- Markaziy banklar oltin zaxiralari
- Oltin va inflatsiya munosabati
- Oltin bozori tarixi
- Professional treyderlar strategiyalari
- Oltin va dollar munosabati
- Muhim oltin narx darajalari tarixi
- Oltin sezonal tendentsiyalar

FAQAT JSON:
{
  "category": "Kategoriya nomi",
  "title": "Sarlavha (emoji bilan)",
  "fact": "Qiziqarli ma'lumot (4-5 gap, o'zbek tilida, juda qiziqarli va foydali)",
  "key_insight": "Asosiy xulosa (1 gap)",
  "image_prompt": "Gold bars financial concept artistic illustration, professional"
}"""

        result = await self._call_claude(system, "Oltinga oid qiziqarli va foydali ma'lumot ber.")
        if not result:
            return None
        try:
            clean = re.sub(r'```json|```', '', result).strip()
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if not match:
                return None
            return json.loads(match.group())
        except Exception as e:
            logger.error(f"Fakt parse xatosi: {e}")
            return None

    # ─────────────────────────────────────────────
    # AI RASM GENERATSIYASI
    # ─────────────────────────────────────────────
    async def generate_image(self, prompt: str) -> bytes | None:
        """Claude API orqali SVG/placeholder rasm yaratadi."""
        try:
            # Rasm uchun SVG generatsiya (Telegram ga yuborish uchun PNG ga convert)
            # To'g'ridan-to'g'ri Anthropic image generation API ishlatamiz
            enhanced_prompt = f"{prompt}. Style: professional financial, dark background, gold and blue colors, modern design."

            # Claude bilan SVG rasm yasaymiz
            system = """Sen professional SVG rasm yaratuvchisan. 
Foydalanuvchi so'ragan mavzu bo'yicha professional, chiroyli SVG rasm yarat.
FAQAT SVG kodi ber, boshqa hech narsa yo'q. 
SVG o'lchamlari: width="800" height="450"
Ranglar: qovoq rang fon (#1a1a2e), oltin (#FFD700), ko'k (#4ECDC4), oq matn.
Professional ko'rinish, ikonlar, matn, geometrik shakllar ishlatib."""

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=self._headers(),
                    json={
                        'model': 'claude-haiku-4-5-20251001',
                        'max_tokens': 2000,
                        'system': system,
                        'messages': [{'role': 'user', 'content': f"Yarating: {enhanced_prompt}"}]
                    }
                )
                data = resp.json()
                svg_text = ''.join(b.get('text', '') for b in data.get('content', []) if b.get('type') == 'text')

            # SVG ni PNG ga convert qilish
            svg_match = re.search(r'<svg.*?</svg>', svg_text, re.DOTALL)
            if svg_match:
                svg_data = svg_match.group().encode('utf-8')
                return svg_data  # SVG ni to'g'ri qaytaramiz

            return None
        except Exception as e:
            logger.error(f"Rasm generatsiya xatosi: {e}")
            return None


class MessageFormatter:
    """Xabar formatlash uchun yordamchi sinf."""

    @staticmethod
    def format_news(news: dict) -> str:
        now = datetime.now(pytz.timezone(TIMEZONE)).strftime('%d.%m.%Y %H:%M')
        return (
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>📰 OLTIN YANGILIGI {news['impact_emoji']}</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
            f"<b>{news['headline']}</b>\n\n"
            f"{news['body']}\n\n"
            f"<b>Ta'sir:</b> {news['impact'].upper()} {news['impact_emoji']}\n"
            f"<i>📌 Manba: {news.get('source', 'Moliyaviy tahlil')}</i>\n\n"
            f"<i>🕐 {now}</i>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>"
        )

    @staticmethod
    def format_technical(ta: dict) -> str:
        now = datetime.now(pytz.timezone(TIMEZONE)).strftime('%d.%m.%Y %H:%M')
        return (
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>📊 XAU/USD TEXNIK TAHLIL</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
            f"<b>💰 Narx:</b> <code>{ta['price']}</code>  {ta.get('change_24h', '')}\n"
            f"<b>📈 Trend:</b> {ta['trend_emoji']} {ta['trend']}\n\n"
            f"<b>🔍 Indikatorlar:</b>\n"
            f"   RSI: {ta['rsi']['emoji']} {ta['rsi']['value']} — {ta['rsi']['signal']}\n"
            f"   MACD: {ta['macd']['emoji']} {ta['macd']['signal']}\n"
            f"   EMA: {ta['ema']['emoji']} {ta['ema']['signal']}\n"
            f"   Bollinger: {ta['bollinger']['emoji']} {ta['bollinger']['signal']}\n\n"
            f"<b>🛡 Support:</b> <code>{ta['support']}</code>\n"
            f"<b>⚔️ Resistance:</b> <code>{ta['resistance']}</code>\n\n"
            f"<b>💡 Xulosa:</b>\n<i>{ta['summary']}</i>\n\n"
            f"<b>🔮 Taxmin:</b> {ta['prediction']}\n\n"
            f"<i>🕐 {now}</i>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>"
        )

    @staticmethod
    def format_fact(fact: dict) -> str:
        now = datetime.now(pytz.timezone(TIMEZONE)).strftime('%d.%m.%Y %H:%M')
        return (
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>🎓 OLTIN HAQIDA BILASIZMI?</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
            f"<b>{fact['title']}</b>\n"
            f"<i>📂 {fact['category']}</i>\n\n"
            f"{fact['fact']}\n\n"
            f"<b>💎 Xulosa:</b> <i>{fact['key_insight']}</i>\n\n"
            f"<i>🕐 {now}</i>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>"
        )
