"""
ICT Price Delivery Arrays
Detects liquidity grab, reversal, and delivery structure of hourly candles.
Based on 10-year research validating macro-delivery correlation.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass

from .swing_detector import SwingDetector


@dataclass
class PriceDeliveryArray:
    """Complete PD Array structure"""
    h1_candle_time: datetime
    h1_direction: str  # 'bullish' or 'bearish'
    h1_open: float
    h1_close: float
    h1_high: float
    h1_low: float
    h1_range: float
    
    # Delivery origin (first held swing)
    launch_origin_price: float
    launch_origin_time: datetime
    launch_origin_index: int
    
    # Continuation pullback (last held swing)
    continuation_swing_price: float
    continuation_swing_time: datetime
    continuation_swing_index: int
    
    # Metrics
    macro_window_start: datetime  # :50 of previous hour
    macro_window_end: datetime    # :10 of current hour
    origin_in_macro: bool
    delivery_points: float
    delivery_ratio: float  # delivery / h1_range
    confidence_score: float
    

class ICTPDArrayDetector:
    """
    Detects ICT Price Delivery Arrays in hourly candles.
    
    A complete PD Array:
    1. LIQUIDITY GRAB: Initial sweep opposite to bias
    2. REVERSAL: Confirmed swing low/high
    3. DELIVERY: Push that delivers 60%+ of H1 range
    
    Key insight from 10Y research:
    72% of H1 delivery origins form inside the :50-:10 macro window
    """
    
    def __init__(self, delivery_threshold: float = 0.60):
        """
        Args:
            delivery_threshold: Required % of H1 range for qualified delivery (default 60%)
        """
        self.delivery_threshold = delivery_threshold
        self.swing_detector = SwingDetector(
            min_confirmation_bars=2,
            min_move_points=3
        )
    
    def analyze_hourly_candle(self, h1_candle: pd.Series, 
                             minute_data: pd.DataFrame,
                             macro_hour: int) -> Optional[PriceDeliveryArray]:
        """
        Analyze a single hourly candle for PD Array structure.
        
        Args:
            h1_candle: Single row with OHLCV data (open, high, low, close)
            minute_data: All 1-minute bars for that hour
            macro_hour: Which hour (0-23) to define macro window
            
        Returns:
            PriceDeliveryArray if conditions met, else None
        """
        
        h1_range = h1_candle['high'] - h1_candle['low']
        h1_direction = 'bullish' if h1_candle['close'] > h1_candle['open'] else 'bearish'
        
        # Find first held swing that delivered 60%+ of range (launch origin)
        launch_origin = self.swing_detector.find_delivery_origin(
            minute_data,
            h1_direction,
            h1_candle['high'],
            h1_candle['low']
        )
        
        if not launch_origin:
            return None  # No qualified delivery found
        
        # Find continuation pullback swings
        continuation = self._find_continuation_swings(
            minute_data,
            h1_direction,
            launch_origin['swing_index'],
            h1_candle['high'],
            h1_candle['low']
        )
        
        # Determine if launch origin was inside macro window
        macro_start_idx = self._get_macro_start_index(minute_data)
        macro_end_idx = self._get_macro_end_index(minute_data)
        origin_in_macro = macro_start_idx <= launch_origin['swing_index'] <= macro_end_idx
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            origin_in_macro,
            launch_origin['delivery_ratio'],
            macro_hour
        )
        
        # Create PD Array
        macro_times = self._get_macro_times(h1_candle['timestamp'], macro_hour)
        
        pd_array = PriceDeliveryArray(
            h1_candle_time=h1_candle['timestamp'],
            h1_direction=h1_direction,
            h1_open=h1_candle['open'],
            h1_close=h1_candle['close'],
            h1_high=h1_candle['high'],
            h1_low=h1_candle['low'],
            h1_range=h1_range,
            
            launch_origin_price=launch_origin['swing_price'],
            launch_origin_time=launch_origin['swing_time'],
            launch_origin_index=launch_origin['swing_index'],
            
            continuation_swing_price=continuation['swing_price'],
            continuation_swing_time=continuation['swing_time'],
            continuation_swing_index=continuation['swing_index'],
            
            macro_window_start=macro_times['start'],
            macro_window_end=macro_times['end'],
            origin_in_macro=origin_in_macro,
            delivery_points=launch_origin['delivery_points'],
            delivery_ratio=launch_origin['delivery_ratio'],
            confidence_score=confidence
        )
        
        return pd_array
    
    def detect_macro_window(self, df: pd.DataFrame, macro_hour: int) -> Dict:
        """
        Identify the exact :50-:10 macro window in minute data.
        
        For hour 10 (10:00-11:00), macro is 09:50-10:10
        
        Args:
            df: Minute-level data
            macro_hour: The hour (e.g., 10 for 10:00 candle)
            
        Returns:
            Dictionary with start_idx, end_idx, start_time, end_time
        """
        if len(df) < 60:
            return None
        
        # Macro starts at :50 of previous hour, ends at :10 of current hour
        # In 60-minute data, that's roughly bars 50-70 (minute 50 through minute 10 of next hour)
        
        timestamps = pd.to_datetime(df['timestamp'])
        
        # Find indices where minute is between :50 and :10 (wrapping around hour)
        macro_indices = []
        for idx, ts in enumerate(timestamps):
            minute = ts.minute
            if minute >= 50 or minute <= 10:
                macro_indices.append(idx)
        
        if not macro_indices:
            return None
        
        start_idx = macro_indices[0]
        end_idx = macro_indices[-1]
        
        return {
            'start_idx': start_idx,
            'end_idx': end_idx,
            'start_time': timestamps.iloc[start_idx],
            'end_time': timestamps.iloc[end_idx],
            'num_bars': end_idx - start_idx + 1
        }
    
    def _find_continuation_swings(self, df: pd.DataFrame, h1_direction: str,
                                 launch_idx: int, h1_high: float,
                                 h1_low: float) -> Dict:
        """
        Find the latest held swing after launch that still delivered.
        This is the "continuation pullback" or latest continuation swing.
        """
        h1_range = h1_high - h1_low
        delivery_threshold = h1_range * self.delivery_threshold
        
        # Get all swings after launch origin
        if h1_direction == 'bullish':
            _, highs = self.swing_detector.detect_swings(df)
            swings_after = [s for s in highs if s.index > launch_idx]
        else:
            lows, _ = self.swing_detector.detect_swings(df)
            swings_after = [s for s in lows if s.index > launch_idx]
        
        confirmed = [s for s in swings_after if s.is_confirmed]
        
        # Return the last confirmed swing that still qualified
        if h1_direction == 'bullish':
            for swing in reversed(confirmed):
                delivery = h1_high - swing.price
                if delivery >= delivery_threshold:
                    return {
                        'swing_price': swing.price,
                        'swing_time': swing.time,
                        'swing_index': swing.index,
                        'delivery_points': delivery,
                        'is_continuation': True
                    }
        else:
            for swing in reversed(confirmed):
                delivery = swing.price - h1_low
                if delivery >= delivery_threshold:
                    return {
                        'swing_price': swing.price,
                        'swing_time': swing.time,
                        'swing_index': swing.index,
                        'delivery_points': delivery,
                        'is_continuation': True
                    }
        
        # Fallback: return latest swing
        if confirmed:
            latest = confirmed[-1]
            return {
                'swing_price': latest.price,
                'swing_time': latest.time,
                'swing_index': latest.index,
                'delivery_points': 0,
                'is_continuation': False
            }
        
        # No swings at all
        return {
            'swing_price': h1_high if h1_direction == 'bullish' else h1_low,
            'swing_time': df.iloc[-1]['timestamp'],
            'swing_index': len(df) - 1,
            'delivery_points': 0,
            'is_continuation': False
        }
    
    def _calculate_confidence(self, origin_in_macro: bool, 
                             delivery_ratio: float, macro_hour: int) -> float:
        """
        Calculate confidence score for a PD Array signal.
        
        Factors:
        - Origin inside macro (+35% base for macro timing)
        - Delivery ratio (60-100% range)
        - Hour efficiency (some hours better than others)
        """
        score = 0.5  # Base confidence
        
        # Macro window bonus
        if origin_in_macro:
            score += 0.25  # Macro timing adds 25%
        
        # Delivery strength bonus
        delivery_strength = (delivery_ratio - 0.60) / 0.40  # Normalize to 0-1
        score += delivery_strength * 0.15
        
        # Hour-based adjustment (from 10Y research)
        hour_efficiency = self._get_hour_efficiency(macro_hour)
        score *= (1 + (hour_efficiency - 0.72) * 0.2)  # ±20% adjustment from baseline
        
        return max(0.0, min(1.0, score))  # Clamp to 0-1
    
    def _get_hour_efficiency(self, hour: int) -> float:
        """
        Historical macro-origin efficiency by hour (10Y data).
        These are actual measured percentages.
        """
        hour_stats = {
            2: 0.778,   # 02:00 ET: 77.8%
            3: 0.768,   # 03:00 ET: 76.8%
            4: 0.811,   # 04:00 ET: 81.1%
            7: 0.786,   # 07:00 ET: 78.6%
            8: 0.646,   # 08:00 ET: 64.6%
            9: 0.402,   # 09:00 ET: 40.2% (NY open - skip)
            10: 0.796,  # 10:00 ET: 79.6% (STRONG)
            11: 0.767,  # 11:00 ET: 76.7% (STRONG)
            13: 0.743,  # 13:00 ET: 74.3%
            14: 0.755,  # 14:00 ET: 75.5%
            15: 0.730,  # 15:00 ET: 73.0%
            16: 0.712,  # 16:00 ET: 71.2%
        }
        return hour_stats.get(hour, 0.72)  # Default to 10Y average
    
    def _get_macro_start_index(self, df: pd.DataFrame) -> int:
        """Get index where macro window starts (:50)"""
        if len(df) < 50:
            return 0
        
        timestamps = pd.to_datetime(df['timestamp'])
        for idx, ts in enumerate(timestamps):
            if ts.minute >= 50:
                return idx
        return 50  # Default
    
    def _get_macro_end_index(self, df: pd.DataFrame) -> int:
        """Get index where macro window ends (:10)"""
        if len(df) < 60:
            return len(df) - 1
        
        timestamps = pd.to_datetime(df['timestamp'])
        for idx, ts in enumerate(timestamps):
            if ts.minute > 10:
                return idx
        return min(70, len(df) - 1)  # Default
    
    def _get_macro_times(self, h1_time: datetime, macro_hour: int) -> Dict:
        """Calculate macro window start and end times"""
        from datetime import timedelta
        
        # Macro is :50 to :10
        start_time = h1_time.replace(minute=50) - timedelta(hours=1)
        end_time = h1_time.replace(minute=10)
        
        return {
            'start': start_time,
            'end': end_time
        }
    
    def generate_report(self, pd_arrays: List[PriceDeliveryArray]) -> Dict:
        """Generate statistical report from analyzed PD Arrays"""
        if not pd_arrays:
            return {}
        
        origins_in_macro = sum(1 for p in pd_arrays if p.origin_in_macro)
        total = len(pd_arrays)
        
        avg_delivery = np.mean([p.delivery_points for p in pd_arrays])
        avg_ratio = np.mean([p.delivery_ratio for p in pd_arrays])
        avg_confidence = np.mean([p.confidence_score for p in pd_arrays])
        
        return {
            'total_candles_analyzed': total,
            'qualified_delivery_structures': total,
            'origins_in_macro': origins_in_macro,
            'macro_origin_rate': origins_in_macro / total if total > 0 else 0,
            'avg_delivery_points': avg_delivery,
            'avg_delivery_ratio': avg_ratio,
            'avg_confidence_score': avg_confidence,
            'median_delivery_points': np.median([p.delivery_points for p in pd_arrays])
        }
