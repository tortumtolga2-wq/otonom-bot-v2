import os
import threading
import logging
import requests
import pandas as pd
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# 32 Global Varlıktan Oluşan Tam Takip Listesi
WATCHLIST = [
    "THYAO.IS", "GARAN.IS", "AKBNK.IS", "KCHOL.IS", "SAHOL.IS", 
    "ASELS.IS", "TUPRS.IS", "SISE.IS", "FROTO.IS", "BIMAS.IS",
    "EEM", "VWO", "INDA", "MCHI", "EWZ", "FXI", "EZA",
    "TSM", "BABA", "VALE", "NU", "MELI", "SE",
    "GLD", "SLV", "XLE", "AAPL", "MSFT", "NVDA", "BRK-B", "JPM", "PG"
]

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def fetch_chart_data(symbol):
    """Yahoo Finance v8 API üzerinden günlük OHLC ve Close verisi çeker (ATR için High/Low dahil)"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            result = data['chart']['result'][0]
            quote = result['indicators']['quote'][0]
            df = pd.DataFrame({
                'Date': pd.to_datetime(result['timestamp'], unit='s'),
                'Open': quote['open'],
                'High': quote['high'],
                'Low': quote['low'],
                'Close': quote['close']
            })
            return df.dropna()
    except Exception as e:
        logging.error(f"Veri çekme hatası {symbol}: {e}")
        return pd.DataFrame()
    return pd.DataFrame()

def send_telegram_message(text):
    """Telegram üzerinden bildirim gönderir"""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
        except Exception as e:
            logging.error(f"Telegram mesajı gönderilemedi: {e}")

def calculate_rsi(series, period=14):
    """RSI indikatörünü hesaplar"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, period=14):
    """Average True Range (ATR) volatilite göstergesini hesaplar"""
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window=period).mean()

def run_backtest():
    """Dinamik ATR Volatilite Kuralları, Rejim Filtresi ve Detaylı Raporlama"""
    logging.info("Dinamik volatilite tabanlı backtest simülasyonu başlatıldı...")
    total_trades = 0
    winning_trades = 0
    processed_count = 0
    commission_rate = 0.001  # %0.1 Komisyon
    
    asset_results = {}
    
    # Piyasa Rejimi Referansı
    market_ref_symbol = "SPY" if "SPY" in WATCHLIST else WATCHLIST[0]
    market_df = fetch_chart_data(market_ref_symbol)
    market_sma200 = market_df['Close'].rolling(200).mean() if not market_df.empty else pd.Series()

    for symbol in WATCHLIST:
        try:
            df = fetch_chart_data(symbol)
            if df.empty or len(df) < 210:
                continue

            processed_count += 1
            sma200 = df['Close'].rolling(200).mean()
            rsi = calculate_rsi(df['Close'])
            atr = calculate_atr(df)

            start_idx = max(200, len(df) - 120)
            end_idx = len(df) - 10
            
            sym_trades = 0
            sym_wins = 0

            for i in range(start_idx, end_idx):
                # Ayı Piyasası Rejimi Filtresi
                if not market_sma200.empty and i < len(market_sma200):
                    if float(market_df['Close'].iloc[i]) < float(market_sma200.iloc[i]):
                        continue

                close = float(df['Close'].iloc[i])
                sma = float(sma200.iloc[i])
                sma_past = float(sma200.iloc[i-15])
                r = float(rsi.iloc[i])
                current_atr = float(atr.iloc[i]) if not pd.isna(atr.iloc[i]) else close * 0.02

                # Trend Takip Koşulları
                if close > sma and sma > sma_past and r < 70:
                    total_trades += 1
                    sym_trades += 1
                    
                    entry_price = close * (1 + commission_rate)
                    
                    # DİNAMİK RİSK KONTROLÜ: Stop mesafesi 1.5 ATR katı olarak belirlenir
                    stop = entry_price - (1.5 * current_atr)
                    target = entry_price + (2.5 * current_atr)  # Risk/Kazanç Oranı: ~1.66

                    future_highs = df['High'].iloc[i+1:i+11].values
                    future_lows = df['Low'].iloc[i+1:i+11].values
                    
                    hit_target = any(future_highs >= target)
                    hit_stop = any(future_lows <= stop)

                    if hit_target and not hit_stop:
                        winning_trades += 1
                        sym_wins += 1

            if sym_trades > 0:
                asset_results[symbol] = (sym_wins / sym_trades) * 100

        except Exception as b_err:
            logging.error(f"Dinamik risk hata detayı {symbol}: {b_err}")

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    top_assets = sorted(asset_results.items(), key=lambda x: x[1], reverse=True)[:3]
    top_str = ", ".join([f"{k} (%{v:.0f})" for k, v in top_assets]) if top_assets else "Veri Yok"

    msg = (
        f"📊 DİNAMİK ATR RİSKLİ STRATEJİ RAPORU\n\n"
        f"🌐 Rejim Referansı: {market_ref_symbol}\n"
        f"📁 Taranan Varlık: {processed_count}/{len(WATCHLIST)}\n"
        f"🎯 Toplam Sinyal: {total_trades}\n"
        f"✅ Başarılı İşlem: {winning_trades}\n"
        f"📈 Genel Başarı (Win Rate): %{win_rate:.1f}\n\n"
        f"🏆 En İyi Performans Verenler:\n{top_str}\n\n"
        f"⚙️ Parametreler: Komisyon %0.1 | Dinamik Stop (1.5x ATR) | Rejim Aktif"
    )
    send_telegram_message(msg)

@app.route('/')
def home():
    return "Trading Bot (Dinamik Volatilite Modu) Aktif ve Çalışıyor!"

@app.route('/backtest')
def manual_backtest():
    """Manuel backtest tetikleme uç noktası"""
    threading.Thread(target=run_backtest).start()
    return "Dinamik backtest arka planda başlatıldı, sonuçlar Telegram'a gönderilecektir."

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
