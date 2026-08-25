import os
import json
import requests
import yfinance as yf
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# --- AYARLAR VE TOKEN BİLGİLERİ ---
TELEGRAM_BOT_TOKEN = "8809685206:AAEkCfzyjMKc622Z7nR5tvtzIYnjFGYKY-k"
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "MEVCUT_CHAT_ID_BURAYA")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "BURAYA_GEMINI_API_KEY")

POZISYON_DOSYASI = "aktif_pozisyonlar.json"
ALARM_DURUM_DOSYASI = "alarm_durumlari.json"
TAKIP_LISTESI_DOSYASI = "taktiksel_liste.json"

VARSAYILAN_TAKIP_LISTESI = {
    "NVIDIA (NVDA)": "NVDA",
    "Palantir (PLTR)": "PLTR",
    "MP Materials (MP)": "MP",
    "Resource Holding (REXC)": "REXC"
}

def dosya_yukle(dosya_adi, varsayilan=None):
    if os.path.exists(dosya_adi):
        try:
            with open(dosya_adi, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return varsayilan if varsayilan is not None else {}

def dosya_kaydet(dosya_adi, veri):
    try:
        with open(dosya_adi, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Kayıt hatası ({dosya_adi}): {e}")

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

# --- GELİŞMİŞ TEKNİK ANALİZ MOTORU (RSI, Hacim, MACD, Bollinger) ---
def gelismis_teknik_analiz(sembol):
    fiyat = None
    rsi = None
    hacim_durumu = "NORMAL"
    macd_durumu = "NÖTR"
    bollinger_durumu = "NÖTR"
    
    try:
        tiker = yf.Ticker(sembol)
        df = tiker.history(period="2mo") # MACD ve Bollinger için biraz daha geniş veri
        if df is not None and not df.empty and len(df) >= 30:
            fiyat = float(df['Close'].iloc[-1])
            close = df['Close']
            volume = df['Volume']
            
            # 1. Hacim Analizi (Son hacim, 20 günlük ortalama hacimden yüksek mi?)
            vol_ortalama = volume.rolling(window=20).mean().iloc[-1]
            son_vol = volume.iloc[-1]
            if son_vol > (vol_ortalama * 1.3):
                hacim_durumu = "YÜKSEK (Güçlü İşlem)"
            elif son_vol < (vol_ortalama * 0.7):
                hacim_durumu = "DÜŞÜK (Sığ Piyasalar)"
            else:
                hacim_durumu = "NORMAL"

            # 2. RSI (14) Hesaplama
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi = float(rsi_series.iloc[-1])

            # 3. Bollinger Bantları (20, 2)
            sma20 = close.rolling(window=20).mean()
            std20 = close.rolling(window=20).std()
            upper_band = sma20 + (std20 * 2)
            lower_band = sma20 - (std20 * 2)
            
            if fiyat <= lower_band.iloc[-1]:
                bollinger_durumu = "ALT BANTTA (Aşırı Ucuz / Sıkışma)"
            elif fiyat >= upper_band.iloc[-1]:
                bollinger_durumu = "ÜST BANTTA (Aşırı Pahalı / Direnç)"
            else:
                bollinger_durumu = "BANT İÇİNDE"

            # 4. MACD (12, 26, 9)
            exp12 = close.ewm(span=12, adjust=False).mean()
            exp26 = close.ewm(span=26, adjust=False).mean()
            macd_line = exp12 - exp26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            
            if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
                macd_durumu = "YUKARI KESİŞİM (Pozitif Momentum 🚀)"
            elif macd_line.iloc[-1] < signal_line.iloc[-1] and macd_line.iloc[-2] >= signal_line.iloc[-2]:
                macd_durumu = "AŞAĞI KESİŞİM (Negatif Momentum ⚠️)"
            elif macd_line.iloc[-1] > signal_line.iloc[-1]:
                macd_durumu = "YUKARI TREND"
            else:
                macd_durumu = "DÜŞÜŞ TRENDİ"

    except Exception as e:
        print(f"Teknik analiz hata ({sembol}): {e}")
        
    return fiyat, rsi, hacim_durumu, macd_durumu, bollinger_durumu

# --- 1. TAM RAPORLAMA ---
def tum_taramalari_calistir(hedef_id=None):
    aktif_pos = dosya_yukle(POZISYON_DOSYASI, {})
    if aktif_pos:
        pos_rapor = "📊 *AKTİF POZİSYONLARINIZ VE TP/SL TAKİBİ*\n\n"
        for sembol, detay in aktif_pos.items():
            fiyat, rsi, _, _, _ = gelismis_teknik_analiz(detay['sembol'])
            if fiyat and str(fiyat) != "nan":
                fiyat_fark = ((fiyat - detay['maliyet']) / detay['maliyet']) * 100
                pos_rapor += f"📌 *{detay['isim']}* ({detay['sembol']})\n" \
                             f"   Maliyet: {detay['maliyet']:.2f} | Güncel: {fiyat:.2f} (%{fiyat_fark:+.2f})\n" \
                             f"   Hedef TP: {detay['tp']} | Zarar Kes SL: {detay['sl']}\n" \
                             f"   -----------------------------------\n"
            else:
                pos_rapor += f"📌 *{detay['isim']}*: Fiyat bekleniyor...\n"
        telegram_mesaj_gonder_butonlu(pos_rapor, None, hedef_id)

    taktiksel_liste = dosya_yukle(TAKIP_LISTESI_DOSYASI, VARSAYILAN_TAKIP_LISTESI)
    
    for isim, sembol in taktiksel_liste.items():
        fiyat, rsi, hacim, macd, bollinger = gelismis_teknik_analiz(sembol)
        if fiyat and rsi and str(fiyat) != "nan":
            onerilen_tp = round(fiyat * 1.10, 2)
            onerilen_sl = round(fiyat * 0.93, 2)
            
            # Profesyonel Skorlama / Strateji Notu Oluşturma
            if rsi < 35 and "ALT BANTTA" in bollinger and "YÜKSEK" in hacim:
                strateji_notu = "🟢 *ELMAS FIRSAT (Aşırı Güçlü Dip):* Hacimli satış dipte karşılandı, kademeli alım için ideal!"
            elif rsi < 35:
                strateji_notu = "🟢 *Dip / Fırsat Bölgesi:* RSI aşırı satımda, kademeli değerlendirilebilir."
            elif rsi > 70 and "ÜST BANTTA" in bollinger:
                strateji_notu = "🔴 *Aşırı Primli / Tepe:* Direnç noktasında, kâr realizasyonu düşünülmeli."
            elif rsi > 70:
                strateji_notu = "🔴 *Aşırı Alım Bölgesi:* Dikkatli olunmalı, yeni alım riski yüksek."
            else:
                strateji_notu = "⚖️ *Dengeli / Bekle-Gör:* Trend nötr seyrediyor."
            
            durum_metni = (
                f"🎯 *Taktiksel Sinyal: {isim}*\n"
                f"💰 Fiyat: {fiyat:.2f} | RSI: {rsi:.1f}\n"
                f"📊 Hacim: {hacim}\n"
                f"📈 Bollinger: {bollinger}\n"
                f"⚡ MACD: {macd}\n\n"
                f"💡 {strateji_notu}\n\n"
                f"📈 Önerilen TP: {onerilen_tp} | SL: {onerilen_sl}\n"
                f"İşlemi açtıysan aşağıdaki butonla takibe alabilirsin:"
            )
            
            keyboard = {
                "inline_keyboard": [
                    [{"text": "✅ Aldım / Takibe Başla", "callback_data": f"AL|{sembol}|{isim}|{fiyat}|{onerilen_tp}|{onerilen_sl}"}],
                    [{"text": "❌ Takibi Bırak", "callback_data": f"SIL|{sembol}"}]
                ]
            }
            telegram_mesaj_gonder_butonlu(durum_metni, keyboard, hedef_id)

# --- 2. ARKA PLAN NÖBETÇİSİ ---
def arka_plan_ani_kontrol():
    print("👀 Arka plan nöbetçisi (RSI + Hacim + MACD + Bollinger) tarıyor...")
    
    # A. Aktif Pozisyon TP / SL Kontrolü
    aktif_pos = dosya_yukle(POZISYON_DOSYASI, {})
    for sembol, detay in aktif_pos.items():
        fiyat, _, _, _, _ = gelismis_teknik_analiz(detay['sembol'])
        if fiyat and str(fiyat) != "nan":
            tp = detay['tp']
            sl = detay['sl']
            isim = detay['isim']
            
            if fiyat >= tp:
                telegram_mesaj_gonder_butonlu(f"🎉 *TP (KÂR HEDEFİ) ULAŞILDI!*\n\n📌 *{isim}* ({sembol}) hedef fiyat olan *{tp}*'yi gördü!\n💰 Güncel Fiyat: {fiyat:.2f}")
            elif fiyat <= sl:
                telegram_mesaj_gonder_butonlu(f"⚠️ *ACİL STOP / SL TETİKLENDİ!*\n\n📌 *{isim}* ({sembol}) zarar kes seviyesi olan *{sl}*'ye geriledi!\n💰 Güncel Fiyat: {fiyat:.2f}")

    # B. Taktiksel Liste Kritik Alarm Kontrolü
    taktiksel_liste = dosya_yukle(TAKIP_LISTESI_DOSYASI, VARSAYILAN_TAKIP_LISTESI)
    alarm_gecmisi = dosya_yukle(ALARM_DURUM_DOSYASI, {})
    degisiklik_oldu = False

    for isim, sembol in taktiksel_liste.items():
        fiyat, rsi, hacim, macd, bollinger = gelismis_teknik_analiz(sembol)
        if fiyat and rsi and str(fiyat) != "nan":
            mevcut_durum = "NORMAL"
            if rsi < 35 and "ALT BANTTA" in bollinger:
                mevcut_durum = "DIP"
            elif rsi > 70 and "ÜST BANTTA" in bollinger:
                mevcut_durum = "TEPE"

            son_durum = alarm_gecmisi.get(sembol, "NORMAL")
            if mevcut_durum in ["DIP", "TEPE"] and son_durum != mevcut_durum:
                if mevcut_durum == "DIP":
                    alarm_mesaj = f"🚨 *GÜÇLÜ DİP / FIRSAT ALARMI!*\n\n📌 *{isim}* alt banda değdi ve RSI < 35 oldu!\n💰 Fiyat: {fiyat:.2f} | RSI: {rsi:.1f}\n📊 Hacim: {hacim}\n⚡ MACD: {macd}"
                else:
                    alarm_mesaj = f"🚨 *KRİTİK TEPE / KÂR AL ALARMI!*\n\n📌 *{isim}* üst banda dayandı ve RSI > 70 oldu!\n💰 Fiyat: {fiyat:.2f} | RSI: {rsi:.1f}\n⚡ MACD: {macd}"
                
                telegram_mesaj_gonder_butonlu(alarm_mesaj, None, None)
                alarm_gecmisi[sembol] = mevcut_durum
                degisiklik_oldu = True
            elif mevcut_durum == "NORMAL":
                if son_durum != "NORMAL":
                    alarm_gecmisi[sembol] = "NORMAL"
                    degisiklik_oldu = True

    if degisiklik_oldu:
        dosya_kaydet(ALARM_DURUM_DOSYASI, alarm_gecmisi)

# --- ZAMANLAYICILAR ---
scheduler = BackgroundScheduler()
scheduler.add_job(func=lambda: tum_taramalari_calistir(None), trigger="cron", hour=9, minute=30)
scheduler.add_job(func=arka_plan_ani_kontrol, trigger="interval", hours=1)
scheduler.start()

@app.route("/")
def ana_sayfa():
    return "Gelişmiş Algoritmik Portföy Asistanı Aktif!", 200

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    
    if data and "message" in data:
        message = data["message"]
        text = message.get("text", "").strip()
        chat_id = message.get("chat", {}).get("id")
        
        if text in ["/tara", "/test", "/tara@Borsa_bot"]:
            telegram_mesaj_gonder_butonlu("🚀 *Gelişmiş İndikatörlerle (RSI, Hacim, MACD, Bollinger) Tarama Başlatıldı...*", None, chat_id)
            tum_taramalari_calistir(chat_id)
            
        elif text.startswith("/ekle "):
            parcalar = text.split(" ", 2)
            if len(parcalar) >= 2:
                sembol = parcalar[1].upper()
                isim = parcalar[2] if len(parcalar) > 2 else sembol
                taktiksel_liste = dosya_yukle(TAKIP_LISTESI_DOSYASI, VARSAYILAN_TAKIP_LISTESI)
                taktiksel_liste[isim] = sembol
                dosya_kaydet(TAKIP_LISTESI_DOSYASI, taktiksel_liste)
                telegram_mesaj_gonder_butonlu(f"✅ *{isim} ({sembol})* listeye eklendi!", None, chat_id)
            else:
                telegram_mesaj_gonder_butonlu("⚠️ Örnek kullanım: `/ekle TSLA Tesla`", None, chat_id)

        elif text.startswith("/hisselistesi"):
            taktiksel_liste = dosya_yukle(TAKIP_LISTESI_DOSYASI, VARSAYILAN_TAKIP_LISTESI)
            liste_str = "📋 *Takip Listesi:*\n\n"
            for isim, sembol in taktiksel_liste.items():
                liste_str += f"• {isim} (`{sembol}`)\n"
            telegram_mesaj_gonder_butonlu(liste_str, None, chat_id)

    elif data and "callback_query" in data:
        query = data["callback_query"]
        callback_data = query.get("data", "")
        chat_id = query.get("message", {}).get("chat", {}).get("id")
        query_id = query.get("id")
        
        parts = callback_data.split("|")
        islem = parts[0]
        aktif_pos = dosya_yukle(POZISYON_DOSYASI, {})
        
        if islem == "AL":
            sembol = parts[1]
            isim = parts[2]
            maliyet = float(parts[3])
            tp = float(parts[4])
            sl = float(parts[5])
            aktif_pos[sembol] = {"sembol": sembol, "isim": isim, "maliyet": maliyet, "tp": tp, "sl": sl}
            dosya_kaydet(POZISYON_DOSYASI, aktif_pos)
            telegram_mesaj_gonder_butonlu(f"✅ *{isim}* pozisyon takibine alındı (TP: {tp}, SL: {sl}).", None, chat_id)
            
        elif islem == "SIL":
            sembol = parts[1]
            if sembol in aktif_pos:
                del aktif_pos[sembol]
                dosya_kaydet(POZISYON_DOSYASI, aktif_pos)
            telegram_mesaj_gonder_butonlu(f"❌ *{sembol}* takipten çıkarıldı.", None, chat_id)
            
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": query_id})
        except Exception:
            pass

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
