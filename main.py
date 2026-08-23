# main.py
import os
import time
import json
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

# Performans Log Dosyası
PERF_LOG_FILE = "signal_performance.json"

def load_performance_logs():
    if os.path.exists(PERF_LOG_FILE):
        try:
            with open(PERF_LOG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_performance_logs(logs):
    try:
        with open(PERF_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=4)
    except Exception as e:
        logging.error(f"Performans logları kaydedilemedi: {e}")

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
    logs = load_performance_logs()
    total_signals = len(logs)
    return f"Otonom Al-Sat Botu (V6.4 Performans Takipli) Çalışıyor. Durum: {status} | Toplam Takip Edilen Sinyal: {total_signals}"

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

def calculate_atr(df, period=14):
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def evaluate_open_signals():
    """
    Geçmişte üretilen sinyallerin son durumunu (TP mi oldu, SL mi oldu) kontrol eder.
    """
    logs = load_performance_logs()
    if not logs:
        return
    
    updated = False
    for log in logs:
        if log["status"] == "AKTİF":
            symbol = log["symbol"]
            entry_price = log["entry_price"]
            tp_price = log["tp_price"]
            sl_price = log["sl_price"]
            
            try:
                df = yf.download(symbol, period="5d", interval="1d", progress=False)
                if df is None or df.empty:
                    continue
                
                current_close = float(df['Close'].iloc[-1])
                current_high = float(df['High'].iloc[-1])
                current_low = float(df['Low'].iloc[-1])
                
                # Kontrol: Hedef (TP) veya Stop-Loss (SL) tetiklendi mi?
                if current_high >= tp_price:
                    log["status"] = "HEDEF BAŞARILI (TP) 🎯"
                    log["exit_price"] = tp_price
                    log["result_pnl_pct"] = ((tp_price - entry_price) / entry_price) * 100
                    updated = True
                    send_telegram_message(f"🎯 *HEDEF BAŞARIYLA ULAŞILDI (TP)*\n• Sembol: `{symbol}`\n• Kâr Oranı: `+%{log['result_pnl_pct']:.2f}`")
                elif current_low <= sl_price:
                    log["status"] = "ZARAR DURDUR (SL) 🛑"
                    log["exit_price"] = sl_price
                    log["result_pnl_pct"] = ((sl_price - entry_price) / entry_price) * 100
                    updated = True
                    send_telegram_message(f"🛑 *ZARAR DURDUR ÇALIŞTI (SL)*\n• Sembol: `{symbol}`\n• Değişim: `%{log['result_pnl_pct']:.2f}`")
            except Exception as e:
                logging.error(f"{symbol} performans kontrolü sırasında hata: {e}")
                
    if updated:
        save_performance_logs(logs)

def run_strategy_check():
    if not BOT_ACTIVE:
        logging.warning("Bot pasif durumda (Panik Modu aktif). Tarama atlandı.")
        return
    
    logging.info("Performans takip sistemli strateji taraması başlatıldı...")
    
    try:
        # Önce mevcut açık sinyallerin durumunu güncelle
        evaluate_open_signals()
        
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
        send_telegram_message(f"🔄 *Performans Takipli Tarama Başlıyor:* Toplam `{len(watchlist)}` varlık inceleniyor...")
        
        current_logs = load_performance_logs()
        
        for symbol in watchlist:
            try:
                time.sleep(1)
                
                df = yf.download(symbol, period="2mo", interval="1d", progress=False)
                if df is None or len(df) < 25:
                    continue
                
                # Hacim Filtresi
                df['Vol_Std'] = df['Volume'].rolling(window=10).std()
                df['Vol_Mean'] = df['Volume'].rolling(window=10).mean()
                
                if df['Vol_Mean'].iloc[-1] == 0 or pd.isna(df['Vol_Mean'].iloc[-1]):
                    continue
                    
                dynamic_threshold = df['Vol_Mean'].iloc[-1] + (0.5 * df['Vol_Std'].iloc[-1])
                if df['Volume'].iloc[-1] < dynamic_threshold:
                    continue 
                
                close = float(df['Close'].iloc[-1])
                sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1])
                
                df['ATR'] = calculate_atr(df)
                current_atr = float(df['ATR'].iloc[-1])
                
                if pd.isna(current_atr) or current_atr <= 0:
                    current_atr = close * 0.03
                
                if close > sma_20:
                    sl_price = close - (1.5 * current_atr)
                    tp_price = close + (2.5 * current_atr)
                    
                    sl_pct = ((close - sl_price) / close) * 100
                    tp_pct = ((tp_price - close) / close) * 100
                    
                    # Yeni sinyali performans loglarına kaydet
                    new_signal_log = {
                        "symbol": symbol,
                        "entry_price": close,
                        "tp_price": tp_price,
                        "sl_price": sl_price,
                        "status": "AKTİF",
                        "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                    }
                    current_logs.append(new_signal_log)
                    
                    signal_msg = (
                        f"🚨 *PERFORMANS TAKİPLİ ALIM SİNYALİ* 🚨\n\n"
                        f"📌 *Sembol:* `{symbol}`\n"
                        f"💵 *Giriş Fiyatı:* `{close:.2f}`\n\n"
                        f"🎯 *Hedefler (ATR Bazlı):*\n"
                        f"• *TP (±%{tp_pct:.1f}):* `{tp_price:.2f}`\n"
                        f"• *SL (±%{sl_pct:.1f}):* `{sl_price:.2f}`\n\n"
                        f"📊 *Durum:* Otomatik PnL takibine eklendi ✅"
                    )
                    send_telegram_message(signal_msg)
                    
            except Exception as inner_e:
                logging.error(f"{symbol} taranırken hata: {inner_e}")
                continue
                
        save_performance_logs(current_logs)
        
        # İstatistiksel Özet Raporu Gönder
        completed_logs = [l for l in current_logs if l["status"] != "AKTİF"]
        wins = [l for l in completed_logs if "BAŞARILI" in l["status"]]
        win_rate = (len(wins) / len(completed_logs) * 100) if completed_logs else 0.0
        
        pnl_report = (
            f"📈 *Otonom Portföy & Performans Özeti*\n\n"
            f"• *Toplam Sinyal:* `{len(current_logs)}`\n"
            f"• *Sonuçlanan İşlem:* `{len(completed_logs)}`\n"
            f"• *Başarı Oranı (Win Rate):* `% {win_rate:.1f}`\n"
            f"• *Sistem Durumu:* Aktif ve İzlemede 🟢"
        )
        send_telegram_message(pnl_report)
        logging.info("Performans tarama döngüsü başarıyla tamamlandı.")
        
    except Exception as e:
        error_msg = f"⚠️ *Kritik Hata:* `{str(e)}`"
        send_telegram_message(error_msg)
        logging.critical(f"Kritik Hata: {e}")

# --- APSCHEDULER ZAMANLAYICI AYARLARI ---
scheduler = BackgroundScheduler()
scheduler.add_job(run_strategy_check, 'cron', hour=10, minute=0)
scheduler.add_job(run_strategy_check, 'cron', hour=14, minute=0)
scheduler.add_job(run_strategy_check, 'cron', hour=18, minute=0)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
