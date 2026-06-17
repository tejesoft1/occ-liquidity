import os
from dotenv import load_dotenv

load_dotenv()

# ── Postgres (misma base que occ-trader-multi) ────────────────────────────────
DB_HOST     = os.getenv('LIQ_DB_HOST', 'db')
DB_PORT     = int(os.getenv('LIQ_DB_PORT', 5432))
DB_NAME     = os.getenv('LIQ_DB_NAME', 'occ_trader')
DB_USER     = os.getenv('LIQ_DB_USER', 'occ')
DB_PASSWORD = os.getenv('LIQ_DB_PASSWORD', '')

# ── API de lectura para exchanges (opcional, mejora rate limits) ──────────────
BINANCE_API_KEY    = os.getenv('LIQ_BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('LIQ_BINANCE_API_SECRET', '')
BINANCE_TESTNET    = os.getenv('LIQ_BINANCE_TESTNET', 'true').lower() == 'true'

# ── CoinGecko ────────────────────────────────────────────────────────────────
COINGECKO_API_KEY  = os.getenv('LIQ_COINGECKO_API_KEY', '')

# ── Scheduler: intervalos en segundos ────────────────────────────────────────
INTERVAL_DEPTH_SEC  = int(os.getenv('LIQ_INTERVAL_DEPTH_SEC',  540))
INTERVAL_VOLUME_SEC = int(os.getenv('LIQ_INTERVAL_VOLUME_SEC', 3600))
INTERVAL_MARKET_SEC = int(os.getenv('LIQ_INTERVAL_MARKET_SEC', 43200))

# ── Parámetros de análisis ────────────────────────────────────────────────────
SLIPPAGE_TOLERANCE_FACTOR = float(os.getenv('LIQ_SLIPPAGE_TOLERANCE', 0.10))
SLIPPAGE_FLOOR_PCT        = float(os.getenv('LIQ_SLIPPAGE_FLOOR',    0.05))
SLIPPAGE_CEILING_PCT      = float(os.getenv('LIQ_SLIPPAGE_CEILING',  0.20))
VOLUME_RULE_PCT           = float(os.getenv('LIQ_VOLUME_RULE_PCT', 0.01))
OI_RULE_BASE_PCT          = float(os.getenv('LIQ_OI_RULE_BASE_PCT', 0.005))
OI_BASE_LEVERAGE          = float(os.getenv('LIQ_OI_BASE_LEVERAGE', 3.0))

# ── API del servicio ──────────────────────────────────────────────────────────
API_TOKEN    = os.getenv('LIQ_API_TOKEN', '')
CORS_ORIGIN  = os.getenv('LIQ_CORS_ORIGIN', '*')

# ── CoinGecko IDs por símbolo base ───────────────────────────────────────────
COINGECKO_IDS = {
    'APT':  'aptos',
    'AAVE': 'aave',
    'BTC':  'bitcoin',
    'ETH':  'ethereum',
    'SOL':  'solana',
    'BNB':  'binancecoin',
    'ADA':  'cardano',
    'LTC':  'litecoin',
    'ARB':  'arbitrum',
    'AVAX': 'avalanche-2',
}
