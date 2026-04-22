"""
Tests for MarketJudgment module

Tests for market state judgment (trend_market/ranging_market).
"""

import pytest

from market_judgment import MarketJudgment, MarketState


@pytest.fixture
def judgment():
    """Create a MarketJudgment instance with default settings"""
    return MarketJudgment(
        primary_timeframes=['1d', '4h', '15m'],
        adx_trend_threshold=25.0,
        rsi_bullish_threshold=50.0,
        rsi_bearish_threshold=50.0,
    )


class TestMarketState:
    """Test MarketState dataclass"""

    def test_default_values(self):
        """Test MarketState default values"""
        state = MarketState()

        assert state.market_type == 'ranging_market'
        assert state.direction == 'ranging'
        assert state.confidence == 0.0
        assert state.primary_timeframes == []
        assert state.aligned_timeframes == []
        assert state.details == {}

    def test_to_dict(self):
        """Test MarketState.to_dict method"""
        state = MarketState(
            market_type='trend_market',
            direction='bullish',
            confidence=0.9,
            primary_timeframes=['1d', '4h'],
            aligned_timeframes=['1d', '4h'],
            details={'1d': {'adx': 30.0}},
        )

        result = state.to_dict()

        assert result['market_type'] == 'trend_market'
        assert result['direction'] == 'bullish'
        assert result['confidence'] == 0.9
        assert result['details']['1d']['adx'] == 30.0


