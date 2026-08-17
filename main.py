import os
import threading
import logging
import requests
import yfinance as yf
import pandas as pd
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

WATCHLIST = [
    # BIST Hisseleri
    "THYAO.IS", "GARAN.IS", "AKBNK.IS", "KCHOL.IS", "SAHOL.IS", 
    "ASELS.IS", "TUPRS.IS", "SISE.IS", "FROTO.IS", "BIMAS.IS",
    
    # EM ETF & ADR'ler
    "EEM", "VWO", "INDA", "MCHI", "EWZ", "FXI", "EZA",
    "TSM", "BABA", "VALE", "NU", "MELI", "SE",
    
    # Emtia & Makro
    "GLD", "SLV", "XLE",
    
    # ABD Devleri
    "AAPL", "MSFT", "NVDA", "BRK-B", "JPM", "PG"
]

def send_telegram_message(text):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        try:
            res = requests.post(url, json=payload, timeout=10)
            res.raise_for_status()
            logging.info("Telegram mesaji basariyla gonderildi.")
        except Exception as e:
            logging.error(f"Telegram mesaj gonderme hatasi: {e}")

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_market_scan(is_daily_summary=False):
    logging.info("Anlik piyasa taramasi baslatildi...")
    passed_symbols = []
    
    for symbol in WATCHLIST:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1y")
            
            if df.empty or len(df) < 200:
                continue

            current_price = float(df['Close'].iloc[-1])
            
            sma_200_series = df['Close'].rolling(window=200).mean()
            sma_200_current = float(sma_200_series.iloc[-1])
            sma_200_past = float(sma_200_series.iloc[-20])

            rsi_series = calculate_rsi(df['Close'])
            rsi_current = float(rsi_series.iloc[-1])

            current_volume = float(df['Volume'].iloc[-1])
            avg_volume_20 = float(df['Volume'].iloc[-21:-1].mean())
            volume_ratio = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0

            rejections = []

            if current_price < sma_200_current:
                rejections.append("Fiyat < 200 SMA")

            if sma_200_current <= sma_200_past:
                rejections.append("200 SMA Egimi Dusuk")

            if rsi_current > 70:
                rejections.append(f"RSI > 70 ({rsi_current:.1f})")

            clean_symbol = symbol.replace('.IS', '')
            currency = "TL" if ".IS" in symbol else "$"

            if len(rejections) == 0:
                passed_symbols.append(clean_symbol)
                stop_loss = sma_200_current * 0.98
                tp1 = current_price * 1.05
                tp2 = current_price * 1.10

                if not is_daily_summary:
                    msg = (
                        f"🎯 MÜKEMMEL EŞLEŞME (DALIO & MOBIUS)\n\n"
                        f"Hisse: {clean_symbol}\n"
                        f"Giriş Fiyatı: {current_price:.2f} {currency}\n"
                        f"200 SMA: {sma_200_current:.2f} {currency}\n"
                        f"RSI (14): {rsi_current:.1f} | Hacim Orani: {volume_ratio:.2f}x\n\n"
                        f"📊 RİSK YÖNETİMİ HEDEFLERİ:\n"
                        f"🛑 Stop-Loss: {stop_loss:.2f} {currency}\n"
                        f"🎯 Hedef 1 (%5): {tp1:.2f} {currency}\n"
                        f"🚀 Hedef 2 (%10): {tp2:.2f} {currency}"
                    )
                    send_telegram_message(msg)

        except Exception as symbol_err:
            logging.error(f"{symbol} analiz hatasi: {symbol_err}")

    if is_daily_summary:
        summary_msg = (
            f"🌙 GÜNLÜK PİYASA ÖZET RAPORU\n\n"
            f"Taranan Enstrüman: {len(WATCHLIST)}\n"
            f"Filtreleri Geçen: {len(passed_symbols)}\n"
            f"Aktif Sinyaller: {', '.join(passed_symbols) if passed_symbols else 'Yok'}"
        )
        send_telegram_message(summary_msg)

def run_backtest():
    logging.info("Backtest simülasyonu başlatıldı...")
    total_trades = 0
    winning_trades = 0
    
    for symbol in WATCHLIST:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1y")
            
            if df.empty or len(df) < 210:
                continue

            sma200 = df['Close'].rolling(200).mean()
            rsi = calculate_rsi(df['Close'])

            # Son 100 işlem gününü test et
            start_idx = max(200, len(df) - 100)
            end_idx = len(df) - 10

            for i in range(start_idx, end_idx):
                close = df['Close'].iloc[i]
                sma = sma200.iloc[i]
                sma_past = sma200.iloc[i-15]
                r = rsi.iloc[i]

                # Esnek Backtest Koşulları (Trend Üstünde & RSI Uygun)
                if close > sma and sma > sma_past and r < 70:
                    total_trades += 1
                    target = close * 1.05
                    stop = sma * 0.98

                    future_prices = df['Close'].iloc[i+1:i+11]
                    
                    hit_target = any(future_prices >= target)
                    hit_stop = any(future_prices <= stop)

                    if hit_target and not hit_stop:
                        winning_trades += 1

        except Exception as b_err:
            logging.error(f"Backtest hatasi {symbol}: {b_err}")

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    msg = (
        f"📈 GEÇMİŞE DÖNÜK BAŞARIM TESTİ (BACKTEST)\n\n"
        f"Test Periyodu: Son 6 Ay\n"
        f"Toplam Üretilen Sinyal: {total_trades}\n"
        f"Başarılı İşlem (TP1 %5): {winning_trades}\n"
        f"Kazanma Oranı (Win Rate): %{win_rate:.1f}\n\n"
        f"Strateji: Dalio Trend + Mobius Kriterleri"
    )
    send_telegram_message(msg)

def start_async_scan(is_daily_summary=False):
    thread = threading.Thread(target=run_market_scan, args=(is_daily_summary,))
    thread.start()

def start_async_backtest():
    thread = threading.Thread(target=run_backtest)
    thread.start()

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(run_market_scan, 'interval', minutes=15)
scheduler.add_job(run_market_scan, 'cron', hour=20, minute=0, kwargs={'is_daily_summary': True})
scheduler.start()

@app.route('/', methods=['GET'])
def home():
    return f"Otonom Bot Active! Takip Edilen Enstruman Sayisi: {len(WATCHLIST)}", 200

@app.route('/scan-now', methods=['GET', 'POST'])
def manual_scan():
    start_async_scan()
    return jsonify({"status": "scan_initiated_async", "total_symbols": len(WATCHLIST)}), 200

@app.route('/backtest', methods=['GET', 'POST'])
def manual_backtest():
    start_async_backtest()
    return jsonify({"status": "backtest_initiated_async"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
