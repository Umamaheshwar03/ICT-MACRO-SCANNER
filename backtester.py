"""
Backtesting Engine
Validates macro strategy on historical 1-minute data.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import json

from core.macro_analyzer import MacroAnalyzer, MacroAnalysisReport
from data.data_fetcher import CCXTFetcher

logger = logging.getLogger(__name__)


class Backtester:
    """
    Historical backtester for ICT macro strategy.
    
    Simulates:
    - Macro window identification
    - Swing detection and delivery validation
    - Signal generation
    - Position management (entry, target, stop)
    - Performance metrics
    """
    
    def __init__(self, symbol: str, exchange: str = 'binance'):
        self.symbol = symbol
        self.exchange_name = exchange
        self.fetcher = CCXTFetcher(exchange)
        self.analyzer = MacroAnalyzer()
        
        # Trade tracking
        self.trades = []
        self.performance = {}
    
    def backtest_period(self, start_date: str, end_date: str,
                       risk_per_trade: float = 0.02,
                       reward_ratio: float = 2.0,
                       slippage: float = 1) -> Dict:
        """
        Run backtest for a period.
        
        Args:
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
            risk_per_trade: Risk % per trade (default 2%)
            reward_ratio: Reward/Risk ratio (default 2:1)
            slippage: Points of slippage per trade
            
        Returns:
            Dictionary with backtest results
        """
        logger.info(f"Starting backtest: {self.symbol} {start_date} to {end_date}")
        
        # Fetch data
        minute_data = self._fetch_backtest_data(start_date, end_date)
        
        if minute_data.empty:
            logger.error("No data available for backtest")
            return {}
        
        # Group by hour and analyze
        minute_data['timestamp'] = pd.to_datetime(minute_data['timestamp'])
        minute_data['hour'] = minute_data['timestamp'].dt.floor('H')
        
        analysis_result = self.analyzer.analyze_period(
            minute_data, start_date, end_date
        )
        
        all_pd_arrays = analysis_result['all_pd_arrays']
        
        # Simulate trades
        self._simulate_trades(
            all_pd_arrays,
            minute_data,
            risk_per_trade,
            reward_ratio,
            slippage
        )
        
        # Calculate performance
        self.performance = self._calculate_performance(risk_per_trade)
        
        # Generate report
        report = {
            'backtest_period': f"{start_date} to {end_date}",
            'symbol': self.symbol,
            'analysis': analysis_result['summary'],
            'trades': self._format_trades(),
            'performance': self.performance,
            'hourly_breakdown': analysis_result['hourly_breakdown'],
            'timestamp': datetime.now().isoformat()
        }
        
        return report
    
    def _fetch_backtest_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch historical 1-minute data for backtest period"""
        try:
            # Calculate number of days
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            days = (end - start).days + 1
            
            logger.info(f"Fetching {days} days of 1-minute data for {self.symbol}")
            
            # Fetch hourly data first (faster), then drill to minutes
            df = self.fetcher.fetch_hourly_data(self.symbol, days)
            
            if df.empty:
                logger.warning("No data fetched from exchange")
                return pd.DataFrame()
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching backtest data: {e}")
            return pd.DataFrame()
    
    def _simulate_trades(self, pd_arrays: List, minute_data: pd.DataFrame,
                        risk_per_trade: float, reward_ratio: float,
                        slippage: float):
        """Simulate trades based on PD Arrays"""
        
        for pd_array in pd_arrays:
            # Skip low-confidence setups
            if pd_array.confidence_score < 0.70:
                continue
            
            # Skip NY open hour
            if pd_array.h1_candle_time.hour == 9:
                continue
            
            # Entry point: at swing origin
            entry_price = pd_array.launch_origin_price
            entry_time = pd_array.launch_origin_time
            entry_price_with_slippage = entry_price + (slippage if pd_array.h1_direction == 'bullish' else -slippage)
            
            # Stop: below/above swing (risk amount)
            stop_distance = 10  # Fixed 10-point stop
            
            if pd_array.h1_direction == 'bullish':
                stop_price = entry_price - stop_distance
                risk_amount = entry_price_with_slippage - stop_price
                target_price = entry_price_with_slippage + (risk_amount * reward_ratio)
            else:
                stop_price = entry_price + stop_distance
                risk_amount = stop_price - entry_price_with_slippage
                target_price = entry_price_with_slippage - (risk_amount * reward_ratio)
            
            # Find exit (target or stop hit)
            exit_data = self._find_exit(
                minute_data[minute_data['timestamp'] >= entry_time],
                target_price,
                stop_price,
                pd_array.h1_direction
            )
            
            if exit_data:
                trade = {
                    'entry_time': entry_time,
                    'entry_price': entry_price_with_slippage,
                    'entry_confidence': pd_array.confidence_score,
                    'direction': pd_array.h1_direction,
                    'stop_price': stop_price,
                    'target_price': target_price,
                    'exit_time': exit_data['exit_time'],
                    'exit_price': exit_data['exit_price'],
                    'exit_type': exit_data['exit_type'],  # 'target', 'stop'
                    'points_profit': self._calculate_points(
                        pd_array.h1_direction, entry_price_with_slippage, exit_data['exit_price']
                    ),
                    'r_multiple': exit_data['r_multiple']
                }
                
                self.trades.append(trade)
    
    def _find_exit(self, future_data: pd.DataFrame, target: float,
                  stop: float, direction: str) -> Optional[Dict]:
        """Find when trade hits target or stop"""
        
        if future_data.empty:
            return None
        
        for idx, row in future_data.iterrows():
            if direction == 'bullish':
                if row['high'] >= target:
                    return {
                        'exit_time': row['timestamp'],
                        'exit_price': target,
                        'exit_type': 'target',
                        'r_multiple': 2.0  # hit 2R target
                    }
                elif row['low'] <= stop:
                    return {
                        'exit_time': row['timestamp'],
                        'exit_price': stop,
                        'exit_type': 'stop',
                        'r_multiple': -1.0  # hit 1R stop
                    }
            else:
                if row['low'] <= target:
                    return {
                        'exit_time': row['timestamp'],
                        'exit_price': target,
                        'exit_type': 'target',
                        'r_multiple': 2.0
                    }
                elif row['high'] >= stop:
                    return {
                        'exit_time': row['timestamp'],
                        'exit_price': stop,
                        'exit_type': 'stop',
                        'r_multiple': -1.0
                    }
        
        return None
    
    def _calculate_points(self, direction: str, entry: float, exit_price: float) -> float:
        """Calculate profit/loss in points"""
        if direction == 'bullish':
            return exit_price - entry
        else:
            return entry - exit_price
    
    def _calculate_performance(self, risk_per_trade: float) -> Dict:
        """Calculate performance metrics"""
        if not self.trades:
            return {}
        
        trades_df = pd.DataFrame(self.trades)
        
        # Basic metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['points_profit'] > 0])
        losing_trades = len(trades_df[trades_df['points_profit'] <= 0])
        
        win_rate = (winning_trades / total_trades) if total_trades > 0 else 0
        
        total_profit = trades_df['points_profit'].sum()
        avg_profit = trades_df['points_profit'].mean()
        avg_win = trades_df[trades_df['points_profit'] > 0]['points_profit'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['points_profit'] <= 0]['points_profit'].mean() if losing_trades > 0 else 0
        
        # Risk-adjusted metrics
        profit_factor = (
            trades_df[trades_df['points_profit'] > 0]['points_profit'].sum() /
            abs(trades_df[trades_df['points_profit'] <= 0]['points_profit'].sum())
        ) if losing_trades > 0 else float('inf')
        
        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_profit_points': total_profit,
            'avg_profit_per_trade': avg_profit,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'expectancy': expectancy,
            'largest_win': trades_df['points_profit'].max(),
            'largest_loss': trades_df['points_profit'].min()
        }
    
    def _format_trades(self) -> List[Dict]:
        """Format trades for output"""
        formatted = []
        for trade in self.trades:
            formatted.append({
                'entry': {
                    'time': trade['entry_time'].isoformat() if hasattr(trade['entry_time'], 'isoformat') else str(trade['entry_time']),
                    'price': round(trade['entry_price'], 2),
                    'confidence': round(trade['entry_confidence'], 2)
                },
                'exit': {
                    'time': trade['exit_time'].isoformat() if hasattr(trade['exit_time'], 'isoformat') else str(trade['exit_time']),
                    'price': round(trade['exit_price'], 2),
                    'type': trade['exit_type']
                },
                'direction': trade['direction'],
                'risk_reward': {
                    'stop': round(trade['stop_price'], 2),
                    'target': round(trade['target_price'], 2),
                    'points': round(trade['points_profit'], 2)
                }
            })
        return formatted
    
    def export_report(self, filename: str):
        """Export backtest report to JSON"""
        # Prepare data for JSON serialization
        def convert_types(obj):
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, dict):
                return {k: convert_types(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_types(item) for item in obj]
            return obj
        
        data = convert_types(self.performance)
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported backtest report to {filename}")


class BacktestReport:
    """Format backtest results as readable reports"""
    
    @staticmethod
    def print_summary(report: Dict):
        """Print backtest summary"""
        perf = report.get('performance', {})
        
        output = f"""
╔════════════════════════════════════════════════════════════════╗
║              BACKTEST REPORT - {report.get('symbol', 'N/A')}
║              {report.get('backtest_period', 'N/A')}
╚════════════════════════════════════════════════════════════════╝

TRADE STATISTICS:
  Total Trades: {perf.get('total_trades', 0)}
  Winning Trades: {perf.get('winning_trades', 0)}
  Losing Trades: {perf.get('losing_trades', 0)}
  Win Rate: {perf.get('win_rate', 0):.1%}

PROFITABILITY:
  Total Points: {perf.get('total_profit_points', 0):.2f}
  Avg Per Trade: {perf.get('avg_profit_per_trade', 0):.2f}
  Avg Win: {perf.get('avg_win', 0):.2f}
  Avg Loss: {perf.get('avg_loss', 0):.2f}
  Profit Factor: {perf.get('profit_factor', 0):.2f}x

RISK ANALYSIS:
  Expectancy: {perf.get('expectancy', 0):.2f} points
  Largest Win: {perf.get('largest_win', 0):.2f}
  Largest Loss: {perf.get('largest_loss', 0):.2f}

MACRO ANALYSIS:
  Total Candles: {report.get('analysis', {}).get('total_candles_analyzed', 0)}
  Macro-Origin Rate: {report.get('analysis', {}).get('macro_origin_rate', 0):.1%}
"""
        print(output)
    
    @staticmethod
    def print_hourly_breakdown(hourly_stats: Dict):
        """Print hourly performance"""
        print("\nHOURLY BREAKDOWN:")
        print("Hour     | Occurrences | Macro Rate | Avg Delivery")
        print("---------|-------------|-----------|---------------")
        
        for hour, stats in sorted(hourly_stats.items()):
            print(
                f"{hour:8s} | {stats['total_occurrences']:11d} | "
                f"{stats['macro_origin_rate']:9.1%} | {stats['avg_delivery_points']:12.2f}"
            )
