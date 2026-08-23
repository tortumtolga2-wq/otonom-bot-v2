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
    return f"Otonom Al-Sat Botu (V6.0 Özel Megatrend Sürüm) Çalışıyor. Durum: {status}"

def get_custom_megatrend_watchlist():
    """
    Senin Tarafından Oluşturulan Özel Megatrend ve BİST Mavi Yakalı Havuzu
    """
    watchlist = [
        # Senin Görsellerdeki Özel Varlıkların (Nükleer, eVTOL, Maden, Teknoloji)
        "OKLO", "GEV", "VST", "JOBY", "ACHR", "MP", 
        "NVDA", "AMZN", "GOOGL", "NU", "SYM", 
        "REXC", "NB", "AEM", "GBUG", "GLTR",
        # Sağlam BİST Çekirdeği
        "THYAO.IS", "EREGL.IS", "ASELS.IS", "GARAN.IS", "AKBNK.IS"
    ]
    return watchlist

def run_strategy_check():
    if not BOT_ACTIVE:
        return
    
    try:
        # 1. Küresel Para Akışı & Sektör Dağılımı Raporu
        flow_report = analyze_market_flow()
        send_telegram_message(flow_report)
        
        # 2. Backtest Performans Raporu (Win Rate Kontrolü)
        backtest_report = run_historical_backtest("NVDA")
        send_telegram_message(backtest_report)
        
        # 3. Özel Megatrend Varlık Listesini Al
        watchlist = get_custom_megatrend_watchlist()
        send_telegram_message(f"🔄 *Özel Megatrend Havuzu Aktif ({len(watchlist)} Varlık):*\n`{', '.join(watchlist[:10])}...`")
        
        for symbol in watchlist:
            try:
                df = yf.download(symbol, period="1mo", interval="1d", progress=False)
                if len(df) < 20:
                    continue
                
                # --- DİNAMİK HACİM FİLTRESİ ---
                df['Vol_Std'] = df['Volume'].rolling(window=10).std()
                df['Vol_Mean'] = df['Volume'].rolling(window=10).mean()
                dynamic_threshold = df['Vol_Mean'].iloc[-1] + (0.5 * df['Vol_Std'].iloc[-1])
                current_vol = df['Volume'].iloc[-1]
                
                if current_vol < dynamic_threshold:
                    continue 
                
                # --- TEKNİK ŞARTLAR & TP/SL HESAPLAMA ---
                close = float(df['Close'].iloc[-1])
                sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1])
                
                if close > sma_20:
                    # Nokta Atışı Risk & Hedef Seviyeleri (%5 TP / %3 SL)
                    tp_price = close * 1.05
                    sl_price = close * 0.97
                    
                    signal_msg = (
                        f"🚨 *PROFESYONEL ALIM SİNYALİ* 🚨\n\n"
                        f"📌 *Sembol:* `{symbol}`\n"
                        f"💵 *Güncel / Giriş Fiyatı:* `{close:.2f}`\n"
                        f"📊 *Hacim Durumu:* Dinamik Eşik Aşıldı (Akıllı Filtre Onaylı ✅)\n\n"
                        f"🎯 *Risk & Hedef Seviyeleri:*\n"
                        f"• *Hedef Kar (TP1 - %5):* `{tp_price:.2f}` *(Yarısını burada sat)*\n"
                        f"• *Zarar Durdur (Stop-Loss - %3):* `{sl_price:.2f}` *(Kritik sınır)*\n\n"
                        f"💰 *Strateji:* 100$ bütçenin %30-%50'si ile kademeli giriş. Hedefe ulaşınca kalanı maliyete çek (Trailing Stop)!"
                    )
                    send_telegram_message(signal_msg)
                    
            except Exception as e:
                print(f"{symbol} taranırken veri hatası: {e}")
                
        # Günlük PnL Özeti
        pnl_report = (
            "📈 *Otonom Portföy & PnL Özeti*\n\n"
            "• *Toplam Sermaye:* $100.00\n"
            "• *Sistem Durumu:* Özel Megatrend Sepeti Aktif 🟢"
        )
        send_telegram_message(pnl_report)
        
    except Exception as e:
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
