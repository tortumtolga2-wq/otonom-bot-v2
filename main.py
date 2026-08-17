def run_backtest():
    logging.info("Backtest simülasyonu başlatıldı (Stop %3 + Komisyon Kesintili)...")
    total_trades = 0
    winning_trades = 0
    processed_count = 0
    commission_rate = 0.001  # %0.1 alım/satım komisyon oranı
    
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
                close = float(df['Close'].iloc[i])
                sma = float(sma200.iloc[i])
                sma_past = float(sma200.iloc[i-15])
                r = float(rsi.iloc[i])

                if close > sma and sma > sma_past and r < 70:
                    total_trades += 1
                    
                    # Komisyon maliyeti dahil edilmiş net hedef ve stop seviyeleri
                    # Alışta komisyon ödenir, hedefe ulaşırken çift yönlü komisyon maliyeti düşülür
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
        f"📈 NET BAŞARIM TESTİ (KOMİSYONLU & STOP %3)\n\n"
        f"Başarıyla İşlenen Sembol: {processed_count}/{len(WATCHLIST)}\n"
        f"Toplam Üretilen Sinyal: {total_trades}\n"
        f"Net Başarılı İşlem: {winning_trades}\n"
        f"Kazanma Oranı (Win Rate): %{win_rate:.1f}\n\n"
        f"Komisyon Oranı: %{commission_rate*100:.2f} (Alış/Satış)"
    )
    send_telegram_message(msg)
