import unittest
import pandas as pd
import numpy as np

# main.py içerisindeki test edilecek fonksiyonları import ediyoruz
from main import calculate_rsi, calculate_atr

class TestTradingBotLogic(unittest.TestCase):
    
    def setUp(self):
        # Test için örnek bir fiyat dataframe'i oluşturuyoruz
        dates = pd.date_range(start='2025-01-01', periods=50, freq='D')
        np.random.seed(42)
        close_prices = 100 + np.cumsum(np.random.randn(50) * 2)
        high_prices = close_prices + np.random.rand(50) * 2
        low_prices = close_prices - np.random.rand(50) * 2
        
        self.test_df = pd.DataFrame({
            'Date': dates,
            'Open': close_prices,
            'High': high_prices,
            'Low': low_prices,
            'Close': close_prices
        })

    def test_calculate_rsi(self):
        """RSI değerlerinin 0 ile 100 arasında olup olmadığını ve hesaplandığını test eder"""
        series = self.test_df['Close']
        rsi = calculate_rsi(series, period=14)
        
        # İlk 14 gün NaN olmalıdır, sonrakiler sayısal olmalıdır
        self.assertEqual(len(rsi), len(series))
        valid_rsi = rsi.dropna()
        
        self.assertTrue(all(valid_rsi >= 0))
        self.assertTrue(all(valid_rsi <= 100))

    def test_calculate_atr(self):
        """ATR (Average True Range) değerlerinin pozitif ve doğru boyutta olduğunu test eder"""
        atr = calculate_atr(self.test_df, period=14)
        
        self.assertEqual(len(atr), len(self.test_df))
        valid_atr = atr.dropna()
        
        # ATR her zaman pozitif olmalıdır
        self.assertTrue(all(valid_atr > 0))

if __name__ == '__main__':
    unittest.main()