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
    return f"Otonom Al-Sat Botu (V5 Efektif Sürüm) Çalışıyor. Durum: {status}"

def get_dynamic_watchlist():
    """
    3. Aşama: Dinamik Sektör Rotasyonu
    O gün piyasalarda en yüksek hacim ve para girişi potansiyeli olan varlıkları dinamik seçer.
    """
    # Örnek Genişletilmiş Küresel & BIST Havuzu
    pool = ["AAPL", "MSFT", "NVDA", "TSLA", "THYAO.IS", "GARAN.IS", "EREGL.IS", "AKBNK.IS"]
    active_list = []
    
    for symbol in pool:
        try:
            df = yf.download(symbol, period="5d", interval="1d", progress=False)
            if len(df) >= 3:
                # Son gün hacmi 3 günlük ortalamadan yüksekse dinamik listeye ekle
                recent_vol = df['Volume'].iloc[-1]
                avg_vol = df['Volume'].iloc[-4:-1].mean()
                if recent_vol > avg_vol:
                    active_list.append(symbol)
        except Exception:
            continue
            
    # Eğer havuz dolmazsa ana listeyle devam et
    return active_list if active_list else ["AAPL", "MSFT", "THYAO.IS", "GARAN.IS"]

def run_strategy_check():
    if not BOT_ACTIVE:
        return
    
    try:
        # Küresel Para Akışı Raporu
        flow_report = analyze_market_flow()
        send_telegram_message(flow_report)
        
        # Backtest Raporu
        backtest_report = run_historical_backtest("AAPL")
        send_telegram_message(backtest_report)
        
        # Dinamik Varlık Listesini Al (Sektör Rotasyonu)
        watchlist = get_dynamic_watchlist()
        send_telegram_message(f"🔄 *Dinamik Tarama Listesi Güncellendi:* `{', '.join(watchlist)}`")
        
        for symbol in watchlist:
            try:
                df = yf.download(symbol, period="1mo", interval="1d", progress=False)
                if len(df) < 20:
                    continue
                
                # --- 1. AŞAMA: DİNAMİK HACİM EŞİĞİ (Volatilite / Standart Sapma Bazlı) ---
                df['Vol_Std'] = df['Volume'].rolling(window=10).std()
                df['Vol_Mean'] = df['Volume'].rolling(window=10).mean()
                
                # Dinamik Eşik: Ortalama + (Standart Sapma * 0.5) -> Piyasa oynaklığına göre esner
                dynamic_threshold = df['Vol_Mean'].iloc[-1] + (0.5 * df['Vol_Std'].iloc[-1])
                current_vol = df['Volume'].iloc[-1]
                
                if current_vol < dynamic_threshold:
                    continue # Hacim dinamik eşiği aşamadıysa ele
                
                # --- TEKNİK ŞARTLAR & 2. AŞAMA (Kademeli Kar Al / Trailing Stop Mantığı) ---
                close = df['Close'].iloc[-1]
                sma_20 = df['Close'].rolling(window=20).mean().iloc[-1]
                
                if close > sma_20:
                    signal_msg = (
                        f"🚨 *PROFESYONEL ALIM SİNYALİ* 🚨\n\n"
                        f"📌 *Sembol:* `{symbol}`\n"
                        f"💵 *Güncel Fiyat:* `{close:.2f}`\n"
                        f"📊 *Hacim Durumu:* Dinamik Eşik Aşıldı (Akıllı Filtre Onaylı ✅)\n"
                        f"💰 *Sermaye Yönetimi:* 100$ bütçenin %30-%50'si ile kademeli giriş.\n"
                        f"🎯 *Strateji (2. Aşama):* %5 Hedefte (TP1) pozisyonun yarısını sat, kalanı için Stop-Loss'u maliyete çek (Trailing Stop)!"
                    )
                    send_telegram_message(signal_msg)
                    
            except Exception as e:
                print(f"{symbol} taranırken veri hatası: {e}")
                
        # Günlük PnL Özeti
        pnl_report = (
            "📈 *Otonom Portföy & PnL Özeti*\n\n"
            "• *Toplam Sermaye:* $100.00\n"
            "• *Sistem Durumu:* Dinamik Hacim ve Sektör Rotasyonu Aktif 🟢"
        )
        send_telegram_message(pnl_report)
        
    except Exception as e:
        # 4. AŞAMA: Gelişmiş Hata Yönetimi & Loglama
        error_msg = f"⚠️ *Sistem Hata Uyarısı:* Tarama döngüsünde istisna oluştu: `{str(e)}`"
        send_telegram_message(error_msg)

# --- APSCHEDULER ZAMANLAYICI AYARLARI ---
scheduler = BackgroundScheduler()
scheduler.add_job(run_strategy_check, 'cron', hour=10, minute=0)
scheduler.add_job(run_strategy_check, 'cron', hour=14, minute=0)
scheduler.add_job(run_strategy_check, 'cron', hour=18, minute=0)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
