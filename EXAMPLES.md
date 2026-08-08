# ICT Macro Scanner - Usage Examples

## Quick Start

### Installation

```bash
git clone https://github.com/Umamaheshwar03/ict-macro-scanner.git
cd ict-macro-scanner
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Example 1: Single Scan (Test Connection)

Test the system with a single scan to verify everything is working:

```bash
python main.py --single-scan --symbols BTC/USDT ETH/USDT
```

This will:
- Connect to Binance
- Fetch recent 1-minute data
- Detect active macro windows
- Display any signals found
- Export signals to JSON

## Example 2: Live Scanning (Production)

Run continuous scanning for multiple symbols:

```bash
python main.py \
  --symbols BTC/USDT ETH/USDT SOL/USDT \
  --exchange binance \
  --interval 60 \
  --min-confidence 0.70
```

Parameters:
- `--symbols`: Trading pairs to monitor (space-separated)
- `--exchange`: CCXT exchange (binance, kraken, okx, etc.)
- `--interval`: Seconds between scans (default: 60)
- `--min-confidence`: Minimum confidence score (0-1, default: 0.70)

The scanner will:
- Check every 60 seconds if current time is in macro window
- Detect swing origins and validate delivery
- Generate signals only in macro windows (:50-:10)
- Export signals to `signals/` directory
- Log all activity to `logs/scanner.log`

## Example 3: Backtest Historical Data

Validate strategy on 2024 data for ETH:

```bash
python backtest_runner.py \
  --symbol ETH/USDT \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --risk-per-trade 0.02 \
  --reward-ratio 2.0
```

Parameters:
- `--symbol`: Trading pair to backtest
- `--start-date`: Start of backtest period (YYYY-MM-DD)
- `--end-date`: End of backtest period
- `--risk-per-trade`: Risk % per trade (default: 2%)
- `--reward-ratio`: Target R/R ratio (default: 2.0)

Output:
```
╔════════════════════════════════════════════════════════════════╗
║              BACKTEST REPORT - ETH/USDT
║              2024-01-01 to 2024-12-31
╚════════════════════════════════════════════════════════════════╝

TRADE STATISTICS:
  Total Trades: 247
  Winning Trades: 176
  Losing Trades: 71
  Win Rate: 71.3%

PROFITABILITY:
  Total Points: 4,821.50
  Avg Per Trade: 19.52
  Avg Win: 31.25
  Avg Loss: -12.50
  Profit Factor: 2.87x
```

## Example 4: Multi-Symbol Backtest

Compare strategy across multiple symbols:

```bash
python backtest_runner.py \
  --symbols BTC/USDT ETH/USDT SOL/USDT XRP/USDT \
  --start-date 2024-01-01 \
  --end-date 2024-12-31
```

## Example 5: Python API Usage

Use the scanner programmatically in your own code:

### Basic Analysis

```python
from core.macro_analyzer import MacroAnalyzer
from data.data_fetcher import CCXTFetcher

# Setup
fetcher = CCXTFetcher('binance')
analyzer = MacroAnalyzer()

# Fetch 1-hour of 1-minute data
minute_data = fetcher.fetch_minute_data('ETH/USDT', hours=1)

# Analyze the hour
pd_array = analyzer.analyze_hour(
    minute_data,
    pd.Timestamp.now().replace(minute=0, second=0, microsecond=0)
)

# Check results
if pd_array:
    print(f"Macro-Origin Rate: {pd_array.macro_window_start}")
    print(f"Launch at: {pd_array.launch_origin_price}")
    print(f"In Macro: {pd_array.origin_in_macro}")
    print(f"Confidence: {pd_array.confidence_score:.1%}")
```

### Swing Detection

```python
from core.swing_detector import SwingDetector
import pandas as pd

detector = SwingDetector(min_confirmation_bars=2)

# Detect swings
lows, highs = detector.detect_swings(minute_data)

# Get only confirmed swings
confirmed_lows = [s for s in lows if s.is_confirmed]
confirmed_highs = [s for s in highs if s.is_confirmed]

print(f"Confirmed swing lows: {len(confirmed_lows)}")
print(f"Confirmed swing highs: {len(confirmed_highs)}")

# Find delivery origin for hourly candle
origin = detector.find_delivery_origin(
    minute_data,
    'bullish',  # Direction
    2500.50,    # H1 high
    2450.00     # H1 low
)

if origin:
    print(f"Origin at: {origin['swing_price']}")
    print(f"Delivery: {origin['delivery_points']} pts")
```

### Live Scanning

```python
import asyncio
from scanner.live_scanner import LiveScannerLoop

# Create scanner
loop = LiveScannerLoop(
    symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
    scan_interval=60,
    exchange='binance',
    min_confidence=0.70
)

