"""
Swing Detector Module
Identifies swing lows and highs from 1-minute OHLCV data.
Uses ICT logic: a swing must be held and confirmed before entry/exit.
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Swing:
    """Represents a confirmed swing point"""
    index: int           # Position in data array
    time: datetime
    price: float
    swing_type: str      # 'low' or 'high'
    is_confirmed: bool   # True if held for min confirmation bars
    bars_since_swing: int  # How many bars since this swing


class SwingDetector:
    """
    Detects swing lows and highs from 1-minute OHLCV data.
    
    Logic:
    - Swing low: Price low < previous 2 lows AND holds
    - Swing high: Price high > previous 2 highs AND holds
    - Confirmation: Swing must be held for N bars after detection
    """
    
    def __init__(self, min_confirmation_bars: int = 2, min_move_points: float = 3):
        """
        Args:
            min_confirmation_bars: Bars needed to confirm a swing
            min_move_points: Minimum absolute move to register as swing
        """
        self.min_confirmation_bars = min_confirmation_bars
        self.min_move_points = min_move_points
        
    def detect_swings(self, df: pd.DataFrame) -> Tuple[List[Swing], List[Swing]]:
        """
        Detect all swing lows and highs in the data.
        
        Args:
            df: DataFrame with columns ['open', 'high', 'low', 'close', 'timestamp']
            
        Returns:
            (swing_lows, swing_highs)
        """
        swing_lows = []
        swing_highs = []
        
        if len(df) < 3:
            return swing_lows, swing_highs
        
        low = df['low'].values
        high = df['high'].values
        
        # Detect swing lows
        for i in range(1, len(df) - 1):
            if self._is_swing_low(low, i):
                swing_low = Swing(
                    index=i,
                    time=df.iloc[i]['timestamp'],
                    price=low[i],
                    swing_type='low',
                    is_confirmed=self._is_swing_held(low, i, direction='low'),
                    bars_since_swing=len(df) - i - 1
                )
                swing_lows.append(swing_low)
        
        # Detect swing highs
        for i in range(1, len(df) - 1):
            if self._is_swing_high(high, i):
                swing_high = Swing(
                    index=i,
                    time=df.iloc[i]['timestamp'],
                    price=high[i],
                    swing_type='high',
                    is_confirmed=self._is_swing_held(high, i, direction='high'),
                    bars_since_swing=len(df) - i - 1
                )
                swing_highs.append(swing_high)
        
        return swing_lows, swing_highs
    
    def get_last_swing_low(self, df: pd.DataFrame) -> Optional[Swing]:
        """Get the most recent confirmed swing low"""
        lows, _ = self.detect_swings(df)
        confirmed = [s for s in lows if s.is_confirmed]
        return confirmed[-1] if confirmed else None
    
    def get_last_swing_high(self, df: pd.DataFrame) -> Optional[Swing]:
        """Get the most recent confirmed swing high"""
        _, highs = self.detect_swings(df)
        confirmed = [s for s in highs if s.is_confirmed]
        return confirmed[-1] if confirmed else None
    
    def get_swings_in_range(self, df: pd.DataFrame, start_idx: int, 
                           end_idx: int) -> Tuple[List[Swing], List[Swing]]:
        """Get swings that formed within a specific index range (e.g., macro window)"""
        all_lows, all_highs = self.detect_swings(df)
        
        lows_in_range = [s for s in all_lows if start_idx <= s.index <= end_idx]
        highs_in_range = [s for s in all_highs if start_idx <= s.index <= end_idx]
        
        return lows_in_range, highs_in_range
    
    def _is_swing_low(self, low_prices: np.ndarray, idx: int) -> bool:
        """Check if index is a potential swing low"""
        if idx < 1 or idx >= len(low_prices) - 1:
            return False
        
        current_low = low_prices[idx]
        prev_low = low_prices[idx - 1]
        next_low = low_prices[idx + 1]
        
        # Simple swing low: lower than previous and next bar
        is_swing = current_low < prev_low and current_low < next_low
        
        # Must have minimum move
        has_min_move = min(abs(current_low - prev_low), 
                          abs(current_low - next_low)) >= self.min_move_points
        
        return is_swing and has_min_move
    
    def _is_swing_high(self, high_prices: np.ndarray, idx: int) -> bool:
        """Check if index is a potential swing high"""
        if idx < 1 or idx >= len(high_prices) - 1:
            return False
        
        current_high = high_prices[idx]
        prev_high = high_prices[idx - 1]
        next_high = high_prices[idx + 1]
        
        # Simple swing high: higher than previous and next bar
        is_swing = current_high > prev_high and current_high > next_high
        
        # Must have minimum move
        has_min_move = min(abs(current_high - prev_high), 
                          abs(current_high - next_high)) >= self.min_move_points
        
        return is_swing and has_min_move
    
    def _is_swing_held(self, prices: np.ndarray, swing_idx: int, 
                      direction: str, current_idx: Optional[int] = None) -> bool:
        """
        Check if a swing has been held (not violated) through min confirmation bars.
        
        Args:
            prices: Array of lows (for swing low) or highs (for swing high)
            swing_idx: Index where swing formed
            direction: 'low' or 'high'
            current_idx: Current bar index (default: last bar)
        """
        if current_idx is None:
            current_idx = len(prices) - 1
        
        swing_price = prices[swing_idx]
        bars_held = current_idx - swing_idx
        
        if bars_held < self.min_confirmation_bars:
            return False
        
        # Check if swing was violated in the confirmation period
        if direction == 'low':
            # For swing low, check that no bar went below it (violation tolerance)
            violation_tolerance = 0.25  # Allow 0.25 point violation
            prices_after = prices[swing_idx + 1:current_idx + 1]
            return all(p >= swing_price - violation_tolerance for p in prices_after)
        else:  # high
            # For swing high, check that no bar went above it
            violation_tolerance = 0.25
            prices_after = prices[swing_idx + 1:current_idx + 1]
            return all(p <= swing_price + violation_tolerance for p in prices_after)
    
    def find_delivery_origin(self, df: pd.DataFrame, h1_candle_dir: str,
                            h1_high: float, h1_low: float) -> Optional[Dict]:
        """
        Find the FIRST held swing that delivered the H1 candle.
        
        This is the key function for ICT macro analysis.
        
        Args:
            df: 1-minute bars for the hour
            h1_candle_dir: 'up' or 'down' (direction of H1 candle)
            h1_high: High of the H1 candle
            h1_low: Low of the H1 candle
            
        Returns:
            Dictionary with origin swing details, or None if no delivery found
        """
        h1_range = h1_high - h1_low
        delivery_threshold = h1_range * 0.60  # 60% of range
        
        if h1_candle_dir == 'up':
            # Bullish candle: find swing low that delivered to H1 high
            lows, _ = self.detect_swings(df)
            confirmed_lows = [s for s in lows if s.is_confirmed]
            
            for swing in confirmed_lows:
                # Does this swing low deliver 60% of the range to H1 high?
                delivery = h1_high - swing.price
                if delivery >= delivery_threshold:
                    return {
                        'swing_type': 'low',
                        'swing_price': swing.price,
                        'swing_time': swing.time,
                        'swing_index': swing.index,
                        'delivery_points': delivery,
                        'h1_range': h1_range,
                        'delivery_ratio': delivery / h1_range,
                        'qualified': True
                    }
        else:  # down
            # Bearish candle: find swing high that delivered to H1 low
            _, highs = self.detect_swings(df)
            confirmed_highs = [s for s in highs if s.is_confirmed]
            
            for swing in confirmed_highs:
                # Does this swing high deliver 60% of the range to H1 low?
                delivery = swing.price - h1_low
                if delivery >= delivery_threshold:
                    return {
                        'swing_type': 'high',
                        'swing_price': swing.price,
                        'swing_time': swing.time,
                        'swing_index': swing.index,
                        'delivery_points': delivery,
                        'h1_range': h1_range,
                        'delivery_ratio': delivery / h1_range,
                        'qualified': True
                    }
        
        return None
    
    def get_swing_stats(self, df: pd.DataFrame) -> Dict:
        """Get statistics about detected swings"""
        lows, highs = self.detect_swings(df)
        confirmed_lows = [s for s in lows if s.is_confirmed]
        confirmed_highs = [s for s in highs if s.is_confirmed]
        
        return {
            'total_swings': len(lows) + len(highs),
            'swing_lows': len(lows),
            'swing_highs': len(highs),
            'confirmed_lows': len(confirmed_lows),
            'confirmed_highs': len(confirmed_highs),
            'avg_bars_between_swings': (len(df) / (len(lows) + len(highs))) 
                                       if (len(lows) + len(highs)) > 0 else 0
        }
