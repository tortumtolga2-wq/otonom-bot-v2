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

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

BOT_ACTIVE = True
PERF_LOG_FILE = "signal_performance.json"

def setup_automatic_webhook():
    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL}/{TELEGRAM_BOT_TOKEN}"
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}"
        try:
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200:
                logging.info(f"Otomatik Webhook Başarıyla Kuruldu: {webhook_url}")
        except Exception as e:
            logging.error(f"Webhook bağlantı hatası: {e}")

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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Telegram mesajı gönderilemedi: {e}")

@app.route("/")
def home():
    status = "AKTİF 🚀" if BOT_ACTIVE else "DURDURULDU 🛑"
    logs = load_performance_logs()
    active_count = len([l for l in logs if l["status"] in ["AKTİF (ONAYLANDI)", "TP1 ULAŞILDI (%50 KAPATILDI)"]])
    return f"Otonom Al-Sat Botu (V9.0 İnteraktif Portföy Onaylı) Çalışıyor. Durum: {status} | Aktif Takipteki Pozisyon: {active_count}"

# --- TELEGRAM WEBHOOK (Buton ve Komut Yönetimi) ---
@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    global BOT_ACTIVE
    update = request.get_json()
    
    if "message" in update:
        text = update["message"].get("text", "")
        if text == "/stats":
            logs = load_performance_logs()
            completed = [l for l in logs if "NİHAİ" in l["status"] or "ZARAR" in l["status"]]
            wins = [l for l in completed if "NİHAİ" in l["status"]]
            win_rate = (len(wins) / len(completed) * 100) if completed else 0.0
            send_telegram_message(f"📊 *Portföy Başarı İstatistikleri*\n• Takip Edilen Toplam Sinyal: `{len(logs)}`\n• Sonuçlanan: `{len(completed)}`\n• Başarı Oranı: `% {win_rate:.1f}`")
        elif text == "/reset":
            if os.path.exists(PERF_LOG_FILE):
                os.remove(PERF_LOG_FILE)
            send_telegram_message("🗑️ *Portföy logları sıfırlandı.*")
        elif text == "/panic":
            BOT_ACTIVE = False
            send_telegram_message("🛑 *PANİK MODU AKTİF!*")
        elif text == "/resume":
            BOT_ACTIVE = True
            send_telegram_message("🚀 *Sistem Yeniden Aktif!*")
            
    elif "callback_query" in update:
        callback = update["callback_query"]
        data = callback["data"]
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        
        # Buton aksiyonlarını yönet
        if data.startswith("buy_"):
            symbol = data.split("_")[1]
            # Loglarda ilgili sembolü "BEKLEMEDE"den "AKTİF (ONAYLANDI)" durumuna geçir
            logs = load_performance_logs()
            updated = False
            for log in logs:
                if log["symbol"] == symbol and log["status"] == "BEKLEMEDE (ONAY BEKLİYOR)":
                    log["status"] = "AKTİF (ONAYLANDI)"
                    updated = True
                    break
            if updated:
                save_performance_logs(logs)
                send_telegram_message(f"✅ *{symbol} için alım onaylandı!* Portföy takibi ve Trailing Stop mekanizması başlatıldı.")
            
        elif data.startswith("ignore_"):
            symbol = data.split("_")[1]
            logs = load_performance_logs()
            logs = [l for l in not_matched if l["symbol"] != symbol or l["status"] != "BEKLEMEDE (ONAY BEKLİYOR)"]
            # Alternatif filtreleme:
            logs = [l for l in logs if not (l["symbol"] == symbol and l["status"] == "BEKLEMEDE (ONAY BEKLİYOR)")]
            save_performance_logs(logs)
            send_telegram_message(f"❌ *{symbol} sinyali reddedildi.* Takibe alınmadı.")

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
        status = log["status"]
        # Sadece kullanıcı tarafından "Aldım" onay verilmiş pozisyonları takip et!
        if status in ["AKTİF (ONAYLANDI)", "TP1 ULAŞILDI (%50 KAPATILDI)"]:
            symbol = log["symbol"]
            entry = log["entry_price"]
            tp1 = log["tp1_price"]
            tp2 = log["tp2_price"]
            sl = log["sl_price"]
            
            try:
                df = yf.download(symbol, period="5d", interval="1d", progress=False)
                if df is None or df.empty:
                    continue
                high = float(df['High'].iloc[-1])
                low = float(df['Low'].iloc[-1])
                
                if status == "AKTİF (ONAYLANDI)" and high >= tp1:
                    log["status"] = "TP1 ULAŞILDI (%50 KAPATILDI)"
                    log["sl_price"] = entry  # Trailing stop: Giriş fiyatına sabitlendi
                    updated = True
                    send_telegram_message(
                        f"🎯 *[PORTFÖY] KADEMELİ HEDEF 1 (TP1) ULAŞILDI!*\n"
                        f"• Sembol: `{symbol}`\n"
                        f"• Aksiyon: Pozisyonun **%50'sini sat**.\n"
                        f"• Trailing Güncellemesi: Kalan pozisyon için SL **giriş fiyatına (`{entry:.2f}`)** çekildi (Sıfır Risk!)."
                    )
                elif high >= tp2:
                    log["status"] = "NİHAİ HEDEF BAŞARILI (TP2) 🎯"
                    log["result_pnl_pct"] = ((tp2 - entry) / entry) * 100
                    updated = True
                    send_telegram_message(
                        f"🚀 *[PORTFÖY] NİHAİ HEDEF (TP2) TAMAMLANDI! (TÜMÜ KAPANDI)*\n"
                        f"• Sembol: `{symbol}`\n"
                        f"• Toplam Kâr Oranı: `+%{log['result_pnl_pct']:.2f}`"
                    )
                elif low <= sl:
                    log["status"] = "ZARAR DURDUR (SL) 🛑"
                    log["result_pnl_pct"] = ((sl - entry) / entry) * 100
                    updated = True
                    send_telegram_message(
                        f"🛑 *[PORTFÖY] ZARAR DURDUR (SL) ÇALIŞTI*\n"
                        f"• Sembol: `{symbol}`\n"
                        f"• Seviye: `{sl:.2f}`"
                    )
            except Exception as e:
                logging.error(f"{symbol} takip hatası: {e}")
                
    if updated:
        save_performance_logs(logs)

