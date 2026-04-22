"""
Tests for IndicatorCalculator module

Tests for technical indicator calculations (ADX, MACD, RSI).
"""

import pytest
import pandas as pd
import numpy as np

from indicator_calculator import IndicatorCalculator


@pytest.fixture
def sample_ohlc_data():
    """Generate sample OHLC data for testing"""
    np.random.seed(42)
    n = 100

    # Generate realistic price data
    close = 100 + np.cumsum(np.random.randn(n))
    high = close + np.abs(np.random.randn(n)) * 0.5
    low = close - np.abs(np.random.randn(n)) * 0.5
    open_price = np.roll(close, 1)
    open_price[0] = 100

    data = {
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000, 10000, n),
    }
    return pd.DataFrame(data)


@pytest.fixture
def calculator():
    """Create an IndicatorCalculator instance"""
    return IndicatorCalculator(
        adx_period=14,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        rsi_period=14,
    )


class TestIndicatorCalculatorInit:
    """Test IndicatorCalculator initialization"""

    def test_init_with_default_params(self):
        """Test initialization with default parameters"""
        calc = IndicatorCalculator()
        assert calc.adx_period == 14
        assert calc.macd_fast == 12
        assert calc.macd_slow == 26
        assert calc.macd_signal == 9
        assert calc.rsi_period == 14

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters"""
        calc = IndicatorCalculator(
            adx_period=20,
            macd_fast=8,
            macd_slow=20,
            macd_signal=5,
            rsi_period=10,
        )
        assert calc.adx_period == 20
        assert calc.macd_fast == 8
        assert calc.rsi_period == 10


class TestIndicatorCalculatorCalculate:
    """Test IndicatorCalculator.calculate method"""

    def test_calculate_adds_all_columns(self, sample_ohlc_data, calculator):
        """Test that calculate adds all indicator columns"""
        result = calculator.calculate(sample_ohlc_data)

        expected_columns = [
            'adx', 'plus_di', 'minus_di',
            'macd', 'macd_signal', 'macd_hist',
            'rsi'
        ]

        for col in expected_columns:
            assert col in result.columns

    def test_calculate_preserves_original_columns(self, sample_ohlc_data, calculator):
        """Test that calculate preserves original OHLCV columns"""
        result = calculator.calculate(sample_ohlc_data)

        for col in ['open', 'high', 'low', 'close', 'volume']:
            assert col in result.columns

    def test_calculate_empty_dataframe(self, calculator):
        """Test calculate with empty DataFrame"""
        empty_df = pd.DataFrame()
        result = calculator.calculate(empty_df)

        assert result.empty

    def test_calculate_insufficient_data(self, calculator):
        """Test calculate with insufficient data"""
        # Create small DataFrame
        data = {
            'open': [100, 101, 102],
            'high': [103, 104, 105],
            'low': [99, 100, 101],
            'close': [101, 102, 103],
            'volume': [1000, 1100, 1200],
        }
        small_df = pd.DataFrame(data)

        result = calculator.calculate(small_df)

        # Should return DataFrame with NaN values for indicators
        assert len(result) == 3
        assert result['rsi'].isna().all()

    def test_calculate_rsi_values_in_range(self, sample_ohlc_data, calculator):
        """Test that RSI values are in valid range (0-100)"""
        result = calculator.calculate(sample_ohlc_data)

        rsi_values = result['rsi'].dropna()
        assert (rsi_values >= 0).all()
        assert (rsi_values <= 100).all()

    def test_calculate_adx_positive(self, sample_ohlc_data, calculator):
        """Test that ADX values are positive"""
        result = calculator.calculate(sample_ohlc_data)

        adx_values = result['adx'].dropna()
        assert (adx_values >= 0).all()


class TestIndicatorCalculatorGetLatestValues:
    """Test IndicatorCalculator.get_latest_values method"""

    def test_get_latest_values_returns_dict(self, sample_ohlc_data, calculator):
        """Test that get_latest_values returns a dictionary"""
        result = calculator.calculate(sample_ohlc_data)
        latest = calculator.get_latest_values(result)

        assert isinstance(latest, dict)
        expected_keys = [
            'adx', 'plus_di', 'minus_di',
            'macd', 'macd_signal', 'macd_hist',
            'rsi'
        ]
        for key in expected_keys:
            assert key in latest

    def test_get_latest_values_all_present(self, sample_ohlc_data, calculator):
        """Test that all indicator values are present"""
        result = calculator.calculate(sample_ohlc_data)
        latest = calculator.get_latest_values(result)

        # With sufficient data, values should not be None
        assert latest['rsi'] is not None
        assert latest['adx'] is not None
        assert latest['macd'] is not None

    def test_get_latest_values_empty_dataframe(self, calculator):
        """Test get_latest_values with empty DataFrame"""
        empty_df = pd.DataFrame()
        latest = calculator.get_latest_values(empty_df)

        assert all(v is None for v in latest.values())

    def test_get_latest_rsi_convenience_method(self, sample_ohlc_data, calculator):
        """Test get_latest_rsi convenience method"""
        result = calculator.calculate(sample_ohlc_data)
        rsi = calculator.get_latest_rsi(result)

        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_get_latest_adx_convenience_method(self, sample_ohlc_data, calculator):
        """Test get_latest_adx convenience method"""
        result = calculator.calculate(sample_ohlc_data)
        adx = calculator.get_latest_adx(result)

        assert adx is not None
        assert adx >= 0

    def test_get_latest_macd_returns_dict(self, sample_ohlc_data, calculator):
        """Test get_latest_macd returns dict with macd, signal, hist"""
        result = calculator.calculate(sample_ohlc_data)
        macd_data = calculator.get_latest_macd(result)

        assert 'macd' in macd_data
        assert 'signal' in macd_data
        assert 'hist' in macd_data


class TestIndicatorCalculatorEdgeCases:
    """Test edge cases for IndicatorCalculator"""

    def test_flat_price_data(self, calculator):
        """Test with flat price data (no movement)"""
        n = 50
        data = {
            'open': [100.0] * n,
            'high': [101.0] * n,
            'low': [99.0] * n,
            'close': [100.0] * n,
            'volume': [1000.0] * n,
        }
        df = pd.DataFrame(data)

        result = calculator.calculate(df)

        # RSI for flat data: when there's no loss, RSI = 100
        # This is mathematically correct (RS = infinity, RSI = 100)
        rsi_values = result['rsi'].dropna()
        if not rsi_values.empty:
            # RSI should be either 100 (no losses) or around 50 (balanced)
            assert rsi_values.iloc[-1] >= 50 or rsi_values.iloc[-1] == 100

    def test_strong_uptrend(self, calculator):
        """Test with strong uptrend data"""
        n = 50
        data = {
            'open': list(range(100, 100 + n)),
            'high': list(range(102, 102 + n)),
            'low': list(range(98, 98 + n)),
            'close': list(range(101, 101 + n)),
            'volume': [1000.0] * n,
        }
        df = pd.DataFrame(data)

        result = calculator.calculate(df)

        # RSI should be high for strong uptrend
        rsi_values = result['rsi'].dropna()
        if not rsi_values.empty:
            assert rsi_values.iloc[-1] > 50

    def test_strong_downtrend(self, calculator):
        """Test with strong downtrend data"""
        n = 50
        data = {
            'open': list(range(100 + n, 100, -1)),
            'high': list(range(102 + n, 102, -1)),
            'low': list(range(98 + n, 98, -1)),
            'close': list(range(101 + n, 101, -1)),
            'volume': [1000.0] * n,
        }
        df = pd.DataFrame(data)

        result = calculator.calculate(df)

        # RSI should be low for strong downtrend
        rsi_values = result['rsi'].dropna()
        if not rsi_values.empty:
            assert rsi_values.iloc[-1] < 50
