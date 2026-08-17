import os
import threading
import logging
import requests
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
    # BIST Hisseleri (.IS)
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

def fetch_chart_data(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            result = data['chart']['result'][0]
            timestamps = result['timestamp']
            quote = result['indicators']['quote'][0]
            df = pd.DataFrame({
                'Date': pd.to_datetime(timestamps, unit='s'),
                'Close': quote['close'],
                'Volume': quote['volume']
            })
            df = df.dropna(subset=['Close']).reset_index(drop=True)
            return df
    except Exception as e:
        logging.error(f"{symbol} veri çekme hatası: {e}")
    return pd.DataFrame()

def send_telegram_message(text):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        try:
            res = requests.post(url, json=payload, timeout=10)
            res.raise_for_status()
            logging.info("Telegram mesajı gönderildi.")
        except Exception as e:
            logging.error(f"Telegram mesaj gönderme hatası: {e}")

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_backtest():
    logging.info("Backtest simülasyonu başlatıldı (Stop %3)...")
    total_trades = 0
    winning_trades = 0
    processed_count = 0
    
    for symbol in WATCHLIST:
        try:
            df = fetch_chart_data(symbol)
            if df.empty or len(df) < 210:
                continue

            processed_count += 1
            sma200 = df['Close'].rolling(200).mean()
            rsi = calculate_rsi(df['Close'])

            start_idx = max(200, len(df) - 120)
            end_idx = len(df) - 10

            for i in range(start_idx, end_idx):
                close = float(df['Close'].iloc[i])
                sma = float(sma200.iloc[i])
                sma_past = float(sma200.iloc[i-15])
                r = float(rsi.iloc[i])

                if close > sma and sma > sma_past and r < 70:
                    total_trades += 1
                    target = close * 1.05
                    stop = sma * 0.97  # Stop %3

                    future_prices = df['Close'].iloc[i+1:i+11].values
                    hit_target = any(future_prices >= target)
                    hit_stop = any(future_prices <= stop)

                    if hit_target and not hit_stop:
                        winning_trades += 1
        except Exception as b_err:
            logging.error(f"Backtest hatası {symbol}: {b_err}")

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    msg = (
        f"📈 GEÇMİŞE DÖNÜK BAŞARIM TESTİ (STOP %3)\n\n"
        f"Başarıyla İşlenen Sembol: {processed_count}/{len(WATCHLIST)}\n"
        f"Toplam Üretilen Sinyal: {total_trades}\n"
        f"Başarılı İşlem (TP1 %5): {winning_trades}\n"
        f"Kazanma Oranı (Win Rate): %{win_rate:.1f}\n\n"
        f"Veri Mimarisi: Direct v8 JSON Engine"
    )
    send_telegram_message(msg)

def start_async_backtest():
    thread = threading.Thread(target=run_backtest)
    thread.start()

@app.route('/', methods=['GET'])
def home():
    return f"Otonom Bot Active! Takip Edilen Enstrüman Sayısı: {len(WATCHLIST)}", 200

@app.route('/backtest', methods=['GET', 'POST'])
def manual_backtest():
    start_async_backtest()
    return jsonify({"status": "backtest_initiated_async"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
