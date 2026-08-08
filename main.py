#!/usr/bin/env python3
"""
ICT Macro Scanner - Live Trading Entry Point
Continuously scans for hourly macro setups in real-time.
"""

import asyncio
import logging
import argparse
from datetime import datetime

from config import (
    SYMBOLS, EXCHANGE, SCAN_INTERVAL, ACTIVE_HOURS, SKIP_HOURS,
    LOG_LEVEL, LOG_FILE, SIGNALS_DIR
)
from scanner.live_scanner import LiveMacroScanner, LiveScannerLoop
from data.data_fetcher import CCXTFetcher

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Live scanning entry point"""
    parser = argparse.ArgumentParser(
        description='ICT Macro Scanner - Real-time trading signals'
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        default=SYMBOLS,
        help='Trading pairs to scan (default: config.py)'
    )
    parser.add_argument(
        '--exchange',
        default=EXCHANGE,
        help='CCXT exchange (default: binance)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=SCAN_INTERVAL,
        help='Scan interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.70,
        help='Minimum confidence score (0-1, default: 0.70)'
    )
    parser.add_argument(
        '--single-scan',
        action='store_true',
        help='Run single scan and exit (for testing)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("ICT MACRO SCANNER - LIVE TRADING MODE")
    logger.info("=" * 70)
    logger.info(f"Symbols: {', '.join(args.symbols)}")
    logger.info(f"Exchange: {args.exchange}")
    logger.info(f"Scan Interval: {args.interval}s")
    logger.info(f"Min Confidence: {args.min_confidence:.1%}")
    logger.info(f"Active Hours: {ACTIVE_HOURS}")
    logger.info(f"Skip Hours: {SKIP_HOURS}")
    logger.info("=" * 70)
    
    if args.single_scan:
        # Single scan mode (for testing)
        run_single_scan(args.symbols, args.exchange, args.min_confidence)
    else:
        # Continuous scanning
        try:
            asyncio.run(run_live_scanning(
                args.symbols,
                args.exchange,
                args.interval,
                args.min_confidence
            ))
        except KeyboardInterrupt:
            logger.info("Scanner stopped by user")


def run_single_scan(symbols: list, exchange: str, min_confidence: float):
    """Run a single scan for testing"""
    logger.info("Running single scan...")
    
    scanner = LiveMacroScanner(symbols, exchange, ACTIVE_HOURS, SKIP_HOURS)
    
    new_signals = scanner.scan(min_confidence)
    
    if new_signals:
        logger.info(f"\n✓ Found {len(new_signals)} signal(s):\n")
        for signal in new_signals:
            logger.info(
                f"  {signal['symbol']:12} {signal['bias']:8} "
                f"Macro: {signal['in_macro']} Confidence: {signal['confidence']:.1%}"
            )
    else:
        logger.info("No signals found in this scan")
    
    # Print active signals summary
    summary = scanner.get_active_signals_summary()
    logger.info(f"\nActive signals: {summary['total']}")
    
    # Export signals
    scanner.export_signals_json(
        f"{SIGNALS_DIR}/scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )


async def run_live_scanning(symbols: list, exchange: str,
                           interval: int, min_confidence: float):
    """Run continuous scanning loop"""
    logger.info("Starting continuous scanning loop...")
    
    loop = LiveScannerLoop(
        symbols=symbols,
        scan_interval=interval,
        exchange=exchange,
        min_confidence=min_confidence
    )
    
    try:
        await loop.run()
    except Exception as e:
        logger.error(f"Scanner error: {e}")
        raise


def test_data_connection(exchange: str = EXCHANGE, symbol: str = 'BTC/USDT'):
    """Test connection to data source"""
    logger.info(f"Testing connection to {exchange}...")
    
    try:
        fetcher = CCXTFetcher(exchange)
        df = fetcher.fetch_ohlcv(symbol, '1m', limit=60)
        
        if not df.empty:
            logger.info(f"✓ Successfully fetched {len(df)} 1-minute bars for {symbol}")
            logger.info(f"  Latest candle: {df.iloc[-1]['timestamp']}")
            logger.info(f"  Price: {df.iloc[-1]['close']:.2f}")
            return True
        else:
            logger.error(f"✗ No data returned for {symbol}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Connection failed: {e}")
        return False


if __name__ == '__main__':
    # Uncomment to test connection first
    # if not test_data_connection():
    #     exit(1)
    
    main()
