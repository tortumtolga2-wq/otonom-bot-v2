import os
import time
import threading
import requests
import yfinance as yf
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

WATCHLIST = [
    # BIST Hisseleri
    "THYAO.IS", "GARAN.IS", "AKBNK.IS", "KCHOL.IS", "SAHOL.IS", 
    "ASELS.IS", "TUPRS.IS", "SISE.IS", "FROTO.IS", "BIMAS.IS",
    
    # Gelişmekte Olan Piyasalar (EM ETF & ADR'ler)
    "EEM", "VWO", "INDA", "MCHI", "EWZ", "FXI", "EZA",
    "TSM", "BABA", "VALE", "NU", "MELI", "SE",
    
    # Emtia ve Makro Koruma
    "GLD", "SLV", "XLE",
    
    # ABD / Küresel Devler
    "AAPL", "MSFT", "NVDA", "BRK-B", "JPM", "PG"
]

def send_telegram_message(text):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        try:
            requests.post(url, json=payload, timeout=8)
        except Exception as e:
            print("Telegram hatasi:", e)

def analyze_ticker(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y")
        
        if hist.empty or len(hist) < 200:
            return

        current_price = hist['Close'].iloc[-1]
        sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]
        
        info = ticker.info or {}
        pe_ratio = info.get('trailingPE', 8.5)
        if pe_ratio is None:
            pe_ratio = 8.5

        rejections = []

        if current_price < sma_200:
            rejections.append("200 SMA altinda")

        if pe_ratio > 20:
            rejections.append(f"F/K yüksek ({pe_ratio:.1f})")

        clean_symbol = symbol.replace('.IS', '')
        currency = "TL" if ".IS" in symbol else "$"
        
        if len(rejections) == 0:
            msg = (
                f"✅ ONAYLANDI (DALIO & MOBIUS FILTRESI)\n\n"
                f"Hisse: {clean_symbol}\n"
                f"Fiyat: {current_price:.2f} {currency}\n"
                f"200 SMA: {sma_200:.2f} {currency}\n"
                f"F/K Orani: {pe_ratio:.1f}\n\n"
                f"Islem Durumu: Stratejik Filtrelerden Gecti!"
            )
            send_telegram_message(msg)

    except Exception as e:
        print(f"{symbol} analiz hatasi:", e)

def run_market_scan():
    print("Otomatik piyasa taramasi baslatildi...")
    for symbol in WATCHLIST:
        analyze_ticker(symbol)
        time.sleep(1.5)  # yfinance rate-limit engelini asmak icin bekleme

def start_async_scan():
    # Gunicorn Zaman Asimini Önlemek Icin Arka Plan Thread'i
    thread = threading.Thread(target=run_market_scan)
    thread.start()

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(run_market_scan, 'interval', minutes=15)
scheduler.start()

@app.route('/', methods=['GET'])
def home():
    return f"Otonom Bot Active! Takip Edilen Enstruman Sayisi: {len(WATCHLIST)}", 200

@app.route('/scan-now', methods=['GET', 'POST'])
def manual_scan():
    start_async_scan()
    return jsonify({"status": "scan_initiated_async", "total_symbols": len(WATCHLIST)}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
