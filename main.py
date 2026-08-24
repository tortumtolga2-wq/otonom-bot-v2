import os
import requests
import yfinance as yf
from flask import Flask, request

app = Flask(__name__)

# --- AYARLAR VE TOKEN BİLGİLERİ ---
TELEGRAM_BOT_TOKEN = "BURAYA_BOT_TOKENINIZI_YAZIN"
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "MEVCUT_CHAT_ID_BURAYA")

# Ücretsiz API Anahtarları
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

def alpha_vantage_veri_cek(sembol):
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

def finnhub_veri_cek(sembol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={sembol}&token={FINNHUB_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        fiyat = data.get("c")
        if fiyat and fiyat > 0:
            return float(fiyat)
    except Exception:
        pass
    return None

def guvenli_veri_cek(takip_sozlugu):
    veriler = {}
    for isim, sembol in takip_sozlugu.items():
        fiyat = None
        try:
            tiker = yf.Ticker(sembol)
            df = tiker.history(period="1d")
            if not df.empty:
                fiyat = df['Close'].iloc[-1]
        except Exception:
            pass
            
        if fiyat is None and ALPHA_VANTAGE_KEY != "BURAYA_ALPHA_VANTAGE_KEY":
            fiyat = alpha_vantage_veri_cek(sembol)
            
        if fiyat is None and FINNHUB_KEY != "BURAYA_FINNHUB_KEY":
            fiyat = finnhub_veri_cek(sembol)
            
        if fiyat is not None:
            veriler[isim] = fiyat
    return veriler

# --- 1. KÜRESEL PİYASA RAPORU ---
def kuresel_piyasa_tara(hedef_id=None):
    takip_listesi = {
        "ABD Teknoloji (QQQ)": "QQQ",
        "ABD Geniş Piyasa (SPY)": "SPY",
        "Gelişen Piyasalar (EEM)": "EEM"
    }
    sonuclar = guvenli_veri_cek(takip_listesi)
    if sonuclar:
        rapor = "🌐 *Küresel Para Akışı & Sektör Raporu*\n"
        for isim, fiyat in sonuclar.items():
            rapor += f"🔹 {isim}: {fiyat:.2f}\n"
        telegram_mesaj_gonder(rapor, hedef_id)

# --- 2. ANA PORTFÖY TARAYICISI ---
def ana_portfoy_tara(hedef_id=None):
    sinyal_aktif = True 
    if sinyal_aktif:
        hisse = "GARAN" 
        fiyat = 112.50
        mesaj = (
            f"🟢 *[ANA PORTFÖY]*\n"
            f"📌 *Hisse:* {hisse}\n"
            f"💰 *Fiyat:* {fiyat} TL\n"
            f"📊 *Durum:* Uzun vadeli ana portföy takibi ve teknik seviye korunuyor."
        )
        telegram_mesaj_gonder(mesaj, hedef_id)

# --- 3. CASH - ANA PAZAR TARAYICISI ---
def cash_ana_pazar_tara(hedef_id=None):
    sinyal_bulundu = True 
    if sinyal_bulundu:
        hisse = "ORNEK_ANA_PAZAR_HISSESI"
        fiyat = 45.20
        risk_tipi = "Riskli (Yüksek Volatilite)"
        hedef_kar = "%12"
        stop_loss = "%4.5"
        
        mesaj = (
            f"⚡ *[CASH - ANA PAZAR]*\n"
            f"🚀 *Hisse:* {hisse}\n"
            f"💰 *Fiyat:* {fiyat} TL\n"
            f"⚖️ *Strateji:* {risk_tipi}\n"
            f"🎯 *Hedef Kâr:* {hedef_kar} | *Stop-Loss:* {stop_loss}\n"
            f"📊 *Not:* Hacim patlaması ve ani para girişi tespit edildi!"
        )
        telegram_mesaj_gonder(mesaj, hedef_id)

def tum_taramalari_calistir(hedef_id=None):
    """Tüm analizleri sırasıyla tetikler."""
    kuresel_piyasa_tara(hedef_id)
    ana_portfoy_tara(hedef_id)
    cash_ana_pazar_tara(hedef_id)

# --- FLASK WEB SUNUCUSU VE TELEGRAM WEBHOOK / TETİKLEYİCİ ---
@app.route("/")
def ana_sayfa():
    return "Borsa Botu Aktif ve Çalışıyor!", 200

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    """Telegram'dan gelen komutları anında karşılayan uç nokta."""
    data = request.get_json()
    if data and "message" in data:
        message = data["message"]
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        if text.strip() in ["/tara", "/test"]:
            telegram_mesaj_gonder("🔄 *Web servis üzerinden komut alındı, tarama başlatılıyor...*", chat_id)
            tum_taramalari_calistir(chat_id)
            
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
