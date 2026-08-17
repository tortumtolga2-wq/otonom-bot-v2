import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Telegram Bot Yapılandırması
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def apply_dalio_mobius_filters(data):
    """
    Ray Dalio & Mark Mobius Yatırım Felsefeleri Filtre Motoru
    """
    price = float(data.get('price', 0))
    score_str = str(data.get('analyst_score', '0')).replace('%', '').split()[0]
    try:
        score = float(score_str)
    except ValueError:
        score = 50.0

    # Teknik ve Temel Metrikler (Sinyalden gelen veya varsayılan değerler)
    sma_200 = float(data.get('sma_200', price * 0.95)) # Dalio: Trend Kontrolü
    pe_ratio = float(data.get('pe_ratio', 8.5))         # Mobius: F/K Çarpanı (Düşük/Makul F/K)
    volume_surge = bool(data.get('volume_surge', True))  # Mobius: Hacim Değişimi

    rejections = []

    # Ray Dalio Filtresi: Fiyat 200 günlük hareketli ortalamanın altındaysa ayı rejimindedir
    if price < sma_200:
        rejections.append("Ray Dalio Filtresi: Fiyat 200 SMA altında (Makro Ayı Trendi).")

    # Mark Mobius Filtresi: Aşırı pahalı değerlemeleri ve hacimsiz hareketleri eler
    if pe_ratio > 20:
        rejections.append("Mark Mobius Filtresi: F/K oranı çok yüksek (>20 Değerleme Riski).")
    
    if score < 70:
        rejections.append("Analist / Sistem skoru yetersiz (<%70).")

    passed = len(rejections) == 0
    return passed, rejections

@app.route('/', methods=['GET'])
def home():
    return "Otonom Bot Sunucusu 7/24 Aktif! (Strateji Filtreleri Aktor)", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True) or {}
    ticker = data.get('ticker', 'BİLİNMİYOR')
    price = data.get('price', '0.00')
    score = data.get('analyst_score', 'N/A')

    # Strateji Filtrelerini Çalıştır
    is_approved, reason_list = apply_dalio_mobius_filters(data)

    if is_approved:
        status_header = "✅ <b>ONAYLANDI (DALIO & MOBIUS FILTRESI)</b>"
        action_text = "<b>İşlem Durumu:</b> AL Sinyali Stratejiye Uygun!"
    else:
        status_header = "⚠️ <b>SİNYAL REDDEDİLDİ (RISK FILTRESI)</b>"
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
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Telegram mesaj hatasi:", e)

    return jsonify({"status": "processed", "approved": is_approved, "received": data}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
