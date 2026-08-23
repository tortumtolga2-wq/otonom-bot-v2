# main.py
import os
import time
import json
import logging
import requests
import pandas as pd
import yfinance as yf
from flask import Flask, request
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

def send_telegram_message(message, reply_markup=None):
    if not BOT_ACTIVE:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
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
    return f"Otonom Al-Sat Botu (V7.0 Tam Entegre Sürüm) Çalışıyor. Durum: {status} | Toplam Sinyal: {total_signals}"

# --- TELEGRAM WEBHOOK (Komut ve Buton Yönetimi) ---
@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    global BOT_ACTIVE
    update = request.get_json()
    
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")
        
        if text == "/stats":
            logs = load_performance_logs()
            completed = [l for l in logs if l["status"] != "AKTİF"]
            wins = [l for l in completed if "BAŞARILI" in l["status"]]
            win_rate = (len(wins) / len(completed) * 100) if completed else 0.0
            
            stats_msg = (
                f"📊 *Bot Başarı İstatistikleri*\n\n"
                f"• *Toplam Sinyal:* `{len(logs)}`\n"
                f"• *Sonuçlanan:* `{len(completed)}`\n"
                f"• *Başarı Oranı:* `% {win_rate:.1f}`"
            )
            send_telegram_message(stats_msg)
            
        elif text == "/reset":
            if os.path.exists(PERF_LOG_FILE):
                os.remove(PERF_LOG_FILE)
            send_telegram_message("🗑️ *Performans logları sıfırlandı.*")
            
        elif text == "/panic":
            BOT_ACTIVE = False
            send_telegram_message("🛑 *PANİK MODU AKTİFLEŞTİRİLDİ!* Tüm taramalar durduruldu.")
            
        elif text == "/resume":
            BOT_ACTIVE = True
            send_telegram_message("🚀 *Sistem Yeniden Aktif!* Taramalar devam ediyor.")
            
    elif "callback_query" in update:
        callback = update["callback_query"]
        data = callback["data"]
        # İnteraktif buton yanıtları
        if data == "btn_status":
            send_telegram_message(f"🟢 Bot Durumu: Aktif\nSermaye: $100.00")
            
    return {"status": "ok"}

def get_custom_megatrend_watchlist():
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
    return tr.rolling(window=period).mean()

def evaluate_open_signals():
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
                current_high = float(df['High'].iloc[-1])
                current_low = float(df['Low'].iloc[-1])
                
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
                logging.error(f"{symbol} performans kontrol hatası: {e}")
    if updated:
        save_performance_logs(logs)

def run_strategy_check():
    if not BOT_ACTIVE:
        logging.warning("Bot pasif durumda. Tarama atlandı.")
        return
    
    logging.info("Tam entegre strateji taraması başlatıldı...")
    try:
        evaluate_open_signals()
        
        try:
            flow_report = analyze_market_flow()
            send_telegram_message(flow_report)
        except Exception as e:
            logging.error(f"Para akışı hatası: {e}")
            
        try:
            backtest_report = run_historical_backtest("NVDA")
            send_telegram_message(backtest_report)
        except Exception as e:
            logging.error(f"Backtest hatası: {e}")
            
        watchlist = get_custom_megatrend_watchlist()
        send_telegram_message(f"🔄 *Tam Donanımlı Tarama Başlıyor:* Toplam `{len(watchlist)}` varlık inceleniyor...")
        
        current_logs = load_performance_logs()
        
        for symbol in watchlist:
            try:
                time.sleep(1)
                df = yf.download(symbol, period="2mo", interval="1d", progress=False)
                if df is None or len(df) < 25:
                    continue
                
                df['Vol_Std'] = df['Volume'].rolling(window=10).std()
                df['Vol_Mean'] = df['Volume'].rolling(window=10).mean()
                if df['Vol_Mean'].iloc[-1] == 0 or pd.isna(df['Vol_Mean'].iloc[-1]):
                    continue
                    
                if df['Volume'].iloc[-1] < (df['Vol_Mean'].iloc[-1] + (0.5 * df['Vol_Std'].iloc[-1])):
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
                    
                    current_logs.append({
                        "symbol": symbol,
                        "entry_price": close,
                        "tp_price": tp_price,
                        "sl_price": sl_price,
                        "status": "AKTİF",
                        "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                    })
                    
                    # İnteraktif Buton Tanımı
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "📊 Bot Durumunu Gör", "callback_data": "btn_status"}]
                        ]
                    }
                    
                    signal_msg = (
                        f"🚨 *İNTERAKTİF ALIM SİNYALİ* 🚨\n\n"
                        f"📌 *Sembol:* `{symbol}`\n"
                        f"💵 *Giriş Fiyatı:* `{close:.2f}`\n\n"
                        f"🎯 *Hedefler (ATR Bazlı):*\n"
                        f"• *TP (+%{tp_pct:.1f}):* `{tp_price:.2f}`\n"
                        f"• *SL (-%{sl_pct:.1f}):* `{sl_price:.2f}`"
                    )
                    send_telegram_message(signal_msg, reply_markup=keyboard)
                    
            except Exception as inner_e:
                logging.error(f"{symbol} taranırken hata: {inner_e}")
                continue
                
        save_performance_logs(current_logs)
        logging.info("Tarama döngüsü başarıyla tamamlandı.")
        
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
