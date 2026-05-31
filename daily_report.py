"""
Kunlik hisobot moduli
"""

from datetime import datetime
import pytz

class DailyReport:
    def __init__(self):
        self.signals = []
        self.tz = pytz.timezone("Asia/Tashkent")

    def add_signal(self, signal: dict):
        self.signals.append({
            "direction":  signal["direction"],
            "entry":      signal["entry_zone"],
            "tp1":        signal["tp1"],
            "tp2":        signal["tp2"],
            "tp3":        signal["tp3"],
            "sl":         signal["stop_loss"],
            "strength":   signal["strength"],
            "timestamp":  signal["timestamp"],
            "tp1_hit":    False,
            "tp2_hit":    False,
            "tp3_hit":    False,
            "sl_hit":     False,
        })

    def mark_tp(self, index: int, level: int):
        if 0 <= index < len(self.signals):
            self.signals[index][f"tp{level}_hit"] = True

    def mark_sl(self, index: int):
        if 0 <= index < len(self.signals):
            self.signals[index]["sl_hit"] = True

    def generate_report(self) -> str:
        today = datetime.now(self.tz).strftime("%d.%m.%Y")
        total = len(self.signals)

        if total == 0:
            return (
                f"<b>📊 KUNLIK HISOBOT — {today}</b>\n\n"
                "Bugun hech qanday signal berilmadi.\n"
                "Bozor kuchli signal bermadi."
            )

        buy_signals  = sum(1 for s in self.signals if s["direction"] == "BUY")
        sell_signals = sum(1 for s in self.signals if s["direction"] == "SELL")
        tp1_hits     = sum(1 for s in self.signals if s["tp1_hit"])
        tp2_hits     = sum(1 for s in self.signals if s["tp2_hit"])
        tp3_hits     = sum(1 for s in self.signals if s["tp3_hit"])
        sl_hits      = sum(1 for s in self.signals if s["sl_hit"])
        avg_strength = sum(s["strength"] for s in self.signals) / total

        profitable = tp1_hits + tp2_hits + tp3_hits
        win_rate   = round((profitable / max(total, 1)) * 100)

        # Natija baho
        if win_rate >= 70:
            result_emoji = "🏆 A'LO KUN!"
        elif win_rate >= 50:
            result_emoji = "👍 YAXSHI KUN"
        else:
            result_emoji = "📉 Qiyin kun"

        report = (
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>📊 KUNLIK HISOBOT</b>\n"
            f"<b>📅 {today}</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
            f"<b>📈 Umumiy natija: {result_emoji}</b>\n\n"
            f"<b>🔢 Signallar:</b>\n"
            f"   Jami signal:   <b>{total}</b> ta\n"
            f"   🟢 BUY:        <b>{buy_signals}</b> ta\n"
            f"   🔴 SELL:       <b>{sell_signals}</b> ta\n\n"
            f"<b>🎯 Natijalar:</b>\n"
            f"   TP1 olindi:    <b>{tp1_hits}</b> ta ✅\n"
            f"   TP2 olindi:    <b>{tp2_hits}</b> ta ✅✅\n"
            f"   TP3 olindi:    <b>{tp3_hits}</b> ta ✅✅✅\n"
            f"   Stop Loss:     <b>{sl_hits}</b> ta ❌\n\n"
            f"<b>📊 Statistika:</b>\n"
            f"   Win rate:      <b>{win_rate}%</b>\n"
            f"   O'rtacha kuch: <b>{avg_strength:.1f}%</b>\n\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<i>Ertaga ham omad! 🍀</i>\n"
            f"<i>Bot 05:00 dan yana ishlaydi.</i>"
        )
        return report

    def reset(self):
        self.signals = []
