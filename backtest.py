# backtest.py
import pandas as pd
import yfinance as yf

def run_historical_backtest(symbol="NVDA"):
    """
    Hacim filtresi ve TP / SL ile geçmiş veriler üzerinde backtest yapar.
    """
    try:
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)
        if df is None or len(df) < 50:
            return f"📊 *Backtest Raporu ({symbol})*\n• Yetersiz veri."

        # Pandas DataFrame çoklu kolon yapısını düzeltme koruması
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df['Vol_Std'] = df['Volume'].rolling(window=10).std()
        df['Vol_Mean'] = df['Volume'].rolling(window=10).mean()
        
        total_trades = 0
        successful_trades = 0

        for i in range(20, len(df)):
            vol_mean_val = float(df['Vol_Mean'].iloc[i])
            vol_std_val = float(df['Vol_Std'].iloc[i])
            current_vol = float(df['Volume'].iloc[i])
            
            if pd.isna(vol_mean_val) or pd.isna(vol_std_val):
                continue

            dynamic_threshold = vol_mean_val + (0.5 * vol_std_val)
            
            if current_vol < dynamic_threshold:
                continue 

            close_val = float(df['Close'].iloc[i])
            sma_val = float(df['Close'].rolling(window=20).mean().iloc[i])

            if close_val > sma_val:
                total_trades += 1
                entry_price = close_val
                tp_price = entry_price * 1.05
                sl_price = entry_price * 0.97
                
                # Gelecek günlerde hedef veya stop oldu mu kontrol et
                trade_success = False
                for j in range(i + 1, min(i + 10, len(df))):
                    high_val = float(df['High'].iloc[j])
                    low_val = float(df['Low'].iloc[j])
                    
                    if high_val >= tp_price:
                        successful_trades += 1
                        trade_success = True
                        break
                    elif low_val <= sl_price:
                        break

        win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0.0

        report = (
            f"📊 *Backtest Sonucu ({symbol})*\n"
            f"• *Toplam Sinyal:* `{total_trades}`\n"
            f"• *Başarılı İşlem (TP):* `{successful_trades}`\n"
            f"• *Test Başarı Oranı:* `% {win_rate:.1f}`"
        )
        return report

    except Exception as e:
        return f"⚠️ *Backtest Hatası:* `{str(e)}`"
