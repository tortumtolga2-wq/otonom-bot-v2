import os
import requests
import yfinance as yf
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Takip Edilecek Örnek Hisse Listesi (BIST hisseleri için .IS uzantısı kullanılır)
WATCHLIST = ["THYAO.IS", "GARAN.IS", "ASELS.IS", "EREGL.IS", "AAPL"]

def send_telegram_message(text):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text
        }
        try:
            requests.post(url, json=payload, timeout=8)
        except Exception as e:
            print("Telegram mesaj gonderme hatasi:", e)

def analyze_ticker(symbol):
    """
    yfinance üzerinden veri çekip Ray Dalio & Mark Mobius filtrelerini uygular.
    """
    try:
        ticker = yf.Ticker(symbol)
        
        # Son 1 yıllık kapanış verisi (200 SMA hesabı için)
        hist = ticker.history(period="1y")
        if hist.empty or len(hist) < 200:
            return

        current_price = hist['Close'].iloc[-1]
        sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]
        
        # Bilanço / Çarpan verileri
        info = ticker.info or {}
        pe_ratio = info.get('trailingPE', 8.5)
        if pe_ratio is None:
            pe_ratio = 8.5

        rejections = []

        # Ray Dalio Filtresi: Trend Kontrolü
        if current_price < sma_200:
            rejections.append("Ray Dalio Filtresi: Fiyat 200 SMA altinda (Makro Ayi Trendi).")

        # Mark Mobius Filtresi: Değerleme Kontrolü
        if pe_ratio > 20:
            rejections.append(f"Mark Mobius Filtresi: F/K orani cok yuksek ({pe_ratio:.1f} > 20).")

        is_approved = len(rejections) == 0

        clean_symbol = symbol.replace('.IS', '')
        
        if is_approved:
            msg = (
                f"✅ ONAYLANDI (OTOMATIK TARAMA)\n\n"
                f"Hisse: {clean_symbol}\n"
                f"Fiyat: {current_price:.2f} TL/$\n"
                f"200 SMA: {sma_200:.2f}\n"
                f"F/K: {pe_ratio:.1f}\n\n"
                f"Islem Durumu: AL Sinyali Stratejiye Uygun!"
            )
            send_telegram_message(msg)

    except Exception as e:
        print(f"{symbol} analizi sirasinda hata: {e}")

def run_market_scan():
    """
    Watchlist listesindeki tüm hisseleri sırayla tarar.
    """
    print("Otomatik piyasa taramasi baslatildi...")
    for symbol in WATCHLIST:
        analyze_ticker(symbol)

# Arka Plan Zamanlayıcısı (Her 15 dakikada bir otomatik tarama yapar)
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(run_market_scan, 'interval', minutes=15)
scheduler.start()

@app.route('/', methods=['GET'])
def home():
    return "Otonom Bot 7/24 Aktif! (yfinance Otomatik Tarayici Calisiyor)", 200

@app.route('/scan-now', methods=['GET', 'POST'])
def manual_scan():
    """
    Manuel tetikleme adresi: Tarayıcıdan bu adrese girince taramayı anında başlatır.
    """
    run_market_scan()
    return jsonify({"status": "scan_initiated", "watchlist": WATCHLIST}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    # Manuel veya dış kaynak webhooks için hazır yapı
    return jsonify({"status": "active"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
