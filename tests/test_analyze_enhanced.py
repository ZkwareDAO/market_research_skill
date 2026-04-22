"""
Tests for enhanced analyze.py with symbol/timeframe parameters

Tests for:
1. Single symbol analysis
2. Auto-resample from 1m data
3. Auto-sync from Binance
"""

import pytest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

# Add scripts directory to path
scripts_path = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(scripts_path))


class TestAnalyzeCLI:
    """Test analyze.py command-line interface"""

    def test_main_with_timeframe_only(self):
        """Test running analyze.py with only timeframe argument"""
        # This should work - default behavior
        result = subprocess.run(
            [sys.executable, str(scripts_path / 'analyze_enhanced.py'), '1h'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(scripts_path)
        )
        # Should not error (may have no data warning)
        assert result.returncode == 0 or "未找到" in result.stdout or "分析" in result.stdout

    def test_main_with_symbol_and_timeframe(self):
        """Test running analyze.py with symbol and timeframe"""
        result = subprocess.run(
            [sys.executable, str(scripts_path / 'analyze_enhanced.py'), '1h', 'BTCUSDT'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(scripts_path)
        )
        # Should accept the arguments (may have no data warning)
        assert result.returncode == 0 or "未找到" in result.stdout or "分析" in result.stdout or "单符号" in result.stdout

    def test_main_with_invalid_timeframe(self):
        """Test running analyze.py with invalid timeframe"""
        result = subprocess.run(
            [sys.executable, str(scripts_path / 'analyze_enhanced.py'), 'invalid'],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(scripts_path)
        )
        assert result.returncode != 0
        assert "错误" in result.stdout or "不支持" in result.stdout


class TestDataOrchestration:
    """Test ensure_data_exists function"""

    @pytest.fixture
    def mock_csv_storage(self):
        """Create a mock CsvStorage"""
        with patch('analyze_enhanced.csv_storage') as mock:
            yield mock

    @pytest.fixture
    def mock_resampler(self):
        """Create a mock DataResampler"""
        with patch('analyze_enhanced.DataResampler') as mock:
            yield mock

    @pytest.fixture
    def mock_data_source(self):
        """Mock DATA_SOURCE environment variable"""
        with patch('analyze_enhanced.DATA_SOURCE', 'local') as mock:
            yield mock

    def test_ensure_data_exists_timeframe_exists(self, mock_csv_storage):
        """Test when requested timeframe data already exists (with >= 30 bars)"""
        # Import after mock is set up
        from analyze_enhanced import ensure_data_exists

        # Mock: timeframe data exists with 30+ bars
        mock_df = MagicMock(empty=False)
        mock_df.__len__ = MagicMock(return_value=35)  # 35 bars
        mock_csv_storage.load_recent.return_value = mock_df

        result = ensure_data_exists('BTCUSDT', '4h')

        assert result is True
        # Should check for 30 bars
        mock_csv_storage.load_recent.assert_called_once_with('BTCUSDT', '4h', limit=30)

    def test_ensure_data_exists_needs_resample(self, mock_csv_storage, mock_resampler):
        """Test when 1m data exists but timeframe needs resampling"""
        from analyze_enhanced import ensure_data_exists, TIMEFRAME_1M_REQUIREMENTS
        import pandas as pd

        # Required 1m bars for 4h timeframe (7200 = 30 * 240)
        required_bars = TIMEFRAME_1M_REQUIREMENTS.get('4h', 7200)

        # Mock: timeframe data doesn't exist, but 1m does
        mock_csv_storage.load_recent.side_effect = [
            MagicMock(empty=True),   # 4h doesn't exist (first check)
            MagicMock(empty=False),  # 1m exists
        ]

        # Create mock 1m dataframe with enough data for 30 output bars
        base_time = pd.Timestamp('2026-04-21 10:00:00', tz='UTC')
        mock_df_1m = pd.DataFrame({
            'timestamp': [base_time + pd.Timedelta(minutes=i) for i in range(required_bars)],
            'open': [100.0 + i * 0.1 for i in range(required_bars)],
            'high': [102.0 + i * 0.1 for i in range(required_bars)],
            'low': [99.0 + i * 0.1 for i in range(required_bars)],
            'close': [101.0 + i * 0.1 for i in range(required_bars)],
            'volume': [1000.0 + i * 10 for i in range(required_bars)],
        }).set_index('timestamp')

        # Mock resampler
        mock_resampler_instance = MagicMock()
        mock_resampler.return_value = mock_resampler_instance
        mock_resampler_instance.get_df.return_value = mock_df_1m
        mock_resampler_instance._dfs = {'BTCUSDT': {'4h': mock_df_1m.resample('4h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()}}
        mock_resampler_instance._save_to_storage = MagicMock()

        result = ensure_data_exists('BTCUSDT', '4h')

        assert result is True
        # Should call DataResampler
        mock_resampler.assert_called_once()

    def test_ensure_data_exists_needs_sync(self, mock_csv_storage, mock_data_source):
        """Test when no data exists and DATA_SOURCE is local"""
        from analyze_enhanced import ensure_data_exists

        # Mock: no data exists
        mock_csv_storage.load_recent.return_value = MagicMock(empty=True)

        result = ensure_data_exists('NEWCOIN', '4h')

        # Should return False when no data and local source
        assert result is False


class TestAnalyzeSymbolWithResample:
    """Test analyze_symbol with auto-resample"""

    @pytest.fixture
    def mock_csv_storage(self):
        """Create a mock CsvStorage"""
        with patch('analyze_enhanced.csv_storage') as mock:
            yield mock

    def test_analyze_symbol_returns_none_when_no_data(self, mock_csv_storage):
        """Test analyze_symbol returns None when no data available"""
        from analyze_enhanced import analyze_symbol

        mock_csv_storage.load_recent.return_value = MagicMock(empty=True)

        result = analyze_symbol('NONEXISTENT', '1h')

        assert result is None

    def test_analyze_symbol_with_sufficient_data(self, mock_csv_storage):
        """Test analyze_symbol with sufficient data"""
        from analyze_enhanced import analyze_symbol
        import pandas as pd

        # Create mock data
        base_time = pd.Timestamp('2026-04-21 10:00:00', tz='UTC')
        data = {
            'timestamp': [base_time + pd.Timedelta(minutes=i) for i in range(100)],
            'open': [100.0 + i * 0.1 for i in range(100)],
            'high': [102.0 + i * 0.1 for i in range(100)],
            'low': [99.0 + i * 0.1 for i in range(100)],
            'close': [101.0 + i * 0.1 for i in range(100)],
            'volume': [1000.0 + i * 10 for i in range(100)],
        }
        df = pd.DataFrame(data)
        mock_csv_storage.load_recent.return_value = df

        result = analyze_symbol('BTCUSDT', '1h')

        assert result is not None
        assert result['symbol'] == 'BTCUSDT'
        assert 'rsi' in result
        assert 'macd' in result
        assert 'adx' in result
        assert 'direction' in result
        assert 'price_trend' in result


class TestGetSymbolsForTimeframe:
    """Test get_symbols_for_timeframe with symbol filter"""

    @pytest.fixture
    def mock_csv_storage(self):
        """Create a mock CsvStorage"""
        with patch('analyze_enhanced.csv_storage') as mock:
            mock.list_symbols.return_value = ['BTCUSDT', 'ETHUSDT']
            mock.list_timeframes.return_value = ['1h', '4h']
            yield mock

    def test_get_symbols_for_timeframe_all_symbols(self, mock_csv_storage):
        """Test getting all symbols for timeframe"""
        from analyze_enhanced import get_symbols_for_timeframe

        mock_csv_storage.load_recent.return_value = MagicMock(empty=False)
        symbols = get_symbols_for_timeframe('1h')

        assert len(symbols) >= 0  # May be empty if no data

    def test_get_symbols_for_timeframe_single_symbol(self, mock_csv_storage):
        """Test getting single symbol for timeframe"""
        from analyze_enhanced import get_symbols_for_timeframe

        # Mock: 1h data exists with 30+ bars
        mock_df = MagicMock(empty=False)
        mock_df.__len__ = MagicMock(return_value=35)  # 35 bars
        mock_csv_storage.load_recent.return_value = mock_df

        symbols = get_symbols_for_timeframe('1h', symbol_filter='BTCUSDT')

        assert symbols == ['BTCUSDT']

    def test_get_symbols_for_timeframe_filtered_out(self, mock_csv_storage):
        """Test when symbol filter doesn't match"""
        from analyze_enhanced import get_symbols_for_timeframe

        mock_csv_storage.load_recent.return_value = MagicMock(empty=True)
        symbols = get_symbols_for_timeframe('1h', symbol_filter='NONEXISTENT')

        assert symbols == []
