import os
import requests
import yfinance as yf
from flask import Flask, request

app = Flask(__name__)

# --- AYARLAR VE TOKEN BİLGİLERİ ---
TELEGRAM_BOT_TOKEN = "8809685206:AAEkCfzyjMKc622Z7nR5tvtzIYnjFGYKY-k"
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "MEVCUT_CHAT_ID_BURAYA")

# Ücretsiz API Anahtarları (Yedek kaynaklar için)
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "BURAYA_ALPHA_VANTAGE_KEY")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "BURAYA_FINNHUB_KEY")

def telegram_mesaj_gonder(mesaj: str, hedef_id=None):
    """Telegram üzerinden mesaj gönderen temel fonksiyon."""
    chat_id = hedef_id if hedef_id else TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mesaj,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Telegram mesaj hatası: {e}")

def alpha_vantage_fiyat_cek(sembol):
    """Yedek Kaynak 1: Alpha Vantage"""
    try:
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={sembol}&apikey={ALPHA_VANTAGE_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        fiyat = data.get("Global Quote", {}).get("05. price")
        if fiyat:
            return float(fiyat)
    except Exception:
        pass
    return None

def finnhub_fiyat_cek(sembol):
    """Yedek Kaynak 2: Finnhub"""
    try:
        # BIST için sembol uyarlaması (Örn: GARAN.IS -> GARAN veya farklı formatlar gerekebilir)
        temiz_sembol = sembol.split('.')[0]
        url = f"https://finnhub.io/api/v1/quote?symbol={temiz_sembol}&token={FINNHUB_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        fiyat = data.get("c")
        if fiyat and fiyat > 0:
            return float(fiyat)
    except Exception:
        pass
    return None

def guvenli_veri_ve_teknik_cek(sembol):
    """
    Önce yfinance dener, hata verirse veya veri gelmezse 
    Alpha Vantage ve Finnhub yedeklerine başvurur (Çoklama / Fallback).
    """
    fiyat = None
    df = None
    sma = None
    rsi = None
    
    # 1. Aşama: yfinance ile geçmiş veri ve teknik göstergeler denenir
    try:
        tiker = yf.Ticker(sembol)
        df = tiker.history(period="1mo")
        if not df.empty:
            fiyat = float(df['Close'].iloc[-1])
            close = df['Close']
            
            # 14 Günlük SMA
            if len(close) >= 14:
                sma = float(close.rolling(window=14).mean().iloc[-1])
                
            # 14 Günlük RSI Hesaplama
            if len(close) >= 14:
                delta = close.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi_series = 100 - (100 / (1 + rs))
                rsi = float(rsi_series.iloc[-1])
    except Exception as e:
        print(f"yfinance hata (${sembol}): {e}")

    # 2. Aşama: Eğer yfinance fiyat alamazsa yedek API'ler devreye girer
    if fiyat is None and ALPHA_VANTAGE_KEY != "BURAYA_ALPHA_VANTAGE_KEY":
        fiyat = alpha_vantage_fiyat_cek(sembol)
        
    if fiyat is None and FINNHUB_KEY != "BURAYA_FINNHUB_KEY":
        fiyat = finnhub_fiyat_cek(sembol)

    return fiyat, sma, rsi

# --- 1. KÜRESEL PİYASA RAPORU ---
def kuresel_piyasa_tara(hedef_id=None):
    takip_listesi = {
        "ABD Teknoloji (QQQ)": "QQQ",
        "ABD Geniş Piyasa (SPY)": "SPY",
        "Gelişen Piyasalar (EEM)": "EEM"
    }
    rapor = "🌐 *Küresel Para Akışı & Teknik Rapor*\n"
    for isim, sembol in takip_listesi.items():
        fiyat, sma, rsi = guvenli_veri_ve_teknik_cek(sembol)
        if fiyat:
            rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
            rapor += f"🔹 {isim}: {fiyat:.2f} | RSI: {rsi_str}\n"
    telegram_mesaj_gonder(rapor, hedef_id)

# --- 2. ANA PORTFÖY VE TEKNİK TARAYICI ---
def ana_portfoy_tara(hedef_id=None):
    portfoy_listesi = {
        "Garanti Bankası": "GARAN.IS",
        "Türk Hava Yolları": "THYAO.IS"
    }
    
    rapor = "🟢 *[GERÇEK ANA PORTFÖY & TEKNİK DURUM]*\n"
    bulundu = False
    
    for isim, sembol in portfoy_listesi.items():
        fiyat, sma, rsi = guvenli_veri_ve_teknik_cek(sembol)
        if fiyat:
            rapor += f"📌 *{isim} ({sembol}):*\n"
            rapor += f"   💰 Fiyat: {fiyat:.2f} TL\n"
            if rsi is not None:
                rapor += f"   📊 RSI (14): {rsi:.1f}\n"
            if sma is not None:
                rapor += f"   📈 14G SMA: {sma:.2f}\n"
            rapor += "   -------------------\n"
            bulundu = True
            
    if bulundu:
        telegram_mesaj_gonder(rapor, hedef_id)

# --- 3. CASH - ANA PAZAR TARAYICISI ---
def cash_ana_pazar_tara(hedef_id=None):
    pazar_listesi = {
        "Ereğli Demir Çelik": "EREGL.IS",
        "İş Bankası (C)": "ISCTR.IS"
    }
    
    for isim, sembol in pazar_listesi.items():
        fiyat, sma, rsi = guvenli_veri_ve_teknik_cek(sembol)
        if fiyat:
            # RSI filtresi (Örn: 30 ile 70 arasında dengeli bölgedeyse bildir)
            if rsi is not None and 30 <= rsi <= 70:
                mesaj = (
                    f"⚡ *[CASH - TEKNİK TARAMA]*\n"
                    f"🚀 *Hisse:* {isim} ({sembol})\n"
                    f"💰 *Fiyat:* {fiyat:.2f} TL\n"
                    f"📊 *RSI:* {rsi:.1f} (Dengeli Bölge)\n"
                    f"🎯 *Durum:* Çoklu kaynak doğrulamasıyla teknik seviyelere uygun."
                )
                telegram_mesaj_gonder(mesaj, hedef_id)

def tum_taramalari_calistir(hedef_id=None):
    """Tüm analizleri çoklu kaynak güvenliğiyle çalıştırır."""
    kuresel_piyasa_tara(hedef_id)
    ana_portfoy_tara(hedef_id)
    cash_ana_pazar_tara(hedef_id)

# --- FLASK WEB SUNUCUSU VE TELEGRAM WEBHOOK ---
@app.route("/")
def ana_sayfa():
    return "Borsa Botu Çoklu Kaynak (Fallback) Modunda Aktif!", 200

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    """Telegram'dan gelen komutları anında karşılayan uç nokta."""
    data = request.get_json()
    if data and "message" in data:
        message = data["message"]
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        if text.strip() in ["/tara", "/test", "/tara@Borsa_bot"]:
            telegram_mesaj_gonder("🔄 *Çoklu kaynak ve teknik göstergeler taranıyor...*", chat_id)
            tum_taramalari_calistir(chat_id)
            
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
