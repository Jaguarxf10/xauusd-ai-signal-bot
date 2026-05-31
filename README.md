# 🥇 XAU/USD AI Signal Telegram Bot

**100% AI boshqaradigan XAU/USD savdo signal boti**

---

## ⚙️ BOTNI SOZLASH — QADAMBA QADAM

### 1-QADAM: Telegram Bot yaratish

1. Telegramda **@BotFather** ni oching
2. `/newbot` yuboring
3. Bot nomi: `XAU/USD AI Signal`
4. Bot username: `xauusd_ai_signal_bot` (yoki boshqa)
5. **Token** ni nusxa oling — bu sizning `TELEGRAM_BOT_TOKEN`

### 2-QADAM: Chat ID olish

**Shaxsiy foydalanish uchun:**
- @userinfobot ga `/start` yuboring → ID ni oling

**Kanal uchun:**
- Kanalni yarating, botni admin qiling
- @username_to_id_bot orqali kanal ID sini oling (masalan: `-1001234567890`)

### 3-QADAM: Anthropic API Key olish

1. https://console.anthropic.com ga kiring
2. **API Keys** → **Create Key**
3. Kalitni nusxa oling

### 4-QADAM: Botni o'rnatish

```bash
# Python 3.10+ kerak
python --version

# Papka ichiga kiring
cd xauusd_bot

# Virtual muhit yarating (tavsiya)
python -m venv venv
source venv/bin/activate        # Linux/Mac
# yoki: venv\Scripts\activate   # Windows

# Kutubxonalarni o'rnating
pip install -r requirements.txt

# .env faylini yarating
cp .env.example .env
nano .env    # yoki Notepad bilan oching
```

### 5-QADAM: .env faylini to'ldirish

```
TELEGRAM_BOT_TOKEN=7123456789:AAFxxx...
TELEGRAM_CHAT_ID=123456789
ANTHROPIC_API_KEY=sk-ant-api03-xxx...
```

### 6-QADAM: Botni ishga tushirish

```bash
python bot.py
```

---

## 🖥️ SERVER DA ISHLATISH (tavsiya — 24/7)

### Render.com (bepul)
1. https://render.com ga boring
2. **New → Web Service**
3. GitHub repoga ulab yoki kodni yuklang
4. **Environment Variables** ga .env dan ma'lumotlarni kiriting
5. Deploy qiling

### VPS (DigitalOcean, Linode, Hetzner)
```bash
# Screen bilan fonda ishlatish
apt install screen
screen -S xaubot
python bot.py
# Ctrl+A, D — fonga qoldirish
```

### systemd service (eng ishonchli)
```ini
[Unit]
Description=XAU/USD AI Signal Bot
After=network.target

[Service]
WorkingDirectory=/home/user/xauusd_bot
EnvironmentFile=/home/user/xauusd_bot/.env
ExecStart=/home/user/xauusd_bot/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 📊 SIGNAL FORMATI

```
━━━━━━━━━━━━━━━━━━━━━━
🥇 XAU/USD · 5M SIGNAL
━━━━━━━━━━━━━━━━━━━━━━

Yo'nalish:    🟢 BUY
Signal kuchi: ⭐⭐⭐⭐⭐ (87%)

📍 Kirish zonasi:  2650.50 - 2651.20

🎯 Take Profit:
   TP1 → 2653.00  (+15 pip)
   TP2 → 2655.50  (+40 pip)
   TP3 → 2659.00  (+75 pip)

🛑 Stop Loss:  2648.00  (-25 pip)

⚠️ Risk darajasi:  PAST ⬇️
📊 R:R nisbat:  1:3

🔍 Tahlil asosi:
RSI 28 (oversold), MACD bullish cross,
EMA 9 > EMA 21, kuchli support zone...

⏰ 15.06.2025 14:35
━━━━━━━━━━━━━━━━━━━━━━
⚡ TP1 yoki TP2 olinganda bez ubitkaga qo'ying!
```

---

## ❓ MUHIM ESLATMALAR

- Bot faqat **kuchli signallarda** (≥75%) xabar yuboradi
- Signallar bozor ochiq vaqtda: **05:00 – 23:00** (Toshkent vaqti)
- Har kuni soat **23:00 da** kunlik hisobot keladi
- TP1 olinganda **SL ni bez ubitkaga** ko'chiring
- Bu bot **tahliliy yordam** beradi — savdo qarori sizniki!

---

## ⚠️ OGOHLANTIRISH

Bu bot moliyaviy maslahat bermaydi. XAU/USD savdosi yuqori xavfli. 
Faqat yo'qotishga rozi bo'lgan mablag'ingiz bilan savdo qiling.
