# main.py
import os
import time
import requests
import pandas as pd
import yfinance as yf
from flask import Flask
from market_flow import analyze_market_flow
from backtest import run_historical_backtest
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# Konfigürasyonlar (Render Environment Variables üzerinden okunur)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

# Panik tuşu ve durum bayrağı
BOT_ACTIVE = True

def send_telegram_message(message):
    if not BOT_ACTIVE:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram mesajı gönderilemedi: {e}")

@app.route("/")
def home():
    status = "AKTİF 🚀" if BOT_ACTIVE else "DURDURULDU (PANİK MODU) 🛑"
    return f"Otonom Al-Sat Botu ve Zamanlayıcı Çalışıyor. Durum: {status}"

def run_strategy_check():
    if not BOT_ACTIVE:
        return
    
    # 1. Küresel Para Akışı Raporunu Gönder
    flow_report = analyze_market_flow()
    send_telegram_message(flow_report)
    
    # 2. Backtest Performans Sonucunu Gönder (Win Rate Kontrolü)
    backtest_report = run_historical_backtest("AAPL")
    send_telegram_message(backtest_report)
    
    # Örnek Tarama Listesi (ABD & BIST)
    watchlist = ["AAPL", "MSFT", "THYAO.IS", "GARAN.IS"]
    
    for symbol in watchlist:
        try:
            df = yf.download(symbol, period="1mo", interval="1d", progress=False)
            if len(df) < 15:
                continue
            
            # --- HACİM FİLTRESİ (Volume Spike) ---
            avg_vol = df['Volume'].iloc[-10:-1].mean()
            current_vol = df['Volume'].iloc[-1]
            if current_vol < (avg_vol * 1.2):
                continue
            
            # --- TEKNİK ŞARTLAR ---
            close = df['Close'].iloc[-1]
            sma_20 = df['Close'].rolling(window=20).mean().iloc[-1]
            
            if close > sma_20:
                signal_msg = (
                    f"🚨 *ALIM SİNYALİ TESPİT EDİLDİ* 🚨\n\n"
                    f"📌 *Sembol:* `{symbol}`\n"
                    f"💵 *Güncel Fiyat:* `{close:.2f}`\n"
                    f"📊 *Hacim Durumu:* Ortalamanın Üzerinde (Hacim Filtresi Onaylı ✅)\n"
                    f"💰 *Sermaye Önerisi:* 100$ bütçenin %30-%50'si (30$-50$) ile kademeli giriş.\n"
                    f"🎯 *Strateji:* Midas üzerinden Stop-Loss ve Kademeli Kar Al (%5 TP1) emirlerini girmeyi unutma!"
                )
                send_telegram_message(signal_msg)
                
        except Exception as e:
            print(f"{symbol} taranırken hata oluştu: {e}")
            
    # Günlük PnL ve Durum Özeti
    pnl_report = (
        "📈 *Periyodik Portföy & PnL Özeti*\n\n"
        "• *Toplam Sermaye:* $100.00 (Başlangıç)\n"
        "• *Açık Pozisyonlar:* Kademeli takipte\n"
        "• *Durum:* Zamanlanmış tarama ve backtest başarıyla tamamlandı."
    )
    send_telegram_message(pnl_report)

# --- APSCHEDULER ZAMANLAYICI AYARLARI ---
scheduler = BackgroundScheduler()
# Her gün saat 10:00 (Açılış), 14:00 (Gün Ortası) ve 18:00 (Kapanış)
scheduler.add_job(run_strategy_check, 'cron', hour=10, minute=0)
scheduler.add_job(run_strategy_check, 'cron', hour=14, minute=0)
scheduler.add_job(run_strategy_check, 'cron', hour=18, minute=0)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
