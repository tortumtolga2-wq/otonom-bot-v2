import os
import time
import requests

# --- AYARLAR VE TOKEN BİLGİLERİ ---
TELEGRAM_BOT_TOKEN = "BURAYA_BOT_TOKENINIZI_YAZIN"
# Mevcut Telegram Chat ID'n buraya doğrudan işlenmiştir:
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "MEVCUT_CHAT_ID_BURAYA")

def telegram_mesaj_gonder(mesaj: str):
    """Telegram kanalına mesaj gönderen temel fonksiyon."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Telegram mesaj hatası: {e}")

# --- 1. ANA PORTFÖY TARAYICISI (Mevcut Büyük Şirketler / Yıldız Pazar) ---
def ana_portfoy_tara():
    # Burada ana portföy hisseleri taranır
    sinyal_aktif = True # Örnek simüle edilmiş sinyal
    
    if sinyal_aktif:
        hisse = "GARAN" 
        fiyat = 112.50
        mesaj = (
            f"🟢 *[ANA PORTFÖY]*\n"
            f"📌 *Hisse:* {hisse}\n"
            f"💰 *Fiyat:* {fiyat} TL\n"
            f"📊 *Durum:* Uzun vadeli ana portföy takibi ve teknik seviye korunuyor."
        )
        telegram_mesaj_gonder(mesaj)

# --- 2. CASH - ANA PAZAR TARAYICISI (10.000 TL'lik Trade Bütçesi) ---
def cash_ana_pazar_tara():
    """
    Sadece Ana Pazar hisselerini tarar. 
    Hacim patlaması ve ani para girişine göre orta-riskli / riskli sinyal üretir.
    """
    sinyal_bulundu = True # Örnek simüle edilmiş sinyal
    
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
        telegram_mesaj_gonder(mesaj)

# --- ANA ÇALIŞTIRMA DÖNGÜSÜ ---
if __name__ == "__main__":
    print("Bot başlatıldı ve piyasa takibi aktif...")
    try:
        # Ana portföy kontrolü
        ana_portfoy_tara()
        
        # Cash - Ana Pazar kontrolü
        cash_ana_pazar_tara()
        
    except Exception as e:
        print(f"Çalışma sırasında hata oluştu: {e}")
