# main.py
import os
import time
import logging
import requests
import pandas as pd
import yfinance as yf
from flask import Flask
from market_flow import analyze_market_flow
from backtest import run_historical_backtest
from apscheduler.schedulers.background import BackgroundScheduler

# --- LOGLAMA YAPILANDIRMASI ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

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
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            logging.error(f"Telegram API Hata Kodu: {response.status_code}, Yanıt: {response.text}")
    except Exception as e:
        logging.error(f"Telegram mesajı gönderilemedi (Bağlantı Hatası): {e}")

@app.route("/")
def home():
    status = "AKTİF 🚀" if BOT_ACTIVE else "DURDURULDU (PANİK MODU) 🛑"
    return f"Otonom Al-Sat Botu (V6.2 Güçlendirilmiş Hata Yönetimi) Çalışıyor. Durum: {status}"

def get_custom_megatrend_watchlist():
    """
    Özel Megatrend ve BİST Mavi Yakalı Havuzu (21 Varlık)
    """
    return [
        "OKLO", "GEV", "VST", "JOBY", "ACHR", "MP", 
        "NVDA", "AMZN", "GOOGL", "NU", "SYM", 
        "REXC", "NB", "AEM", "GBUG", "GLTR",
        "THYAO.IS", "EREGL.IS", "ASELS.IS", "GARAN.IS", "AKBNK.IS"
    ]

def run_strategy_check():
    if not BOT_ACTIVE:
        logging.warning("Bot pasif durumda (Panik Modu aktif). Tarama atlandı.")
        return
    
    logging.info("Otonom strateji taraması başlatıldı...")
    
    try:
        # 1. Küresel Para Akışı & Sektör Dağılımı Raporu
        try:
            flow_report = analyze_market_flow()
            send_telegram_message(flow_report)
        except Exception as e:
            logging.error(f"Para akışı analizi alınamadı: {e}")
        
        # 2. Backtest Performans Raporu
        try:
            backtest_report = run_historical_backtest("NVDA")
            send_telegram_message(backtest_report)
        except Exception as e:
            logging.error(f"Backtest raporu oluşturulamadı: {e}")
        
        # 3. Varlık Listesini Al ve Tara
        watchlist = get_custom_megatrend_watchlist()
        send_telegram_message(f"🔄 *Gelişmiş Tarama Başlıyor:* Toplam `{len(watchlist)}` varlık inceleniyor...")
        
        for symbol in watchlist:
            try:
                time.sleep(1)  # API hız sınırı koruması
                
                df = yf.download(symbol, period="1mo", interval="1d", progress=False)
                if df is None or len(df) < 20:
                    logging.warning(f"{symbol} için yeterli veri alınamadı.")
                    continue
                
                # --- DİNAMİK HACİM FİLTRESİ ---
                df['Vol_Std'] = df['Volume'].rolling(window=10).std()
                df['Vol_Mean'] = df['Volume'].rolling(window=10).mean()
                
                if df['Vol_Mean'].iloc[-1] == 0 or pd.isna(df['Vol_Mean'].iloc[-1]):
                    continue
                    
                dynamic_threshold = df['Vol_Mean'].iloc[-1] + (0.5 * df['Vol_Std'].iloc[-1])
                current_vol = df['Volume'].iloc[-1]
                
                if current_vol < dynamic_threshold:
                    continue 
                
                # --- TEKNİK ŞARTLAR & TP/SL HESAPLAMA ---
                close = float(df['Close'].iloc[-1])
                sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1])
                
                if close > sma_20:
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
                    logging.info(f"SİNYAL ÜRETİLDİ: {symbol} - Fiyat: {close}")
                    
            except Exception as inner_e:
                logging.error(f"{symbol} taranırken işlem hatası oluştu: {inner_e}")
                continue
                
        # Günlük PnL Özeti
        pnl_report = (
            "📈 *Otonom Portföy & PnL Özeti*\n\n"
            "• *Toplam Sermaye:* $100.00\n"
            "• *Sistem Durumu:* Hata Korumalı Gelişmiş Tarama Tamamlandı 🟢"
        )
        send_telegram_message(pnl_report)
        logging.info("Strateji tarama döngüsü başarıyla tamamlandı.")
        
    except Exception as e:
        error_msg = f"⚠️ *Sistem Kritik Hata Uyarısı:* Tarama döngüsünde istisna oluştu: `{str(e)}`"
        send_telegram_message(error_msg)
        logging.critical(f"Kritik Tarama Hatası: {e}")

# --- APSCHEDULER ZAMANLAYICI AYARLARI ---
scheduler = BackgroundScheduler()
scheduler.add_job(run_strategy_check, 'cron', hour=10, minute=0)
scheduler.add_job(run_strategy_check, 'cron', hour=14, minute=0)
scheduler.add_job(run_strategy_check, 'cron', hour=18, minute=0)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
