import os
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

def run_market_scan():
    print("Otomatik piyasa taramasi baslatildi (Batch Mode)...")
    try:
        # Tek bir istekte tüm sembollerin 1 yıllık verisini çek (Rate-limit engelini aşar)
        data = yf.download(WATCHLIST, period="1y", group_by='ticker', threads=True)
        
        for symbol in WATCHLIST:
            try:
                # Toplu veriden ilgili sembolü çek
                df = data[symbol] if len(WATCHLIST) > 1 else data
                df = df.dropna(subset=['Close'])
                
                if df.empty or len(df) < 200:
                    continue

                current_price = float(df['Close'].iloc[-1])
                sma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])

                rejections = []
                if current_price < sma_200:
                    rejections.append("200 SMA altinda")

                clean_symbol = symbol.replace('.IS', '')
                currency = "TL" if ".IS" in symbol else "$"

                if len(rejections) == 0:
                    msg = (
                        f"✅ ONAYLANDI (DALIO TREND FILTRESI)\n\n"
                        f"Hisse: {clean_symbol}\n"
                        f"Fiyat: {current_price:.2f} {currency}\n"
                        f"200 SMA: {sma_200:.2f} {currency}\n\n"
                        f"Durum: Yükseliş Trendi Onaylandı!"
                    )
                    send_telegram_message(msg)

            except Exception as e:
                print(f"{symbol} analiz hatasi:", e)

    except Exception as e:
        print("Toplu veri çekme hatası:", e)

def start_async_scan():
    # Sunucu zaman aşımını önlemek için arka plan thread kullanımı
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
