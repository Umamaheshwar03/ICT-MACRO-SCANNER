"""
ICT Macro Scanner Configuration
Central place for all tunable parameters
"""

import os
from datetime import time

# ============================================================================
# MACRO PARAMETERS (Based on 10Y research)
# ============================================================================

# Hourly macro window definition
MACRO_START_OFFSET = -10  # :50 (10 minutes before hour)
MACRO_END_OFFSET = 10     # :10 (10 minutes after hour)
MACRO_WINDOW_MINUTES = 20

# Delivery validation
DELIVERY_THRESHOLD = 0.60  # 60% of H1 range must be delivered
MIN_POINTS_TO_MOVE = 5     # Minimum absolute movement in points
SWING_HOLD_TOLERANCE = 0.25  # Points swing can be violated before terminal

# ============================================================================
# SCANNING PARAMETERS
# ============================================================================

# Live scanning settings
SCAN_INTERVAL = 60  # Check for new signals every 60 seconds
SYMBOLS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'XRP/USDT',
]

EXCHANGE = 'binance'  # Use Binance spot market (1m data available)
TIMEFRAME = '1m'      # Analyze 1-minute candles

# How much historical data to keep in memory (for swing detection)
LOOKBACK_MINUTES = 500  # ~8 hours of data

# ============================================================================
# TIME FILTERS (ET timezone)
# ============================================================================

# Active trading hours (7 AM to 10 PM ET)
ACTIVE_HOURS = list(range(7, 22))

# Hours to SKIP entirely
SKIP_HOURS = {
    9,  # 09:00-10:00 ET (NY open transition - only 40.9% macro-origin rate)
}

# Additional session filters
LONDON_SESSION = (2, 9)   # 02:00-09:00 ET
NY_SESSION = (9, 17)      # 09:00-17:00 ET
US_PM_SESSION = (14, 21)  # 14:00-21:00 ET

# ============================================================================
# SIGNAL GENERATION & VALIDATION
# ============================================================================

# Require higher-timeframe confirmation before scanning
REQUIRE_HIGHER_TF_BIAS = True
BIAS_TIMEFRAME = '1h'  # Check 1H trend direction

# Swing confirmation
MIN_BARS_CONFIRMATION = 2  # Minimum bars to confirm swing before entry
MIN_SWING_MOVE_POINTS = 3  # Minimum move to register as valid swing

# Signal quality thresholds
MIN_CONFIDENCE_SCORE = 0.70  # 70% confidence before signaling
MACRO_EFFICIENCY_WEIGHT = 0.30  # Weight historical macro success rate

# ============================================================================
# PRICE DELIVERY ARRAY DETECTION
# ============================================================================

# PD Array structure
PD_ARRAY_CONFIG = {
    'liquidity_grab_points': 20,  # Points to look for liquidity
    'reversal_confirmation_bars': 2,  # Bars needed to confirm reversal
    'delivery_mode': 'aggressive',  # 'conservative' (70%) or 'aggressive' (60%)
}

# ============================================================================
# DATA FETCHING
# ============================================================================

# CCXT exchange settings
CCXT_CONFIG = {
    'enableRateLimit': True,
    'rateLimit': 200,  # ms between requests
}

# Retry logic
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# ============================================================================
# BACKTESTING PARAMETERS
# ============================================================================

BACKTEST_CONFIG = {
    'start_date': '2024-01-01',
    'end_date': '2024-12-31',
    'symbols': ['ETH/USDT', 'BTC/USDT'],
    'timeframe': '1m',
    
    # Slippage & fees
    'slippage_points': 1,  # Assume 1 point slippage on entry/exit
    'maker_fee': 0.0001,   # 0.01% on Binance
    'taker_fee': 0.0001,   # 0.01% on Binance
    
    # Position sizing
    'risk_per_trade': 0.02,  # Risk 2% per signal
    'reward_ratio': 2.0,     # 1:2 risk/reward
    
    # Stop & target logic
    'stop_offset_points': 10,  # Place stop 10 points below swing
    'target_multiplier': 2.0,  # Target = 2x the H1 range from macro
}

# ============================================================================
# OUTPUT & LOGGING
# ============================================================================

# Signal storage
SIGNALS_DIR = 'signals'
BACKTEST_REPORTS_DIR = 'backtest_reports'
LOGS_DIR = 'logs'

# Create directories if they don't exist
os.makedirs(SIGNALS_DIR, exist_ok=True)
os.makedirs(BACKTEST_REPORTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Logging configuration
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = f'{LOGS_DIR}/scanner.log'

# Signal output format
SIGNAL_OUTPUT = 'json'  # 'json' or 'csv'

# ============================================================================
# ALERT SETTINGS (Optional)
# ============================================================================

# Discord webhook for real-time alerts
DISCORD_WEBHOOK = os.getenv('DISCORD_WEBHOOK_URL', None)

# Telegram bot
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', None)
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', None)

# Alert conditions
ALERT_ON_MACRO_ENTRY = True  # Alert when macro launch forms
ALERT_ON_DELIVERY = True     # Alert when target hit
ALERT_ON_REVERSAL = False    # Alert on failed setups

# ============================================================================
# ADVANCED SETTINGS
# ============================================================================

# Multi-timeframe confluence
CONFLUENCE_TIMEFRAMES = {
    'macro': '1h',    # Hourly macro window
    'structure': '4h', # Structure confirmation
    'bias': '1d',     # Daily bias direction
}

# Correlation filtering (skip correlated assets)
USE_CORRELATION_FILTER = True
CORRELATION_THRESHOLD = 0.85  # Skip if correlation > 85%

# Performance monitoring
TRACK_METRICS = True
METRICS_SAMPLE_RATE = 0.1  # Sample 10% of signals for deep analysis

# ============================================================================
# RESEARCH MODE (For backtesting & validation)
# ============================================================================

RESEARCH_MODE = False  # Set to True to disable live trading, run analysis only
RESEARCH_TIMEFRAMES = ['1m', '5m', '15m']  # Compare multiple timeframes
