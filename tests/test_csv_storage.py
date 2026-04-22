"""
Tests for CsvStorage module

Tests for CSV storage management with daily file rotation.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import shutil
import tempfile

from csv_storage import CsvStorage


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory for testing"""
    temp_dir = tempfile.mkdtemp()
    storage = CsvStorage(temp_dir, load_limit=100)
    yield storage, temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_kline_data():
    """Generate sample K-line data for testing"""
    base_time = pd.Timestamp('2026-04-21 10:00:00', tz='UTC')
    data = {
        'timestamp': [base_time + pd.Timedelta(minutes=i) for i in range(10)],
        'open': [100.0 + i for i in range(10)],
        'high': [102.0 + i for i in range(10)],
        'low': [99.0 + i for i in range(10)],
        'close': [101.0 + i for i in range(10)],
        'volume': [1000.0 + i * 100 for i in range(10)],
    }
    return pd.DataFrame(data)


class TestCsvStorageInit:
    """Test CsvStorage initialization"""

    def test_init_creates_directory(self, temp_storage):
        """Test that initialization creates the data directory"""
        storage, temp_dir = temp_storage
        assert Path(temp_dir).exists()
        assert Path(temp_dir).is_dir()

    def test_init_with_custom_load_limit(self):
        """Test initialization with custom load limit"""
        temp_dir = tempfile.mkdtemp()
        try:
            storage = CsvStorage(temp_dir, load_limit=50)
            assert storage.load_limit == 50
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestCsvStorageAppend:
    """Test CsvStorage append functionality"""

    def test_append_creates_daily_file(self, temp_storage, sample_kline_data):
        """Test that append creates a daily file"""
        storage, temp_dir = temp_storage

        result = storage.append('BTCUSDT', '1h', sample_kline_data)

        assert result is True
        # Check file was created
        file_path = Path(temp_dir) / 'BTCUSDT' / '1h' / 'BTCUSDT-1h-2026-04-21.csv'
        assert file_path.exists()

    def test_append_empty_dataframe(self, temp_storage):
        """Test appending empty DataFrame"""
        storage, temp_dir = temp_storage
        empty_df = pd.DataFrame()

        result = storage.append('BTCUSDT', '1h', empty_df)

        assert result is True  # Should handle gracefully

    def test_append_avoids_duplicates(self, temp_storage, sample_kline_data):
        """Test that append avoids duplicate timestamps"""
        storage, temp_dir = temp_storage

        # Append same data twice
        storage.append('BTCUSDT', '1h', sample_kline_data)
        storage.append('BTCUSDT', '1h', sample_kline_data)

        # Load and check no duplicates
        result = storage.load_all('BTCUSDT', '1h')
        assert len(result) == len(sample_kline_data)


class TestCsvStorageLoad:
    """Test CsvStorage load functionality"""

    def test_load_recent_returns_data(self, temp_storage, sample_kline_data):
        """Test loading recent data"""
        storage, temp_dir = temp_storage
        storage.append('BTCUSDT', '1h', sample_kline_data)

        result = storage.load_recent('BTCUSDT', '1h')

        assert not result.empty
        assert len(result) == 10
        assert 'open' in result.columns

    def test_load_recent_with_limit(self, temp_storage, sample_kline_data):
        """Test loading recent data with limit"""
        storage, temp_dir = temp_storage
        storage.append('BTCUSDT', '1h', sample_kline_data)

        result = storage.load_recent('BTCUSDT', '1h', limit=5)

        assert len(result) == 5

    def test_load_recent_no_data_returns_empty(self, temp_storage):
        """Test loading when no data exists"""
        storage, temp_dir = temp_storage

        result = storage.load_recent('BTCUSDT', '1h')

        assert result.empty

    def test_load_all_returns_all_data(self, temp_storage, sample_kline_data):
        """Test loading all data"""
        storage, temp_dir = temp_storage
        storage.append('BTCUSDT', '1h', sample_kline_data)

        result = storage.load_all('BTCUSDT', '1h')

        assert len(result) == 10


class TestCsvStorageListMethods:
    """Test CsvStorage list methods"""

    def test_list_symbols_empty(self, temp_storage):
        """Test listing symbols when empty"""
        storage, temp_dir = temp_storage

        symbols = storage.list_symbols()

        assert symbols == []

    def test_list_symbols_with_data(self, temp_storage, sample_kline_data):
        """Test listing symbols with data"""
        storage, temp_dir = temp_storage
        storage.append('BTCUSDT', '1h', sample_kline_data)
        storage.append('ETHUSDT', '1h', sample_kline_data)

        symbols = storage.list_symbols()

        assert 'BTCUSDT' in symbols
        assert 'ETHUSDT' in symbols
        assert len(symbols) == 2

    def test_list_timeframes(self, temp_storage, sample_kline_data):
        """Test listing timeframes for a symbol"""
        storage, temp_dir = temp_storage
        storage.append('BTCUSDT', '1h', sample_kline_data)
        storage.append('BTCUSDT', '4h', sample_kline_data)

        timeframes = storage.list_timeframes('BTCUSDT')

        assert '1h' in timeframes
        assert '4h' in timeframes

    def test_list_dates(self, temp_storage, sample_kline_data):
        """Test listing dates for a symbol/timeframe"""
        storage, temp_dir = temp_storage
        storage.append('BTCUSDT', '1h', sample_kline_data)

        dates = storage.list_dates('BTCUSDT', '1h')

        assert '2026-04-21' in dates


class TestCsvStorageSaveFull:
    """Test CsvStorage save_full functionality"""

    def test_save_full_creates_file(self, temp_storage, sample_kline_data):
        """Test full save creates file"""
        storage, temp_dir = temp_storage

        result = storage.save_full('BTCUSDT', '1h', sample_kline_data)

        assert result is True
        file_path = Path(temp_dir) / 'BTCUSDT' / '1h' / 'BTCUSDT-1h-2026-04-21.csv'
        assert file_path.exists()

    def test_save_full_empty_dataframe(self, temp_storage):
        """Test saving empty DataFrame"""
        storage, temp_dir = temp_storage
        empty_df = pd.DataFrame()

        result = storage.save_full('BTCUSDT', '1h', empty_df)

        assert result is True  # Should handle gracefully
