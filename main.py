import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Telegram Bot Bilgileri
TELEGRAM_BOT_TOKEN = "8809685206:AAEkCfzyjMKc622Z7nR5tvtzIYnjFGYKY-k"
TELEGRAM_CHAT_ID = "8600131877"

def send_telegram_signal(data):
    """Gelen veriyi Telegram mesajına dönüştürüp gönderir."""
    ticker = data.get("ticker", "THYAO")
    price = data.get("price", "0")
    analyst_score = data.get("analyst_score", "%88 Boğa")

    caption = (
        f"🚨 <b>OTOMATİK SİNYAL ALINDI (BULUT SUNUCU)</b> 🚨\n\n"
        f"📌 <b>Hisse/Sembol:</b> {ticker}\n"
        f"💵 <b>Fiyat Seviyesi:</b> {price}\n"
        f"📊 <b>Analist Skoru:</b> {analyst_score}\n\n"
        f"⚙️ <i>Sistem kurgunuza göre işlem yapılması onaylanıyor mu?</i>"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Onayla (AL)", "callback_data": f"buy_{ticker}"},
                {"text": "❌ İptal Et", "callback_data": f"cancel_{ticker}"}
            ]
        ]
    }

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": caption,
        "parse_mode": "HTML",
        "reply_markup": reply_markup
    }

    try:
        response = requests.post(url, json=payload)
        res_data = response.json()
        print("Telegram API Yanıtı:", res_data)
        return res_data.get("ok", False)
    except Exception as e:
        print("Telegram mesajı gönderilirken hata oluştu:", e)
        return False

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or {}
    print("Gelen Webhook Verisi:", data)
    
    success = send_telegram_signal(data)
    if success:
        return jsonify({"status": "success", "message": "Telegram bildirimi gönderildi"}), 200
    else:
        return jsonify({"status": "error", "message": "Telegram bildirimi başarısız"}), 500

@app.route("/", methods=["GET"])
def home():
    return "Otonom Bot Sunucusu 7/24 Aktif!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)