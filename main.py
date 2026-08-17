import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def apply_dalio_mobius_filters(data):
    """
    Ray Dalio & Mark Mobius Yatırım Felsefeleri Filtre Motoru
    """
    try:
        price = float(data.get('price', 0))
    except (ValueError, TypeError):
        price = 0.0

    # Analist skoru içerisindeki sayısal değeri güvenli şekilde çıkarma
    raw_score = str(data.get('analyst_score', '0'))
    score = 50.0
    for token in raw_score.replace('%', '').split():
        try:
            score = float(token)
            break
        except ValueError:
            continue

    try:
        sma_200 = float(data.get('sma_200', price * 0.95))
    except (ValueError, TypeError):
        sma_200 = price * 0.95

    try:
        pe_ratio = float(data.get('pe_ratio', 8.5))
    except (ValueError, TypeError):
        pe_ratio = 8.5

    rejections = []

    # Ray Dalio Filtresi: Trend Kontrolü
    if price < sma_200:
        rejections.append("Ray Dalio Filtresi: Fiyat 200 SMA altında (Makro Ayı Trendi).")

    # Mark Mobius Filtresi: Değerleme Kontrolü
    if pe_ratio > 20:
        rejections.append("Mark Mobius Filtresi: F/K oranı çok yüksek (>20 Değerleme Riski).")
    
    if score < 70:
        rejections.append(f"Analist / Sistem skoru yetersiz (%{score:.0f} < %70).")

    passed = len(rejections) == 0
    return passed, rejections

@app.route('/', methods=['GET'])
def home():
    return "Otonom Bot Sunucusu 7/24 Aktif! (Strateji Filtreleri Aktif)", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True) or {}
    ticker = data.get('ticker', 'BILINMIYOR')
    price = data.get('price', '0.00')
    score = data.get('analyst_score', 'N/A')

    is_approved, reason_list = apply_dalio_mobius_filters(data)

    if is_approved:
        status_header = "✅ <b>ONAYLANDI (DALIO & MOBIUS FILTRESI)</b>"
        action_text = "<b>Islem Durumu:</b> AL Sinyali Stratejiye Uygun!"
    else:
        status_header = "⚠️ <b>SINYAL REDDEDILDI (RISK FILTRESI)</b>"
        reasons = "\n".join([f"• {r}" for r in reason_list])
        action_text = f"<b>Red Nedenleri:</b>\n{reasons}"

    message = (
        f"{status_header}\n\n"
        f"<b>Hisse:</b> {ticker}\n"
        f"<b>Fiyat:</b> {price} TL\n"
        f"<b>Analiz Skoru:</b> {score}\n\n"
        f"{action_text}"
    )

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            res = requests.post(url, json=payload, timeout=5)
            print("Telegram Yanit:", res.status_code, res.text)
        except Exception as e:
            print("Telegram mesaj hatasi:", e)

    return jsonify({"status": "processed", "approved": is_approved, "received": data}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
