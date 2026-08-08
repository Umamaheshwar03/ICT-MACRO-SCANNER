#!/usr/bin/env python3
"""
ICT Macro Scanner - Backtesting Entry Point
Validates strategy on historical 1-minute data.
"""

import logging
import argparse
import json
from datetime import datetime, timedelta

from config import (
    BACKTEST_CONFIG, BACKTEST_REPORTS_DIR, LOG_LEVEL, LOG_FILE
)
from backtest.backtester import Backtester, BacktestReport

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
    """Backtesting entry point"""
    parser = argparse.ArgumentParser(
        description='ICT Macro Scanner - Historical Backtesting'
    )
    parser.add_argument(
        '--symbol',
        default='ETH/USDT',
        help='Trading pair to backtest (default: ETH/USDT)'
    )
    parser.add_argument(
        '--start-date',
        default=BACKTEST_CONFIG['start_date'],
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        default=BACKTEST_CONFIG['end_date'],
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--exchange',
        default='binance',
        help='CCXT exchange (default: binance)'
    )
    parser.add_argument(
        '--risk-per-trade',
        type=float,
        default=BACKTEST_CONFIG['risk_per_trade'],
        help='Risk per trade as % (default: 2%)'
    )
    parser.add_argument(
        '--reward-ratio',
        type=float,
        default=BACKTEST_CONFIG['reward_ratio'],
        help='Reward/Risk ratio (default: 2.0)'
    )
    parser.add_argument(
        '--slippage',
        type=float,
        default=BACKTEST_CONFIG.get('slippage_points', 1),
        help='Slippage in points (default: 1)'
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='Test multiple symbols (overrides --symbol)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("ICT MACRO SCANNER - BACKTESTING MODE")
    logger.info("=" * 70)
    logger.info(f"Period: {args.start_date} to {args.end_date}")
    logger.info(f"Exchange: {args.exchange}")
    logger.info(f"Risk/Trade: {args.risk_per_trade:.2%}")
    logger.info(f"Reward/Risk: {args.reward_ratio:.1f}:1")
    logger.info(f"Slippage: {args.slippage} points")
    logger.info("=" * 70)
    
    # Determine symbols to test
    symbols = args.symbols if args.symbols else [args.symbol]
    
    # Run backtest for each symbol
    all_reports = {}
    for symbol in symbols:
        logger.info(f"\nBacktesting {symbol}...")
        
        try:
            report = run_backtest(
                symbol,
                args.start_date,
                args.end_date,
                args.exchange,
                args.risk_per_trade,
                args.reward_ratio,
                args.slippage
            )
            
            all_reports[symbol] = report
            
            # Print summary
            BacktestReport.print_summary(report)
            if 'hourly_breakdown' in report:
                BacktestReport.print_hourly_breakdown(report['hourly_breakdown'])
            
        except Exception as e:
            logger.error(f"Backtest failed for {symbol}: {e}")
            continue
    
    # Export all reports
    export_reports(all_reports)


def run_backtest(symbol: str, start_date: str, end_date: str,
                exchange: str, risk_per_trade: float,
                reward_ratio: float, slippage: float) -> dict:
    """Run backtest for a single symbol"""
    
    backtester = Backtester(symbol, exchange)
    
    report = backtester.backtest_period(
        start_date=start_date,
        end_date=end_date,
        risk_per_trade=risk_per_trade,
        reward_ratio=reward_ratio,
        slippage=slippage
    )
    
    # Export individual report
    if report:
        filename = (
            f"{BACKTEST_REPORTS_DIR}/"
            f"{symbol.replace('/', '_')}_{start_date}_{end_date}.json"
        )
        backtester.export_report(filename)
        logger.info(f"Report exported: {filename}")
    
    return report


def export_reports(reports: dict):
    """Export all backtest reports to JSON"""
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{BACKTEST_REPORTS_DIR}/backtest_results_{timestamp}.json"
    
    # Convert for JSON serialization
    def convert_types(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: convert_types(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_types(item) for item in obj]
        elif isinstance(obj, float):
            return round(obj, 4)
        return obj
    
    clean_reports = convert_types(reports)
    
    with open(filename, 'w') as f:
        json.dump(clean_reports, f, indent=2)
    
    logger.info(f"All reports exported: {filename}")
    
    # Print summary statistics
    print("\n" + "=" * 70)
    print("BACKTEST SUMMARY")
    print("=" * 70)
    
    for symbol, report in reports.items():
        perf = report.get('performance', {})
        print(f"\n{symbol}:")
        print(f"  Total Trades: {perf.get('total_trades', 0)}")
        print(f"  Win Rate: {perf.get('win_rate', 0):.1%}")
        print(f"  Total Points: {perf.get('total_profit_points', 0):.2f}")
        print(f"  Profit Factor: {perf.get('profit_factor', 0):.2f}x")


def generate_comparison_report(symbols: list, reports: dict):
    """Generate comparison report across multiple symbols"""
    
    print("\n" + "=" * 70)
    print("SYMBOL COMPARISON")
    print("=" * 70)
    print(
        "Symbol      | Trades | Win Rate | Total Pts | Profit Factor | Expectancy"
    )
    print("-" * 78)
    
    for symbol in symbols:
        report = reports.get(symbol, {})
        perf = report.get('performance', {})
        
        print(
            f"{symbol:12} | "
            f"{perf.get('total_trades', 0):6} | "
            f"{perf.get('win_rate', 0):8.1%} | "
            f"{perf.get('total_profit_points', 0):9.2f} | "
            f"{perf.get('profit_factor', 0):13.2f} | "
            f"{perf.get('expectancy', 0):10.2f}"
        )


if __name__ == '__main__':
    main()
