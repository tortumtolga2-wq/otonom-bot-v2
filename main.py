import os
import requests
import yfinance as yf
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from google import genai

app = Flask(__name__)

# --- AYARLAR VE TOKEN BİLGİLERİ ---
TELEGRAM_BOT_TOKEN = "8809685206:AAEkCfzyjMKc622Z7nR5tvtzIYnjFGYKY-k"
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "MEVCUT_CHAT_ID_BURAYA")

ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "BURAYA_ALPHA_VANTAGE_KEY")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "BURAYA_FINNHUB_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "BURAYA_GEMINI_API_KEY")

def telegram_mesaj_gonder(mesaj: str, hedef_id=None):
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
    try:
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
    fiyat = None
    sma = None
    rsi = None
    
    try:
        tiker = yf.Ticker(sembol)
        df = tiker.history(period="1mo")
        if not df.empty:
            fiyat = float(df['Close'].iloc[-1])
            close = df['Close']
            
            if len(close) >= 14:
                sma = float(close.rolling(window=14).mean().iloc[-1])
                
            if len(close) >= 14:
                delta = close.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi_series = 100 - (100 / (1 + rs))
                rsi = float(rsi_series.iloc[-1])
    except Exception as e:
        print(f"yfinance hata (${sembol}): {e}")

    if fiyat is None and ALPHA_VANTAGE_KEY != "BURAYA_ALPHA_VANTAGE_KEY":
        fiyat = alpha_vantage_fiyat_cek(sembol)
        
    if fiyat is None and FINNHUB_KEY != "BURAYA_FINNHUB_KEY":
        fiyat = finnhub_fiyat_cek(sembol)

    return fiyat, sma, rsi

# --- 1. KATEGORİ: CASH LİSTESİ (Nakit Akışı & Güçlü Temel Omurga) ---
def cash_listesi_tara(hedef_id=None):
    # Sağlam bilanço, temettü veya güçlü nakit akışı yaratan varlıklar (Dokunulmaz Çekirdek / Dip Fırsatı kollananlar)
    liste = {
        "Vistra Energy (VST)": "VST",
        "Amazon (AMZN)": "AMZN",
        "Alphabet / Google (GOOGL)": "GOOGL",
        "NVIDIA (NVDA)": "NVDA",
        "Taiwan Semiconductor (TSM)": "TSM",
        "Palantir Technologies (PLTR)": "PLTR",
        "Tesla (TSLA)": "TSLA",
        "Oklo Inc. (OKLO)": "OKLO",
        "GE Vernova (GEV)": "GEV",
        "Türk Hava Yolları (THYAO)": "THYAO.IS",
        "Koç Holding (KCHOL)": "KCHOL.IS",
        "Garanti Bankası (GARAN)": "GARAN.IS",
        "Ereğli Demir Çelik (EREGL)": "EREGL.IS",
        "Şişecam (SISE)": "SISE.IS"
    }
    rapor = "💰 *CASH LİSTESİ (Nakit Akışı & Çekirdek Omurga)*\n_(Uzun vadeli kartopu, dip alımı & kriz kalkanı)_\n\n"
    for isim, sembol in liste.items():
        fiyat, sma, rsi = guvenli_veri_ve_teknik_cek(sembol)
        if fiyat:
            rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
            durum = "🟢 Dip Bölgesi / Topla" if rsi and rsi < 40 else ("🔴 Aşırı Şişkin" if rsi and rsi > 70 else "⚖️ Dengeli")
            rapor += f"🔹 {isim}: ${fiyat if 'IS' not in sembol else fiyat} | RSI: {rsi_str} ({durum})\n"
    telegram_mesaj_gonder(rapor, hedef_id)

# --- 2. KATEGORİ: TAKTİKSEL VARLIKLAR (Takip Eden TP & SL Yönetimi) ---
def taktiksel_liste_tara(hedef_id=None):
    # Emtialar, madenler ve yüksek hareketli büyüme/spekülatif temalar
    liste = {
        "MP Materials (MP)": "MP",
        "Resource Holding (REXC)": "REXC",
        "Precious Metals ETF (GLTR)": "GLTR",
        "GBUG (GBUG)": "GBUG",
        "Maden Varlığı (NB)": "NB",
        "Agnico Eagle Mines (AEM)": "AEM",
        "Nu Holdings (NU)": "NU",
        "Symbotic (SYM)": "SYM",
        "Joby Aviation (JOBY)": "JOBY",
        "Archer Aviation (ACHR)": "ACHR"
    }
    rapor = "⚡ *TAKTİKSEL VARLIKLAR (TP / SL Takip Listesi)*\n_(Hızlı hareketli emtialar & dinamik stop-loss yönetimi)_\n\n"
    for isim, sembol in liste.items():
        fiyat, sma, rsi = guvenli_veri_ve_teknik_cek(sembol)
        if fiyat:
            rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
            rapor += f"🎯 {isim}: ${fiyat:.2f} | RSI: {rsi_str} | *(Takip Eden TP/SL Aktif)*\n"
    telegram_mesaj_gonder(rapor, hedef_id)

# --- 3. GOOGLE GEMINI AI İLE HABER & MAKRO SÜZGECİ ---
def gemini_haber_analizi_sun(hedef_id=None):
    if GEMINI_API_KEY == "BURAYA_GEMINI_API_KEY":
        telegram_mesaj_gonder("💡 *Makro Süzgeç:* Gemini API anahtarı girilmediği için standart akıllı öngörü sunuluyor.", hedef_id)
        return

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = (
            "Küresel piyasalarda yapay zeka, nükleer enerji altyapısı (OKLO, VST), madenler/emtialar (MP, REXC) "
            "ve tedarik zinciri açısından önümüzdeki dönemi değerlendir. 5-10 yıllık yatırımcı gözüyle "
            "kısa ve vurucu bir stratejik risk/fırsat analizi yap."
        )
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        analiz_metni = f"🧠 *Yapay Zeka (Gemini) Stratejik Piyasa Süzgeci*\n\n{response.text}"
        telegram_mesaj_gonder(analiz_metni, hedef_id)
    except Exception as e:
        telegram_mesaj_gonder(f"⚠️ Gemini analiz hatası: {e}", hedef_id)

def tum_taramalari_calistir(hedef_id=None):
    cash_listesi_tara(hedef_id)
    taktiksel_liste_tara(hedef_id)
    gemini_haber_analizi_sun(hedef_id)

# --- OTOMATİK ZAMANLAYICI ---
def otomatik_gunluk_tarama():
    print("⏰ Otomatik günlük portföy taraması tetiklendi...")
    telegram_mesaj_gonder("⏰ *Günlük Otomatik Portföy & Stratejik Sinyal Raporu Başlatılıyor...*")
    tum_taramalari_calistir(None)

scheduler = BackgroundScheduler()
scheduler.add_job(func=otomatik_gunluk_tarama, trigger="cron", hour=9, minute=30)
scheduler.start()

@app.route("/")
def ana_sayfa():
    return "Portföy Takip & Gemini AI Botu Aktif ve Çalışıyor!", 200

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if data and "message" in data:
        message = data["message"]
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        if text.strip() in ["/tara", "/test", "/tara@Borsa_bot"]:
            telegram_mesaj_gonder("🚀 *Manuel Anlık Portföy Raporu Hazırlanıyor...*", chat_id)
            tum_taramalari_calistir(chat_id)
            
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
