def run_backtest():
    logging.info("Backtest simülasyonu başlatıldı (Piyasa Rejimi Filtreli + Stop %3 + Komisyon)...")
    total_trades = 0
    winning_trades = 0
    processed_count = 0
    commission_rate = 0.001  # %0.1 alım/satım komisyon oranı
    
    # 1. Adım: Piyasa Rejimi Tespiti için referans varlık (Örn: S&P 500 - SPY veya yaygın bir endeks)
    # Watchlist içinden genel piyasa eğilimini ölçmek için ana bir varlık seçelim (yoksa ilk varlığı baz alır)
    market_ref_symbol = "SPY" if "SPY" in WATCHLIST else WATCHLIST[0]
    market_df = fetch_chart_data(market_ref_symbol)
    market_sma200 = market_df['Close'].rolling(200).mean() if not market_df.empty else pd.Series()

    for symbol in WATCHLIST:
        try:
            df = fetch_chart_data(symbol)
            if df.empty or len(df) < 210:
                continue

            processed_count += 1
            sma200 = df['Close'].rolling(200).mean()
            rsi = calculate_rsi(df['Close'])

            start_idx = max(200, len(df) - 120)
            end_idx = len(df) - 10

            for i in range(start_idx, end_idx):
                # Piyasa Rejimi Kontrolü (Ayı Piyasası Filtresi)
                # Referans piyasa fiyatı 200 SMA'nın altındaysa yeni alım sinyallerini atla
                if not market_sma200.empty and i < len(market_sma200):
                    market_close = float(market_df['Close'].iloc[i])
                    market_sma = float(market_sma200.iloc[i])
                    if market_close < market_sma:
                        continue  # Ayı piyasasında alım yapma!

                close = float(df['Close'].iloc[i])
                sma = float(sma200.iloc[i])
                sma_past = float(sma200.iloc[i-15])
                r = float(rsi.iloc[i])

                if close > sma and sma > sma_past and r < 70:
                    total_trades += 1
                    
                    entry_price = close * (1 + commission_rate)
                    target = entry_price * 1.05 * (1 + commission_rate)
                    stop = sma * 0.97

                    future_prices = df['Close'].iloc[i+1:i+11].values
                    hit_target = any(future_prices >= target)
                    hit_stop = any(future_prices <= stop)

                    if hit_target and not hit_stop:
                        winning_trades += 1

        except Exception as b_err:
            logging.error(f"Backtest hatası {symbol}: {b_err}")

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    msg = (
        f"📈 PİYASA REJİMLİ NET BAŞARIM TESTİ\n\n"
        f"Referans Endeks Filtresi: Aktif ({market_ref_symbol})\n"
        f"Başarıyla İşlenen Sembol: {processed_count}/{len(WATCHLIST)}\n"
        f"Toplam Üretilen Sinyal: {total_trades}\n"
        f"Net Başarılı İşlem: {winning_trades}\n"
        f"Kazanma Oranı (Win Rate): %{win_rate:.1f}\n\n"
        f"Komisyon: %{commission_rate*100:.2f} | Stop: %3"
    )
    send_telegram_message(msg)