class TestMarketJudgmentInit:
    """Test MarketJudgment initialization"""

    def test_init_with_default_params(self):
        """Test initialization with default parameters"""
        judgment = MarketJudgment()

        assert judgment.primary_timeframes == ['1d', '4h', '15m']
        assert judgment.adx_trend_threshold == 25.0
        assert judgment.rsi_bullish_threshold == 50.0

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters"""
        judgment = MarketJudgment(
            primary_timeframes=['1h', '15m'],
            adx_trend_threshold=30.0,
        )

        assert judgment.primary_timeframes == ['1h', '15m']
        assert judgment.adx_trend_threshold == 30.0


class TestMarketJudgmentTrendMarket:
    """Test MarketJudgment for trend market detection"""

    def test_bullish_trend_market(self, judgment):
        """Test detection of bullish trend market"""
        # All timeframes bullish with strong ADX
        indicators = {
            '1d': {'adx': 35.0, 'plus_di': 30.0, 'minus_di': 15.0, 'rsi': 60.0},
            '4h': {'adx': 30.0, 'plus_di': 28.0, 'minus_di': 18.0, 'rsi': 58.0},
            '15m': {'adx': 28.0, 'plus_di': 25.0, 'minus_di': 20.0, 'rsi': 55.0},
        }

        state = judgment.judge(indicators)

        assert state.market_type == 'trend_market'
        assert state.direction == 'bullish'
        assert state.confidence == 1.0

    def test_bearish_trend_market(self, judgment):
        """Test detection of bearish trend market"""
        # All timeframes bearish with strong ADX
        indicators = {
            '1d': {'adx': 35.0, 'plus_di': 15.0, 'minus_di': 30.0, 'rsi': 40.0},
            '4h': {'adx': 30.0, 'plus_di': 18.0, 'minus_di': 28.0, 'rsi': 42.0},
            '15m': {'adx': 28.0, 'plus_di': 20.0, 'minus_di': 25.0, 'rsi': 45.0},
        }

        state = judgment.judge(indicators)

        assert state.market_type == 'trend_market'
        assert state.direction == 'bearish'
        assert state.confidence == 1.0


class TestMarketJudgmentRangingMarket:
    """Test MarketJudgment for ranging market detection"""

    def test_ranging_market_mixed_directions(self, judgment):
        """Test detection of ranging market with mixed directions"""
        # Mixed directions
        indicators = {
            '1d': {'adx': 35.0, 'plus_di': 30.0, 'minus_di': 15.0, 'rsi': 60.0},  # Bullish
            '4h': {'adx': 30.0, 'plus_di': 15.0, 'minus_di': 25.0, 'rsi': 40.0},  # Bearish
            '15m': {'adx': 28.0, 'plus_di': 25.0, 'minus_di': 20.0, 'rsi': 55.0},  # Bullish
        }

        state = judgment.judge(indicators)

        assert state.market_type == 'ranging_market'
        assert state.direction == 'bullish'  # More bullish than bearish

    def test_ranging_market_weak_trend(self, judgment):
        """Test detection of ranging market with weak trends"""
        # All timeframes have weak ADX (below threshold)
        indicators = {
            '1d': {'adx': 15.0, 'plus_di': 25.0, 'minus_di': 20.0, 'rsi': 52.0},
            '4h': {'adx': 18.0, 'plus_di': 22.0, 'minus_di': 20.0, 'rsi': 51.0},
            '15m': {'adx': 20.0, 'plus_di': 23.0, 'minus_di': 21.0, 'rsi': 50.0},
        }

        state = judgment.judge(indicators)

        assert state.market_type == 'ranging_market'
        assert state.direction == 'ranging'  # No clear direction

    def test_ranging_market_equal_directions(self, judgment):
        """Test ranging market with equal bullish/bearish count"""
        # Can't have exactly equal with 3 timeframes, but test with 2
        judgment_2tf = MarketJudgment(
            primary_timeframes=['1d', '4h'],
            adx_trend_threshold=25.0,
        )

        indicators = {
            '1d': {'adx': 35.0, 'plus_di': 30.0, 'minus_di': 15.0, 'rsi': 60.0},  # Bullish
            '4h': {'adx': 35.0, 'plus_di': 15.0, 'minus_di': 30.0, 'rsi': 40.0},  # Bearish
        }

        state = judgment_2tf.judge(indicators)

        assert state.market_type == 'ranging_market'


class TestMarketJudgmentConfidence:
    """Test MarketJudgment confidence calculation"""

    def test_full_confidence_all_aligned(self, judgment):
        """Test confidence = 1.0 when all timeframes aligned"""
        indicators = {
            '1d': {'adx': 35.0, 'plus_di': 30.0, 'minus_di': 15.0, 'rsi': 60.0},
            '4h': {'adx': 30.0, 'plus_di': 28.0, 'minus_di': 18.0, 'rsi': 58.0},
            '15m': {'adx': 28.0, 'plus_di': 25.0, 'minus_di': 20.0, 'rsi': 55.0},
        }

        state = judgment.judge(indicators)

        assert state.confidence == 1.0

    def test_partial_confidence_some_trending(self, judgment):
        """Test partial confidence when some timeframes trending"""
        # Only 2 out of 3 trending
        indicators = {
            '1d': {'adx': 35.0, 'plus_di': 30.0, 'minus_di': 15.0, 'rsi': 60.0},  # Trending
            '4h': {'adx': 30.0, 'plus_di': 28.0, 'minus_di': 18.0, 'rsi': 58.0},  # Trending
            '15m': {'adx': 15.0, 'plus_di': 25.0, 'minus_di': 20.0, 'rsi': 52.0},  # Not trending
        }

        state = judgment.judge(indicators)

        assert state.market_type == 'ranging_market'
        assert state.confidence > 0  # Some confidence due to 2 trending


class TestMarketJudgmentEdgeCases:
    """Test MarketJudgment edge cases"""

    def test_missing_timeframe(self, judgment):
        """Test handling of missing timeframe data"""
        # Missing 15m data
        indicators = {
            '1d': {'adx': 35.0, 'plus_di': 30.0, 'minus_di': 15.0, 'rsi': 60.0},
            '4h': {'adx': 30.0, 'plus_di': 28.0, 'minus_di': 18.0, 'rsi': 58.0},
            # '15m' is missing
        }

        state = judgment.judge(indicators)

        # Should handle gracefully
        assert state.market_type in ['trend_market', 'ranging_market']

    def test_none_values_in_indicators(self, judgment):
        """Test handling of None values in indicators"""
        indicators = {
            '1d': {'adx': None, 'plus_di': None, 'minus_di': None, 'rsi': None},
            '4h': {'adx': 30.0, 'plus_di': 28.0, 'minus_di': 18.0, 'rsi': 58.0},
            '15m': {'adx': 28.0, 'plus_di': 25.0, 'minus_di': 20.0, 'rsi': 55.0},
        }

        state = judgment.judge(indicators)

        # Should handle gracefully with ranging market
        assert state is not None

    def test_empty_indicators(self, judgment):
        """Test handling of empty indicators dict"""
        state = judgment.judge({})

        assert state.market_type == 'ranging_market'
        assert state.direction == 'ranging'


class TestMarketJudgmentGetSummary:
    """Test MarketJudgment.get_summary method"""

    def test_get_summary_format(self, judgment):
        """Test summary string format"""
        state = MarketState(
            market_type='trend_market',
            direction='bullish',
            confidence=0.85,
        )

        summary = judgment.get_summary(state)

        assert 'trend_market' in summary
        assert 'bullish' in summary
        assert '0.85' in summary or '0.8' in summary
