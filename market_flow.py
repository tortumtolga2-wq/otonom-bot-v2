# market_flow.py
import yfinance as yf
import pandas as pd

def analyze_market_flow():
    """
    Küresel ETF'ler ve BIST üzerinden hacim ve trend analizi yaparak para akış yönünü tespit eder.
    """
    tickers = {
        "ABD Teknoloji (QQQ)": "QQQ",
        "ABD Geniş Piyasa (SPY)": "SPY",
        "Gelişen Piyasalar (EEM)": "EEM",
        "BIST 100 (XU100)": "XU100.IST"
    }
    
    report = "🌐 *Küresel Para Akışı & Sektör Raporu*\n\n"
    
    for name, symbol in tickers.items():
        try:
            data = yf.download(symbol, period="5d", interval="1d", progress=False)
            if len(data) >= 2:
                # Son günün hacmi ile önceki günün hacmini kıyasla
                recent_volume = data['Volume'].iloc[-1]
                avg_volume = data['Volume'].iloc[-5:-1].mean()
                volume_change = ((recent_volume - avg_volume) / avg_volume) * 100
                
                # Fiyat değişimi
                price_change = ((data['Close'].iloc[-1] - data['Close'].iloc[-2]) / data['Close'].iloc[-2]) * 100
                
                trend_icon = "🟢" if price_change > 0 else "🔴"
                report += f"{trend_icon} *{name}*\n"
                report += f"   • Fiyat Değişimi: %{price_change:.2f}\n"
                report += f"   • Hacim Değişimi: %{volume_change:.2f}\n\n"
        except Exception as e:
            report += f"⚠️ *{name}* verisi alınamadı.\n\n"
            
    return report
