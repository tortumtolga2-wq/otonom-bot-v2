import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Telegram Bot Yapılandırması (Environment Variables)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

@app.route('/', methods=['GET'])
def home():
    return "Otonom Bot Sunucusu 7/24 Aktif!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True) or {}
    ticker = data.get('ticker', 'BİLİNMİYOR')
    price = data.get('price', '0.00')
    score = data.get('analyst_score', 'N/A')

    message = (
        f"🚨 <b>OTOMATİK SİNYAL ALINDI (BULUT SUNUCU)</b> 🚨\n\n"
        f"<b>Hisse:</b> {ticker}\n"
        f"<b>Fiyat:</b> {price} TL\n"
        f"<b>Analiz / Skor:</b> {score}\n\n"
        f"<i>İşlem onay bekliyor...</i>"
    )

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Telegram mesaj hatasi:", e)

    return jsonify({"status": "success", "received": data}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
