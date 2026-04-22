#!/usr/bin/env python3
"""
市场状态判断模块 - MarketJudgment

功能:
根据多周期指标一致性，判断市场类型和方向
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class MarketState:
    """
    市场状态

    Attributes:
        market_type: 市场类型 (trend_market / ranging_market)
        direction: 方向 (bullish / bearish / ranging)
        confidence: 置信度 (0-1)
        primary_timeframes: 用于判断的主要周期
        aligned_timeframes: 方向一致的周期列表
        details: 各周期的详细指标值
    """

    market_type: str = "ranging_market"
    direction: str = "ranging"
    confidence: float = 0.0
    primary_timeframes: Optional[List[str]] = None
    aligned_timeframes: Optional[List[str]] = None
    details: Optional[Dict[str, Dict]] = None

    def __post_init__(self):
        if self.primary_timeframes is None:
            self.primary_timeframes = []
        if self.aligned_timeframes is None:
            self.aligned_timeframes = []
        if self.details is None:
            self.details = {}

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "market_type": self.market_type,
            "direction": self.direction,
            "confidence": self.confidence,
            "primary_timeframes": self.primary_timeframes,
            "aligned_timeframes": self.aligned_timeframes,
            "details": self.details,
        }


class MarketJudgment:
    """
    市场状态判断器

    判断规则:
    - 1d × 4h × 15m 三者方向一致 → trend_market
    - 否则 → ranging_market
    """

    def __init__(
        self,
        primary_timeframes: Optional[List[str]] = None,
        adx_trend_threshold: float = 25.0,
        rsi_bullish_threshold: float = 50.0,
        rsi_bearish_threshold: float = 50.0,
    ):
        """
        初始化判断器

        Args:
            primary_timeframes: 用于判断的主要周期列表
            adx_trend_threshold: ADX 趋势阈值
            rsi_bullish_threshold: RSI 看涨阈值
            rsi_bearish_threshold: RSI 看跌阈值
        """
        self.primary_timeframes = primary_timeframes or ["1d", "4h", "15m"]
        self.adx_trend_threshold = adx_trend_threshold
        self.rsi_bullish_threshold = rsi_bullish_threshold
        self.rsi_bearish_threshold = rsi_bearish_threshold

    def judge(
        self, indicators_by_timeframe: Dict[str, Dict[str, Optional[float]]]
    ) -> MarketState:
        """
        判断市场状态

        Args:
            indicators_by_timeframe: {timeframe: {adx, plus_di, minus_di, rsi}}

        Returns:
            MarketState 市场状态
        """
        details = {}
        bullish_count = 0
        bearish_count = 0
        trending_count = 0

        for tf in self.primary_timeframes:
            if tf not in indicators_by_timeframe:
                logger.warning(f"缺少周期 {tf} 的指标数据")
                continue

            indicators = indicators_by_timeframe[tf]
            adx = indicators.get("adx")
            plus_di = indicators.get("plus_di")
            minus_di = indicators.get("minus_di")
            rsi = indicators.get("rsi")

            # 判断该周期的状态
            tf_state = self._judge_timeframe(adx, plus_di, minus_di, rsi)
            details[tf] = {
                "adx": adx,
                "plus_di": plus_di,
                "minus_di": minus_di,
                "rsi": rsi,
                "direction": tf_state["direction"],
                "is_trending": tf_state["is_trending"],
            }

            # 统计
            if tf_state["direction"] == "bullish":
                bullish_count += 1
            elif tf_state["direction"] == "bearish":
                bearish_count += 1

            if tf_state["is_trending"]:
                trending_count += 1

        # 判断整体市场类型
        # 只有所有主要周期都是趋势且方向一致，才是 trend_market
        all_trending = trending_count == len(self.primary_timeframes)
        all_same_direction = bullish_count == len(
            self.primary_timeframes
        ) or bearish_count == len(self.primary_timeframes)

        if all_trending and all_same_direction:
            market_type = "trend_market"
            direction = "bullish" if bullish_count > bearish_count else "bearish"
            confidence = 1.0
        else:
            market_type = "ranging_market"
            direction = "ranging"
            # 计算置信度：基于有多少周期是趋势
            confidence = (
                trending_count / len(self.primary_timeframes)
                if self.primary_timeframes
                else 0.0
            )

        # 确定方向（即使在 ranging 市场，也可能有倾向性）
        if market_type == "ranging_market":
            if bullish_count > bearish_count:
                direction = "bullish"
            elif bearish_count > bullish_count:
                direction = "bearish"
            else:
                direction = "ranging"

        return MarketState(
            market_type=market_type,
            direction=direction,
            confidence=confidence,
            primary_timeframes=self.primary_timeframes,
            aligned_timeframes=self.primary_timeframes,  # 简化的实现
            details=details,
        )

    def _judge_timeframe(
        self,
        adx: Optional[float],
        plus_di: Optional[float],
        minus_di: Optional[float],
        rsi: Optional[float],
    ) -> dict:
        """
        判断单个周期的状态

        Returns:
            {direction: str, is_trending: bool}
        """
        result = {
            "direction": "ranging",
            "is_trending": False,
        }

        # 检查数据是否可用
        if adx is None or plus_di is None or minus_di is None:
            return result

        # 判断是否为趋势市场
        is_trending = adx > self.adx_trend_threshold
        result["is_trending"] = is_trending

        if not is_trending:
            return result

        # 判断方向
        if plus_di > minus_di:
            # 上涨趋势
            if rsi is not None and rsi > self.rsi_bullish_threshold:
                result["direction"] = "bullish"
            else:
                result["direction"] = "bullish"  # DI 交叉优先
        elif minus_di > plus_di:
            # 下跌趋势
            if rsi is not None and rsi < self.rsi_bearish_threshold:
                result["direction"] = "bearish"
            else:
                result["direction"] = "bearish"  # DI 交叉优先
        else:
            result["direction"] = "ranging"

        return result

    def get_summary(self, state: MarketState) -> str:
        """
        获取状态摘要字符串

        Args:
            state: MarketState

        Returns:
            摘要字符串
        """
        return (
            f"Market: {state.market_type}, "
            f"Direction: {state.direction}, "
            f"Confidence: {state.confidence:.2f}"
        )