def run_strategy_check():
    if not BOT_ACTIVE:
        return
    logging.info("İnteraktif strateji taraması başlatıldı...")
    try:
        evaluate_open_signals()
        
        try:
            flow_report = analyze_market_flow()
            send_telegram_message(flow_report)
        except Exception:
            pass
            
        watchlist = get_custom_megatrend_watchlist()
        send_telegram_message(f"🔄 *Tarama Başlıyor:* `{len(watchlist)}` varlık inceleniyor...")
        
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
                    tp1_price = close + (1.5 * current_atr)
                    tp2_price = close + (3.0 * current_atr)
                    
                    sl_pct = ((close - sl_price) / close) * 100
                    tp1_pct = ((tp1_price - close) / close) * 100
                    tp2_pct = ((tp2_price - close) / close) * 100
                    
                    # Henüz onaylanmadı, beklemede ekle
                    current_logs.append({
                        "symbol": symbol,
                        "entry_price": close,
                        "tp1_price": tp1_price,
                        "tp2_price": tp2_price,
                        "sl_price": sl_price,
                        "status": "BEKLEMEDE (ONAY BEKLİYOR)",
                        "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                    })
                    
                    # İnteraktif Butonlar
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "✅ Aldım (Takibi Başlat)", "callback_data": f"buy_{symbol}"},
                                {"text": "❌ Almadım (Pas Geç)", "callback_data": f"ignore_{symbol}"}
                            ]
                        ]
                    }
                    
                    signal_msg = (
                        f"🚨 *YENİ ALIM SİNYALİ (ONAY BEKLİYOR)* 🚨\n\n"
                        f"📌 *Sembol:* `{symbol}`\n"
                        f"💵 *Giriş Fiyatı:* `{close:.2f}`\n\n"
                        f"🎯 *Hedefler:*\n"
                        f"• *TP1 (%{tp1_pct:.1f}):* `{tp1_price:.2f}`\n"
                        f"• *TP2 (%{tp2_pct:.1f}):* `{tp2_price:.2f}`\n"
                        f"• *SL (-%{sl_pct:.1f}):* `{sl_price:.2f}`\n\n"
                        f"👇 *Bu hisseyi aldın mı? Takibi başlatmak için seç:*"
                    )
                    send_telegram_message(signal_msg, reply_markup=keyboard)
                    
            except Exception as inner_e:
                logging.error(f"{symbol} hata: {inner_e}")
                continue
                
        save_performance_logs(current_logs)
        logging.info("Tarama tamamlandı.")
    except Exception as e:
        logging.critical(f"Kritik Hata: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(run_strategy_check, 'cron', hour=10, minute=0)
scheduler.add_job(run_strategy_check, 'cron', hour=14, minute=0)
scheduler.add_job(run_strategy_check, 'cron', hour=18, minute=0)
scheduler.start()

setup_automatic_webhook()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
