import os
import json
import requests
import yfinance as yf
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from google import genai

app = Flask(__name__)

# --- AYARLAR VE TOKEN BİLGİLERİ ---
TELEGRAM_BOT_TOKEN = "8809685206:AAEkCfzyjMKc622Z7nR5tvtzIYnjFGYKY-k"
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "MEVCUT_CHAT_ID_BURAYA")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "BURAYA_GEMINI_API_KEY")

POZISYON_DOSYASI = "aktif_pozisyonlar.json"

def pozisyonlari_yukle():
    if os.path.exists(POZISYON_DOSYASI):
        try:
            with open(POZISYON_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def pozisyonlari_kaydet(veri):
    try:
        with open(POZISYON_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Pozisyon kayıt hatası: {e}")

def telegram_mesaj_gonder_butonlu(mesaj: str, reply_markup=None, hedef_id=None):
    chat_id = hedef_id if hedef_id else TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mesaj,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Telegram mesaj hatası: {e}")

def guvenli_veri_ve_teknik_cek(sembol):
    fiyat = None
    rsi = None
    try:
        tiker = yf.Ticker(sembol)
        df = tiker.history(period="1mo")
        if df is not None and not df.empty:
            fiyat = float(df['Close'].iloc[-1])
            close = df['Close']
            if len(close) >= 14:
                delta = close.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi_series = 100 - (100 / (1 + rs))
                rsi = float(rsi_series.iloc[-1])
    except Exception as e:
        print(f"yfinance hata ({sembol}): {e}")
    return fiyat, rsi

# --- TARAMA VE AKILLI AÇIKLAMALI RAPORLAMA ---
def tum_taramalari_calistir(hedef_id=None):
    # 1. Aktif Takip Edilen Pozisyonların Güncel Durumu
    aktif_pos = pozisyonlari_yukle()
    if aktif_pos:
        pos_rapor = "📊 *AKTİF POZİSYONLARINIZ VE TP/SL TAKİBİ*\n\n"
        for sembol, detay in aktif_pos.items():
            fiyat, rsi = guvenli_veri_ve_teknik_cek(detay['sembol'])
            if fiyat and str(fiyat) != "nan":
                fiyat_fark = ((fiyat - detay['maliyet']) / detay['maliyet']) * 100
                pos_rapor += f"📌 *{detay['isim']}*\n" \
                             f"   Maliyet: {detay['maliyet']:.2f} | Güncel: {fiyat:.2f} (%{fiyat_fark:+.2f})\n" \
                             f"   Hedef TP: {detay['tp']} | Zarar Kes SL: {detay['sl']}\n" \
                             f"   -----------------------------------\n"
            else:
                pos_rapor += f"📌 *{detay['isim']}*: Fiyat bekleniyor...\n"
        telegram_mesaj_gonder_butonlu(pos_rapor, None, hedef_id)

    # 2. Taktiksel Fırsatlar ve Akıllı Yönlendirme
    taktiksel_liste = {
        "NVIDIA (NVDA)": "NVDA",
        "Palantir (PLTR)": "PLTR",
        "MP Materials (MP)": "MP",
        "Resource Holding (REXC)": "REXC"
    }
    
    for isim, sembol in taktiksel_liste.items():
        fiyat, rsi = guvenli_veri_ve_teknik_cek(sembol)
        if fiyat and rsi and str(fiyat) != "nan":
            onerilen_tp = round(fiyat * 1.10, 2)
            onerilen_sl = round(fiyat * 0.93, 2)
            
            # İstediğin net ve kısa akıllı yönlendirme mantığı
            if rsi > 70:
                strateji_notu = "🔴 *Aşırı Primli:* Elinde varsa kâr al, elinde yoksa alma bekle."
            elif rsi < 35:
                strateji_notu = "🟢 *Dip / Fırsat Bölgesi:* Elinde yoksa kademeli al, elinde varsa tut."
            else:
                strateji_notu = "⚖️ *Dengeli / Bekle-Gör:* Nötr bölgede, acele etme."
            
            durum_metni = (
                f"🎯 *Taktiksel Sinyal: {isim}*\n"
                f"💰 Güncel Fiyat: {fiyat:.2f} | RSI: {rsi:.1f}\n"
                f"💡 {strateji_notu}\n\n"
                f"📈 Önerilen TP: {onerilen_tp} | SL: {onerilen_sl}\n"
                f"Bu işlemi açtıysan aşağıdaki butonla takibe alabilirsin:"
            )
            
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Aldım / Takibe Başla", "callback_data": f"AL|{sembol}|{isim}|{fiyat}|{onerilen_tp}|{onerilen_sl}"}
                    ],
                    [
                        {"text": "❌ Takibi Bırak (Pozisyonu Kapat)", "callback_data": f"SIL|{sembol}"}
                    ]
                ]
            }
            telegram_mesaj_gonder_butonlu(durum_metni, keyboard, hedef_id)

# --- OTOMATİK ZAMANLAYICI ---
def otomatik_gunluk_tarama():
    print("⏰ Otomatik günlük portföy taraması tetiklendi...")
    telegram_mesaj_gonder_butonlu("⏰ *Günlük Otomatik Portföy & Pozisyon Takip Raporu Başlatılıyor...*")
    tum_taramalari_calistir(None)

scheduler = BackgroundScheduler()
scheduler.add_job(func=otomatik_gunluk_tarama, trigger="cron", hour=9, minute=30)
scheduler.start()

@app.route("/")
def ana_sayfa():
    return "Portföy Takip & Akıllı Sinyal Botu Aktif!", 200

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    
    if data and "message" in data:
        message = data["message"]
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        if text.strip() in ["/tara", "/test", "/tara@Borsa_bot"]:
            telegram_mesaj_gonder_butonlu("🚀 *Tüm Listeler ve Aktif Pozisyonlar Taranıyor...*", None, chat_id)
            tum_taramalari_calistir(chat_id)

    elif data and "callback_query" in data:
        query = data["callback_query"]
        callback_data = query.get("data", "")
        chat_id = query.get("message", {}).get("chat", {}).get("id")
        query_id = query.get("id")
        
        parts = callback_data.split("|")
        islem = parts[0]
        
        aktif_pos = pozisyonlari_yukle()
        
        if islem == "AL":
            sembol = parts[1]
            isim = parts[2]
            maliyet = float(parts[3])
            tp = float(parts[4])
            sl = float(parts[5])
            
            aktif_pos[sembol] = {
                "sembol": sembol,
                "isim": isim,
                "maliyet": maliyet,
                "tp": tp,
                "sl": sl
            }
            pozisyonlari_kaydet(aktif_pos)
            telegram_mesaj_gonder_butonlu(f"✅ *{isim}* başarıyla aktif takip listene eklendi! Maliyet: {maliyet}, TP: {tp}, SL: {sl}", None, chat_id)
            
        elif islem == "SIL":
            sembol = parts[1]
            if sembol in aktif_pos:
                del aktif_pos[sembol]
                pozisyonlari_kaydet(aktif_pos)
            telegram_mesaj_gonder_butonlu(f"❌ *{sembol}* pozisyon takipten çıkarıldı. (Genel piyasa taramalarında görünmeye devam edecek).", None, chat_id)
            
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": query_id})
        except Exception:
            pass

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
