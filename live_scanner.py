"""
Live Trading Scanner
Continuously monitors market data and generates signals in real-time.
"""

import pandas as pd
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio
import json

from core.macro_analyzer import MacroAnalyzer
from core.ict_pd_arrays import PriceDeliveryArray
from data.data_fetcher import CCXTFetcher

logger = logging.getLogger(__name__)


class LiveMacroScanner:
    """
    Real-time scanner for ICT hourly macro setups.
    
    Workflow:
    1. Fetch 1-minute data for active symbols
    2. Check if current time is in macro window (:50-:10)
    3. Detect swings and validate macro delivery
    4. Generate high-confidence signals
    5. Log and alert on qualified setups
    """
    
    def __init__(self, symbols: List[str], exchange: str = 'binance',
                 active_hours: List[int] = None, skip_hours: set = None):
        """
        Args:
            symbols: List of trading pairs (e.g., ['BTC/USDT', 'ETH/USDT'])
            exchange: CCXT exchange name
            active_hours: List of hours to scan (default: 7-22 ET)
            skip_hours: Set of hours to skip (default: {9})
        """
        self.symbols = symbols
        self.exchange_name = exchange
        self.fetcher = CCXTFetcher(exchange)
        self.analyzer = MacroAnalyzer()
        
        self.active_hours = active_hours or list(range(7, 22))
        self.skip_hours = skip_hours or {9}
        
        # Signal tracking
        self.active_signals = {}
        self.closed_signals = {}
        self.signal_history = []
        
    def scan(self, min_confidence: float = 0.70) -> List[Dict]:
        """
        Perform a single scan of all symbols.
        
        Returns:
            List of new signals generated
        """
        new_signals = []
        current_hour = datetime.now().hour
        current_minute = datetime.now().minute
        
        # Check if in active trading hours
        if current_hour not in self.active_hours:
            logger.debug(f"Outside active hours ({current_hour}:00)")
            return new_signals
        
        # Check if in macro window
        in_macro = current_minute >= 50 or current_minute <= 10
        if not in_macro:
            logger.debug(f"Not in macro window (current: {current_minute}:00)")
            return new_signals
        
        # Scan each symbol
        for symbol in self.symbols:
            try:
                signal = self.scan_symbol(symbol, min_confidence)
                if signal:
                    new_signals.append(signal)
                    self.active_signals[signal['signal_id']] = signal
                    self.signal_history.append(signal)
                    
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                continue
        
        return new_signals
    
    def scan_symbol(self, symbol: str, min_confidence: float = 0.70) -> Optional[Dict]:
        """
        Scan a single symbol for macro setup.
        
        Returns:
            Signal dict if qualified setup found, else None
        """
        try:
            # Fetch recent 1-minute data (last 2 hours)
            df = self.fetcher.fetch_minute_data(symbol, hours=2)
            
            if df.empty or len(df) < 60:
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
            # Get current hour's data
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            hour_data = df[df['timestamp'] >= current_hour].copy()
            
            if len(hour_data) < 10:
                return None
            
            # Detect swings
            lows, highs = self.analyzer.swing_detector.detect_swings(hour_data)
            confirmed_lows = [s for s in lows if s.is_confirmed]
            confirmed_highs = [s for s in highs if s.is_confirmed]
            
            if not (confirmed_lows or confirmed_highs):
                return None
            
            # Determine market bias from recent price
            recent_close = hour_data.iloc[-1]['close']
            hour_start = hour_data.iloc[0]['open']
            bias = 'bullish' if recent_close > hour_start else 'bearish'
            
            # Get macro window info
            macro_info = self.analyzer.pd_detector.detect_macro_window(
                hour_data, datetime.now().hour
            )
            
            in_macro = False
            if macro_info:
                current_idx = len(hour_data) - 1
                in_macro = macro_info['start_idx'] <= current_idx <= macro_info['end_idx']
            
            # Build signal
            signal = {
                'signal_id': f"{symbol}_{datetime.now().isoformat()}",
                'timestamp': datetime.now(),
                'symbol': symbol,
                'bias': bias,
                'macro_window': f"{datetime.now().hour:02d}:50-{(datetime.now().hour+1)%24:02d}:10",
                'in_macro': in_macro,
                'confirmed_swings': {
                    'lows': len(confirmed_lows),
                    'highs': len(confirmed_highs)
                },
                'price': recent_close,
                'swing_count': len(confirmed_lows) + len(confirmed_highs),
                'status': 'ACTIVE',
                'confidence': 0.75 if in_macro else 0.60
            }
            
            # Only return if meets confidence threshold
            if signal['confidence'] >= min_confidence:
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return None
    
    def update_signal(self, signal_id: str, price: float, 
                     target_hit: bool = False, stop_hit: bool = False):
        """Update an active signal with new price data"""
        if signal_id not in self.active_signals:
            return
        
        signal = self.active_signals[signal_id]
        signal['last_update'] = datetime.now()
        signal['current_price'] = price
        
        if target_hit:
            signal['status'] = 'TARGET_HIT'
            self.closed_signals[signal_id] = self.active_signals.pop(signal_id)
            logger.info(f"✓ Signal {signal_id} TARGET HIT at {price}")
            
        elif stop_hit:
            signal['status'] = 'STOP_HIT'
            self.closed_signals[signal_id] = self.active_signals.pop(signal_id)
            logger.warning(f"✗ Signal {signal_id} STOP HIT at {price}")
    
    def close_expired_signals(self, max_age_minutes: int = 60):
        """Close signals that are older than max_age"""
        now = datetime.now()
        expired = []
        
        for signal_id, signal in self.active_signals.items():
            age = (now - signal['timestamp']).total_seconds() / 60
            if age > max_age_minutes:
                signal['status'] = 'EXPIRED'
                self.closed_signals[signal_id] = signal
                expired.append(signal_id)
        
        for signal_id in expired:
            del self.active_signals[signal_id]
            logger.info(f"Signal {signal_id} expired after {max_age_minutes}min")
    
    def get_active_signals_summary(self) -> Dict:
        """Get summary of currently active signals"""
        if not self.active_signals:
            return {'total': 0, 'signals': []}
        
        summary = {
            'total': len(self.active_signals),
            'by_symbol': {},
            'by_status': {},
            'signals': []
        }
        
        for signal_id, signal in self.active_signals.items():
            # By symbol
            symbol = signal['symbol']
            if symbol not in summary['by_symbol']:
                summary['by_symbol'][symbol] = 0
            summary['by_symbol'][symbol] += 1
            
            # By status
            status = signal['status']
            if status not in summary['by_status']:
                summary['by_status'][status] = 0
            summary['by_status'][status] += 1
            
            # Add to signals list
            summary['signals'].append({
                'id': signal_id,
                'symbol': symbol,
                'time': signal['timestamp'].isoformat(),
                'bias': signal['bias'],
                'in_macro': signal['in_macro'],
                'confidence': signal['confidence'],
                'price': signal.get('price'),
                'status': status
            })
        
        return summary
    
    def export_signals_json(self, filename: str):
        """Export active signals to JSON"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'active_signals': list(self.active_signals.values()),
            'closed_signals': list(self.closed_signals.values()),
            'summary': self.get_active_signals_summary()
        }
        
        # Convert datetime objects to strings for JSON serialization
        def convert_datetimes(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_datetimes(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetimes(item) for item in obj]
            return obj
        
        data = convert_datetimes(data)
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported signals to {filename}")


class LiveScannerLoop:
    """
    Async loop for continuous scanning.
    
    Usage:
        loop = LiveScannerLoop(symbols, scan_interval=60)
        await loop.run()
    """
    
    def __init__(self, symbols: List[str], scan_interval: int = 60,
                 exchange: str = 'binance', min_confidence: float = 0.70):
        self.scanner = LiveMacroScanner(symbols, exchange)
        self.scan_interval = scan_interval
        self.min_confidence = min_confidence
        self.running = False
    
    async def run(self):
        """Start the continuous scanning loop"""
        self.running = True
        logger.info(f"Starting live scanner loop (interval: {self.scan_interval}s)")
        
        try:
            while self.running:
                # Perform scan
                new_signals = self.scanner.scan(self.min_confidence)
                
                if new_signals:
                    logger.info(f"Found {len(new_signals)} new signal(s)")
                    for signal in new_signals:
                        logger.info(
                            f"  → {signal['symbol']}: {signal['bias']} "
                            f"(confidence: {signal['confidence']:.1%})"
                        )
                
                # Update signal tracking
                self.scanner.close_expired_signals(max_age_minutes=60)
                
                # Log summary
                summary = self.scanner.get_active_signals_summary()
                if summary['total'] > 0:
                    logger.info(f"Active signals: {summary['total']} "
                               f"({json.dumps(summary['by_symbol'])})")
                
                # Wait for next scan
                await asyncio.sleep(self.scan_interval)
        
        except KeyboardInterrupt:
            logger.info("Scanner stopped by user")
        except Exception as e:
            logger.error(f"Error in scan loop: {e}")
        finally:
            self.running = False
            # Export final signals
            self.scanner.export_signals_json(
                f"signals/final_signals_{datetime.now().isoformat()}.json"
            )
    
    def stop(self):
        """Stop the scanning loop"""
        self.running = False
        logger.info("Stopping scanner")
