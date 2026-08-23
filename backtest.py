# backtest.py
import pandas as pd
import yfinance as yf

def run_historical_backtest(symbol="AAPL"):
    """
    Hacim filtresi ve %5 TP / %3 SL kurallarıyla geçmiş veriler üzerinde backtest yapar.
    """
    try:
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)
        if len(df) < 30:
            return f"⚠️ {symbol} için yeterli veri yok."
        
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['Avg_Vol'] = df['Volume'].rolling(window=10).mean()
        
        total_trades = 0
        successful_trades = 0
        
        for i in range(20, len(df) - 5):
            current_vol = df['Volume'].iloc[i]
            avg_vol = df['Avg_Vol'].iloc[i-1]
            close = df['Close'].iloc[i]
            sma = df['SMA20'].iloc[i]
            
            # Hacim Filtresi ve Trend Şartı
            if current_vol >= (avg_vol * 1.2) and close > sma:
                total_trades += 1
                entry_price = df['Close'].iloc[i]
                target_price = entry_price * 1.05  # %5 Hedef (TP1)
                stop_price = entry_price * 0.97    # %3 Stop Loss
                
                # 5 günlük süre içinde hedef mi geldi, stop mu oldu?
                for j in range(1, 6):
                    if i + j < len(df):
                        high = df['High'].iloc[i+j]
                        low = df['Low'].iloc[i+j]
                        if high >= target_price:
                            successful_trades += 1
                            break
                        elif low <= stop_price:
                            break
                            
        win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
        
        report = (
            f"📊 *Backtest Sonucu ({symbol})*\n\n"
            f"• *Toplam Sinyal:* {total_trades}\n"
            f"• *Başarılı İşlem (TP):* {successful_trades}\n"
            f"• *Yeni Kazanma Oranı (Win Rate):* %{win_rate:.2f}\n"
        )
        return report
    except Exception as e:
        return f"Backtest hatası: {e}"
