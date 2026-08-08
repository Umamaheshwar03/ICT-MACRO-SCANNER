"""
Data Fetcher Module
Retrieves 1-minute and hourly OHLCV data from free sources (CCXT).
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
import time
import ccxt

logger = logging.getLogger(__name__)


class CCXTFetcher:
    """
    Fetch market data from CCXT-supported exchanges.
    
    Supports: Binance, Kraken, OKX, Bybit, etc.
    Recommended: Binance (reliable 1-minute data)
    """
    
    def __init__(self, exchange_name: str = 'binance', sandbox: bool = False):
        """
        Args:
            exchange_name: Name of CCXT exchange ('binance', 'kraken', etc.)
            sandbox: Use sandbox/testnet API
        """
        self.exchange_name = exchange_name.lower()
        self.sandbox = sandbox
        
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            self.exchange = exchange_class({
                'enableRateLimit': True,
                'rateLimit': 200,
            })
            
            if sandbox and hasattr(self.exchange, 'set_sandbox_mode'):
                self.exchange.set_sandbox_mode(True)
            
            logger.info(f"Initialized {exchange_name} fetcher")
        except Exception as e:
            logger.error(f"Failed to initialize {exchange_name}: {e}")
            raise
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m',
                   limit: int = 100, since: Optional[int] = None) -> pd.DataFrame:
        """
        Fetch OHLCV data.
        
        Args:
            symbol: Trading pair (e.g., 'ETH/USDT')
            timeframe: '1m', '5m', '1h', '4h', '1d'
            limit: Number of candles to fetch
            since: Milliseconds timestamp to start from
            
        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            
            # Remove zero-volume candles (often indicates incomplete data)
            df = df[df['volume'] > 0]
            
            logger.info(f"Fetched {len(df)} {timeframe} candles for {symbol}")
            return df.reset_index(drop=True)
            
        except Exception as e:
            logger.error(f"Error fetching {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    
    def fetch_minute_data(self, symbol: str, hours: int = 24) -> pd.DataFrame:
        """
        Fetch 1-minute data for the last N hours.
        
        Note: CCXT typically limits to ~500 candles per request.
        For longer periods, we need to make multiple requests.
        
        Args:
            symbol: Trading pair
            hours: Number of hours to fetch
            
        Returns:
            DataFrame with 1-minute OHLCV
        """
        all_data = []
        
        # Calculate how many 1-minute candles we need
        limit = hours * 60
        
        # Fetch in chunks (CCXT often limits to 500-1000)
        chunk_size = 500
        num_chunks = (limit // chunk_size) + 1
        
        since = None
        for i in range(num_chunks):
            try:
                chunk = self.fetch_ohlcv(symbol, '1m', limit=chunk_size, since=since)
                
                if chunk.empty:
                    break
                
                all_data.append(chunk)
                
                # Use the last timestamp as starting point for next chunk
                since = int(chunk.iloc[-1]['timestamp'].timestamp() * 1000)
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Error fetching chunk {i}: {e}")
                break
        
        if not all_data:
            return pd.DataFrame()
        
        df = pd.concat(all_data, ignore_index=True)
        df = df.sort_values('timestamp').drop_duplicates('timestamp')
        
        return df.reset_index(drop=True)
    
    def fetch_hourly_data(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """
        Fetch hourly data for backtesting.
        
        Args:
            symbol: Trading pair
            days: Number of days to fetch
            
        Returns:
            DataFrame with hourly OHLCV
        """
        limit = days * 24
        chunk_size = 500
        
        all_data = []
        since = None
        
        for i in range((limit // chunk_size) + 1):
            try:
                chunk = self.fetch_ohlcv(symbol, '1h', limit=chunk_size, since=since)
                
                if chunk.empty:
                    break
                
                all_data.append(chunk)
                since = int(chunk.iloc[-1]['timestamp'].timestamp() * 1000)
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Error fetching hourly chunk {i}: {e}")
                break
        
        if not all_data:
            return pd.DataFrame()
        
        df = pd.concat(all_data, ignore_index=True)
        df = df.sort_values('timestamp').drop_duplicates('timestamp')
        
        return df.reset_index(drop=True)
    
    def fetch_multiple_symbols(self, symbols: List[str], 
                              timeframe: str = '1m',
                              hours: int = 1) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple symbols concurrently.
        
        Args:
            symbols: List of trading pairs
            timeframe: '1m' or '1h'
            hours: Lookback period
            
        Returns:
            Dictionary mapping symbol -> DataFrame
        """
        data = {}
        
        for symbol in symbols:
            try:
                if timeframe == '1m':
                    df = self.fetch_minute_data(symbol, hours)
                else:
                    df = self.fetch_hourly_data(symbol, hours)
                
                data[symbol] = df
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                data[symbol] = pd.DataFrame()
        
        return data
    
    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validate OHLCV data quality.
        
        Returns:
            (is_valid, list_of_issues)
        """
        issues = []
        
        if df.empty:
            issues.append("Empty DataFrame")
            return False, issues
        
        # Check required columns
        required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required if col not in df.columns]
        if missing:
            issues.append(f"Missing columns: {missing}")
        
        # Check for NaN values
        if df.isnull().any().any():
            issues.append(f"Contains {df.isnull().sum().sum()} NaN values")
        
        # Check OHLC logic
        invalid_hlc = (df['high'] < df['low']).sum()
        if invalid_hlc > 0:
            issues.append(f"{invalid_hlc} candles have high < low")
        
        open_not_in_range = (
            ((df['open'] < df['low']) | (df['open'] > df['high'])).sum()
        )
        if open_not_in_range > 0:
            issues.append(f"{open_not_in_range} candles have open outside high-low")
        
        close_not_in_range = (
            ((df['close'] < df['low']) | (df['close'] > df['high'])).sum()
        )
        if close_not_in_range > 0:
            issues.append(f"{close_not_in_range} candles have close outside high-low")
        
        # Check for gaps
        if len(df) > 1:
            time_diffs = df['timestamp'].diff()
            expected_diff = time_diffs.iloc[1:].mode()[0]  # Most common interval
            large_gaps = (time_diffs > expected_diff * 2).sum()
            if large_gaps > 0:
                issues.append(f"{large_gaps} candles have larger time gaps")
        
        is_valid = len(issues) == 0
        return is_valid, issues


class DataValidator:
    """Validate and clean OHLCV data"""
    
    @staticmethod
    def remove_incomplete_candles(df: pd.DataFrame, 
                                 timeframe: str = '1m') -> pd.DataFrame:
        """Remove the most recent incomplete candle"""
        if df.empty:
            return df
        
        # Keep all but the last candle (which is being formed)
        return df.iloc[:-1].reset_index(drop=True)
    
    @staticmethod
    def forward_fill_missing(df: pd.DataFrame, 
                            max_fill: int = 3) -> pd.DataFrame:
        """Forward-fill small gaps in data"""
        if len(df) < 2:
            return df
        
        # Check for time gaps
        time_diffs = df['timestamp'].diff()
        expected_diff = time_diffs.mode()[0]
        
        # Only fill small gaps
        df_filled = df.copy()
        for col in ['close', 'volume']:
            df_filled[col] = df_filled[col].fillna(method='ffill', limit=max_fill)
        
        return df_filled
    
    @staticmethod
    def normalize_volume(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize volume to 0-1 range"""
        if 'volume' not in df.columns or df['volume'].max() == 0:
            return df
        
        df['volume_normalized'] = (
            (df['volume'] - df['volume'].min()) / 
            (df['volume'].max() - df['volume'].min())
        )
        return df
    
    @staticmethod
    def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
        """Add basic technical indicator columns"""
        df['body'] = abs(df['close'] - df['open'])
        df['wick_up'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['wick_down'] = df[['open', 'close']].min(axis=1) - df['low']
        df['range'] = df['high'] - df['low']
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
        
        return df