# Run live scanning
asyncio.run(loop.run())
```

## Example 6: Backtest with Custom Parameters

Fine-tune the backtest with different risk parameters:

```bash
# Aggressive (higher win rate requirement)
python backtest_runner.py \
  --symbol ETH/USDT \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --risk-per-trade 0.01 \
  --reward-ratio 3.0 \
  --slippage 2

# Conservative (tighter risk management)
python backtest_runner.py \
  --symbol ETH/USDT \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --risk-per-trade 0.02 \
  --reward-ratio 1.5 \
  --slippage 0.5
```

## Example 7: Custom Configuration

Edit `config.py` to customize scanner behavior:

```python
# Customize macro window
MACRO_START_OFFSET = -10  # :50
MACRO_END_OFFSET = 10     # :10
DELIVERY_THRESHOLD = 0.60  # 60% of H1 range

# Active hours (ET timezone)
ACTIVE_HOURS = list(range(7, 22))  # 7 AM - 10 PM
SKIP_HOURS = {9}  # Skip NY open

# Scanning parameters
SCAN_INTERVAL = 60  # Seconds
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']

# Confidence thresholds
MIN_CONFIDENCE_SCORE = 0.70
MACRO_EFFICIENCY_WEIGHT = 0.30
```

Then run with custom config:

```bash
python main.py --symbols BTC/USDT --interval 30
```

## Example 8: Historical Analysis Report

Generate detailed analysis for a period:

```python
from core.macro_analyzer import MacroAnalyzer, MacroAnalysisReport
from data.data_fetcher import CCXTFetcher
import pandas as pd

fetcher = CCXTFetcher('binance')
analyzer = MacroAnalyzer()

# Fetch all data for period
df = fetcher.fetch_hourly_data('ETH/USDT', days=30)

# Analyze entire period
result = analyzer.analyze_period(
    df,
    '2024-11-01',
    '2024-11-30'
)

# Print formatted report
print(MacroAnalysisReport.format_summary(result))
print(MacroAnalysisReport.format_hourly_breakdown(result['hourly_breakdown']))
```

## Example 9: Output Files

The scanner generates several output files:

### Signals Directory
```
signals/
├── active_signals_2024-12-15.json      # Current active signals
├── closed_signals_2024-12-15.json      # Closed signals from today
└── scan_20241215_143022.json           # Individual scan results
```

### Backtest Reports
```
backtest_reports/
├── ETH_USDT_2024-01-01_2024-12-31.json
├── BTC_USDT_2024-01-01_2024-12-31.json
└── backtest_results_20241215_143022.json  # Summary of all backtests
```

### Logs
```
logs/
└── scanner.log                         # All scanner activity
```

## Example 10: Integration with Trading Bot

Use this project as a signal generator for your trading bot:

```python
from scanner.live_scanner import LiveMacroScanner
from your_broker_api import TradingClient

scanner = LiveMacroScanner(['BTC/USDT', 'ETH/USDT'])
broker = TradingClient(api_key='...', secret='...')

while True:
    # Scan for signals
    signals = scanner.scan(min_confidence=0.75)
    
    for signal in signals:
        if signal['in_macro']:
            # Place trade
            order = broker.place_order(
                symbol=signal['symbol'],
                side='BUY' if signal['bias'] == 'bullish' else 'SELL',
                order_type='LIMIT',
                size=0.01,
                price=signal['price']
            )
            
            # Track signal
            scanner.active_signals[signal['signal_id']] = signal
    
    # Wait for next scan
    time.sleep(60)
```

## Troubleshooting

### "No data fetched"
- Check internet connection
- Verify exchange is online
- Try different symbol or exchange
- Check CCXT rate limits

### "Insufficient data"
- Need at least 60 1-minute candles for hourly analysis
- Try fetching more historical data
- Ensure market is liquid (high volume)

### "Confidence score too low"
- Lower `MIN_CONFIDENCE_SCORE` in config.py
- Use `--min-confidence 0.60` flag
- Wait for macro window (:50-:10)

### "Connection timeout"
- Check internet connection
- Increase `rateLimit` in config
- Try fewer symbols to scan

## Performance Tips

1. **Reduce scan interval** for more frequent signals (but higher API calls)
2. **Filter by hour** - skip low-efficiency hours (e.g., hour 8, 9)
3. **Use multiple exchanges** for better liquidity
4. **Add correlation filter** - skip highly correlated pairs
5. **Implement take-profit** - close winners early
6. **Use time-based exits** - close after X hours if no target hit

## Next Steps

1. ✓ Run single scan to test setup
2. ✓ Backtest on historical data to validate strategy
3. ✓ Run live scanner during macro windows
4. ✓ Track signals and real-world performance
5. → Optimize based on results
6. → Add higher-timeframe confluence filters
7. → Integrate with broker API for automated trading
