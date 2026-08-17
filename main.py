import os
import threading
import requests
import yfinance as yf
import pandas as pd
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

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_market_scan():
    print("Otomatik piyasa taramasi baslatildi (Gelişmiş Trend & RSI Filtreli)...")
    try:
        data = yf.download(WATCHLIST, period="1y", group_by='ticker', threads=True)
        
        for symbol in WATCHLIST:
            try:
                df = data[symbol] if len(WATCHLIST) > 1 else data
                df = df.dropna(subset=['Close'])
                
                if df.empty or len(df) < 220:
                    continue

                current_price = float(df['Close'].iloc[-1])
                
                # 200 SMA Hesaplaması ve Eğim Mantığı
                sma_200_series = df['Close'].rolling(window=200).mean()
                sma_200_current = float(sma_200_series.iloc[-1])
                sma_200_past = float(sma_200_series.iloc[-20])  # 20 işlem günü önceki 200 SMA

                # RSI (14) Hesaplaması
                rsi_series = calculate_rsi(df['Close'])
                rsi_current = float(rsi_series.iloc[-1])

                rejections = []

                # Filtre 1: Fiyat 200 SMA üzerinde mi?
                if current_price < sma_200_current:
                    rejections.append("Fiyat 200 SMA altında")

                # Filtre 2: 200 SMA yukarı yönlü eğimli mi? (Trend Yönü Onayı)
                if sma_200_current <= sma_200_past:
                    rejections.append("200 SMA eğimi aşağı/yatay")

                # Filtre 3: RSI aşırı alım bölgesinde mi? (> 70 ise riskli)
                if rsi_current > 70:
                    rejections.append(f"RSI aşırı alımda ({rsi_current:.1f})")

                clean_symbol = symbol.replace('.IS', '')
                currency = "TL" if ".IS" in symbol else "$"

                # Tüm filtrelerden geçen kaliteli sinyaller
                if len(rejections) == 0:
                    msg = (
                        f"✅ GÜÇLÜ TREND ONAYLANDI\n\n"
                        f"Hisse: {clean_symbol}\n"
                        f"Fiyat: {current_price:.2f} {currency}\n"
                        f"200 SMA: {sma_200_current:.2f} {currency}\n"
                        f"RSI (14): {rsi_current:.1f}\n\n"
                        f"Durum: Yükseliş trendi güçlü, 200 SMA eğimi yukarı ve tepe noktada değil."
                    )
                    send_telegram_message(msg)

            except Exception as e:
                print(f"{symbol} analiz hatasi:", e)

    except Exception as e:
        print("Toplu veri çekme hatası:", e)

def start_async_scan():
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
