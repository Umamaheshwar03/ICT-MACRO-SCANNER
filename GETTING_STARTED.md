# Getting Started - ICT Macro Scanner

This guide will get you up and running in 5 minutes.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Internet connection (for market data)

Check your Python version:
```bash
python --version  # Should be 3.8+
```

## Step 1: Clone or Download Project

```bash
# Clone from GitHub (or download as ZIP)
git clone https://github.com/yourusername/ict-macro-scanner.git
cd ict-macro-scanner
```

## Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- pandas (data manipulation)
- numpy (numerical operations)
- ccxt (market data)
- Other dependencies

Installation typically takes 2-3 minutes.

## Step 4: Test Your Installation

Run a quick test to verify everything works:

```bash
python main.py --single-scan --symbols BTC/USDT
```

Expected output:
```
2024-12-15 14:30:22 - __main__ - INFO - ======================================================================
2024-12-15 14:30:22 - __main__ - INFO - ICT MACRO SCANNER - LIVE TRADING MODE
2024-12-15 14:30:22 - __main__ - INFO - Symbols: BTC/USDT
2024-12-15 14:30:22 - __main__ - INFO - Exchange: binance
2024-12-15 14:30:22 - __main__ - INFO - Scan Interval: 60s
2024-12-15 14:30:23 - scanner - INFO - Scanning BTC/USDT...
2024-12-15 14:30:25 - data - INFO - Fetched 120 1m candles for BTC/USDT
```

If you see data being fetched, **you're ready to go!**

## Step 5: Run Your First Backtest

Test the strategy on historical data:

```bash
python backtest_runner.py \
  --symbol ETH/USDT \
  --start-date 2024-11-01 \
  --end-date 2024-11-30
```

Expected output:
```
╔════════════════════════════════════════════════════════════════╗
║              BACKTEST REPORT - ETH/USDT
║              2024-11-01 to 2024-11-30
╚════════════════════════════════════════════════════════════════╝

TRADE STATISTICS:
  Total Trades: 23
  Winning Trades: 16
  Losing Trades: 7
  Win Rate: 69.6%

PROFITABILITY:
  Total Points: 487.50
  Avg Per Trade: 21.19
```

## Common Commands

### Single Scan (Test)
```bash
python main.py --single-scan --symbols BTC/USDT ETH/USDT
```

### Live Scanning (30-second interval)
```bash
python main.py --symbols BTC/USDT ETH/USDT --interval 30
```

### Backtest Multiple Symbols
```bash
python backtest_runner.py \
  --symbols BTC/USDT ETH/USDT SOL/USDT \
  --start-date 2024-01-01 \
  --end-date 2024-12-31
```

### Lower Confidence Threshold
```bash
python main.py --single-scan --min-confidence 0.60
```

## Understanding Output Files

After running, check these directories:

```
signals/
  └── scan_20241215_143022.json   # Signals from this scan

backtest_reports/
  └── ETH_USDT_2024-11-01_2024-11-30.json  # Backtest results

logs/
  └── scanner.log   # All activity log
```

View a signal file:
```bash
# On Windows:
type signals\scan_20241215_143022.json

# On macOS/Linux:
cat signals/scan_20241215_143022.json
```

## Configuration

The system is configured via `config.py`. Default settings work well for:
- ETH/USDT, BTC/USDT, SOL/USDT
- Binance exchange
- 7 AM - 10 PM ET active hours

To customize:

```python
# In config.py

# Change active trading hours (example: 9 AM - 5 PM ET)
ACTIVE_HOURS = list(range(9, 18))

# Add more symbols
SYMBOLS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'XRP/USDT',  # Add this
    'ADA/USDT',  # Add this
]

# Lower confidence for more signals
MIN_CONFIDENCE_SCORE = 0.60
```

Then save and run again.

## Troubleshooting

### "ModuleNotFoundError: No module named 'ccxt'"

**Solution**: Reinstall requirements
```bash
pip install --upgrade -r requirements.txt
```

### "No data returned" or "Insufficient data"

**Possible causes:**
- Market hours (ETH/USDT trades 24/7, others have limited hours)
- Exchange is down
- Rate limits hit too quickly

**Solutions:**
- Try a different symbol (BTC/USDT is most liquid)
- Wait a minute and try again
- Check your internet connection

### "Cannot find signals directory"

**Solution**: The scanner creates it automatically. If it doesn't:
```bash
mkdir signals
mkdir logs
mkdir backtest_reports
```

### Scan is slow or timing out

**Solution**: Increase the rate limit in requests
```python
# In config.py
CCXT_CONFIG = {
    'enableRateLimit': True,
    'rateLimit': 500,  # Increase from 200 to 500
}
```

### "Confidence score too low"

The default is 0.70. To see more signals:
```bash
python main.py --min-confidence 0.60
```

Or change in config.py:
```python
MIN_CONFIDENCE_SCORE = 0.60
```

## Next Steps

1. **Read the full README**: `README.md`
2. **See examples**: `EXAMPLES.md`
3. **Understand the project**: `PROJECT_SUMMARY.md`
4. **Check the code**: Start with `core/macro_analyzer.py`
5. **Customize for your needs**: Edit `config.py`
6. **Deploy to GitHub**: For portfolio

## Questions?

- Read the docstrings in the code
- Check `EXAMPLES.md` for code samples
- Look at `logs/scanner.log` for detailed output
- Review the README for architecture overview

## Success Checklist

✓ Python 3.8+ installed  
✓ Virtual environment created and activated  
✓ Dependencies installed  
✓ Single scan runs successfully  
✓ Backtest completes and shows results  
✓ Understand signals and output files  
✓ Can customize config.py  

**You're ready to use ICT Macro Scanner!**

---

## Quick Reference

| Task | Command |
|------|---------|
| Test installation | `python main.py --single-scan --symbols BTC/USDT` |
| Scan one hour | `python main.py --single-scan` |
| Scan continuously | `python main.py` |
| Backtest 1 month | `python backtest_runner.py --symbol ETH/USDT --start-date 2024-11-01 --end-date 2024-11-30` |
| Backtest 1 year | `python backtest_runner.py --symbol ETH/USDT --start-date 2024-01-01 --end-date 2024-12-31` |
| View signals | `cat signals/scan_*.json` |
| View logs | `tail logs/scanner.log` |
| Edit config | Open `config.py` in any text editor |

---

**Happy scanning!** 🚀
