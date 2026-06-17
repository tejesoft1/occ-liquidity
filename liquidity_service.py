"""
liquidity_service.py
Lógica de cálculo de capacidad operativa de mercado.
Usa ccxt para acceso multi-exchange y CoinGecko para cap de mercado.
"""
import logging
import requests
import ccxt
import config_liquidity as config
import database_liquidity as db

logger = logging.getLogger(__name__)

# ── Instancias de exchanges (ccxt) ────────────────────────────────────────────
# Cada exchange se instancia una sola vez y se reutiliza.
# Para agregar un exchange nuevo: agregar una entrada en este dict.
_exchange_instances = {}

def get_exchange(exchange_name):
    if exchange_name not in _exchange_instances:
        kwargs = {'options': {'defaultType': 'future'}}
        if exchange_name == 'binance':
            if config.BINANCE_API_KEY:
                kwargs['apiKey'] = config.BINANCE_API_KEY
                kwargs['secret'] = config.BINANCE_API_SECRET
            if config.BINANCE_TESTNET:
                kwargs['options']['defaultType'] = 'future'
                kwargs['urls'] = {
                    'api': {
                        'public':  'https://testnet.binancefuture.com',
                        'private': 'https://testnet.binancefuture.com',
                    }
                }
        # Para agregar Bybit: ccxt.bybit({'options': {'defaultType': 'future'}})
        # Para OKX:           ccxt.okx({'options': {'defaultType': 'swap'}})
        cls = getattr(ccxt, exchange_name)
        _exchange_instances[exchange_name] = cls(kwargs)
    return _exchange_instances[exchange_name]


# ── Análisis del order book ───────────────────────────────────────────────────
def _depth_at_slippage(levels, mid_price, slippage_pct, side):
    """
    Calcula el notional disponible (USDT) dentro de un umbral de slippage.
    side: 'buy' (consume asks, precio sube) | 'sell' (consume bids, precio baja)
    """
    if side == 'buy':
        limit = mid_price * (1 + slippage_pct / 100)
        total = sum(price * qty for price, qty in levels if price <= limit)
    else:
        limit = mid_price * (1 - slippage_pct / 100)
        total = sum(price * qty for price, qty in levels if price >= limit)
    return total


def fetch_order_book_depth(exchange_name, symbol):
    """
    Consulta el order book y calcula la profundidad para los umbrales
    estándar (0.05%, 0.10%, 0.20%, 0.50%).
    Retorna un dict con todos los valores necesarios para insert_depth().
    """
    ex = get_exchange(exchange_name)
    ob = ex.fetch_order_book(symbol, limit=100)

    bids = ob['bids']  # [[price, qty], ...] ordenados de mayor a menor
    asks = ob['asks']  # [[price, qty], ...] ordenados de menor a mayor

    if not bids or not asks:
        raise ValueError(f"Order book vacío para {symbol} en {exchange_name}")

    mid_price = (bids[0][0] + asks[0][0]) / 2

    result = {
        'mid_price':   mid_price,
        'bid_levels':  len(bids),
        'ask_levels':  len(asks),
    }
    pct_keys = {0.05: '005', 0.10: '010', 0.20: '020', 0.50: '050'}
    for pct, key in pct_keys.items():
        result[f'buy_{key}']  = _depth_at_slippage(asks, mid_price, pct, 'buy')
        result[f'sell_{key}'] = _depth_at_slippage(bids, mid_price, pct, 'sell')

    return result


# ── Volumen 24h, Open Interest, Funding Rate ──────────────────────────────────
def fetch_volume_data(exchange_name, symbol, symbol_raw=None):
    ex = get_exchange(exchange_name)

    # Volumen 24h del ticker
    ticker = ex.fetch_ticker(symbol)
    volume_24h = ticker.get('quoteVolume') or 0.0

    # Open Interest via endpoint REST público de Binance
    raw = symbol_raw or symbol.replace('/', '')
    oi_usdt = fetch_open_interest_binance(raw)

    # Funding rate
    funding_rate = None
    try:
        fr = ex.fetch_funding_rate(symbol)
        funding_rate = fr.get('fundingRate')
    except Exception as e:
        logger.warning(f"Funding rate no disponible para {symbol} en {exchange_name}: {e}")

    # Long/Short ratio (no todos los exchanges lo exponen en ccxt)
    long_short_ratio = None
    try:
        if hasattr(ex, 'fetch_long_short_ratio'):
            lsr = ex.fetch_long_short_ratio(symbol, '1h')
            long_short_ratio = lsr.get('longShortRatio')
    except Exception:
        pass

    return {
        'volume_24h_usdt':    volume_24h,
        'open_interest_usdt': oi_usdt,
        'funding_rate':       funding_rate,
        'long_short_ratio':   long_short_ratio,
    }


# ── Cap de mercado (CoinGecko) — una sola llamada para todos los símbolos ─────
def fetch_market_caps_batch(symbol_bases):
    """
    Consulta CoinGecko /coins/markets en una sola llamada para todos los
    símbolos — evita el rate limit del plan gratuito (max ~30 req/min).
    """
    ids = [config.COINGECKO_IDS[b.upper()] for b in symbol_bases
           if b.upper() in config.COINGECKO_IDS]
    if not ids:
        return {}

    headers = {}
    if config.COINGECKO_API_KEY:
        headers['x-cg-pro-api-key'] = config.COINGECKO_API_KEY
        base_url = 'https://pro-api.coingecko.com/api/v3'
    else:
        base_url = 'https://api.coingecko.com/api/v3'

    params = {
        'vs_currency': 'usd',
        'ids': ','.join(ids),
        'order': 'market_cap_desc',
        'per_page': 250,
        'page': 1,
        'sparkline': 'false',
        'price_change_percentage': '24h',
    }
    resp = requests.get(f"{base_url}/coins/markets",
                        params=params, headers=headers, timeout=15)
    resp.raise_for_status()

    # Invertir el mapa COINGECKO_IDS para buscar símbolo base por id
    id_to_base = {v: k for k, v in config.COINGECKO_IDS.items()}

    result = {}
    for coin in resp.json():
        base = id_to_base.get(coin['id'])
        if base:
            result[base] = {
                'symbol_base':        base,
                'coingecko_id':       coin['id'],
                'market_cap_usdt':    coin.get('market_cap'),
                'circulating_supply': coin.get('circulating_supply'),
                'price_usd':          coin.get('current_price'),
                'price_change_24h':   coin.get('price_change_percentage_24h'),
            }
    return result


# ── Open Interest directo via REST de Binance (sin auth requerida) ─────────────
def fetch_open_interest_binance(symbol_raw):
    """
    Consulta el OI directamente via el endpoint público REST de Binance Futures.
    No requiere autenticación. Retorna el OI en USDT.
    """
    try:
        if config.BINANCE_TESTNET:
            base = 'https://testnet.binancefuture.com'
        else:
            base = 'https://fapi.binance.com'
        resp = requests.get(f"{base}/fapi/v1/openInterest",
                             params={'symbol': symbol_raw}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        oi_contracts = float(data.get('openInterest', 0))
        # OI viene en contratos (unidades del activo base), necesitamos en USDT
        # Multiplicamos por el precio actual
        price_resp = requests.get(f"{base}/fapi/v1/ticker/price",
                                   params={'symbol': symbol_raw}, timeout=10)
        price_resp.raise_for_status()
        price = float(price_resp.json().get('price', 0))
        return oi_contracts * price
    except Exception as e:
        logger.warning(f"OI REST directo falló para {symbol_raw}: {e}")
        return None


# ── Cálculo del umbral de slippage dinámico ───────────────────────────────────
def calculate_slippage_threshold(account_name='owner'):
    """
    Calcula el umbral de slippage óptimo basado en el PnL promedio real
    de la estrategia. Si no hay datos suficientes, usa el floor.
    """
    stats = db.get_stats_for_slippage(account_name)
    total = stats.get('total_trades') or 0

    if total < 10:
        # Insuficientes trades para calcular — usar floor conservador
        return config.SLIPPAGE_FLOOR_PCT

    winners  = stats.get('winners') or 0
    winrate  = winners / total
    avg_win  = float(stats.get('avg_win_pct') or 0)
    avg_loss = abs(float(stats.get('avg_loss_pct') or 0))

    pnl_esperado = (winrate * avg_win) - ((1 - winrate) * avg_loss)

    if pnl_esperado <= 0:
        return config.SLIPPAGE_FLOOR_PCT

    umbral = pnl_esperado * config.SLIPPAGE_TOLERANCE_FACTOR
    return max(config.SLIPPAGE_FLOOR_PCT,
               min(umbral, config.SLIPPAGE_CEILING_PCT))


# ── Cálculo de recomendación final ───────────────────────────────────────────
def calculate_recommendation(exchange, symbol, leverage, slippage_pct):
    """
    Combina los tres techos (book depth, volumen, OI) y devuelve
    la recomendación final con su factor limitante.
    """
    # Último snapshot de depth
    conn = db.get_conn(); c = db._cur(conn)
    c.execute('''
        SELECT mid_price, buy_depth_005, buy_depth_010, buy_depth_020, buy_depth_050
        FROM liquidity_depth
        WHERE exchange=%s AND symbol=%s
        ORDER BY id DESC LIMIT 1
    ''', (exchange, symbol))
    depth_row = c.fetchone()

    c.execute('''
        SELECT volume_24h_usdt, open_interest_usdt
        FROM liquidity_volume
        WHERE exchange=%s AND symbol=%s
        ORDER BY id DESC LIMIT 1
    ''', (exchange, symbol))
    vol_row = c.fetchone()

    c.close(); conn.close()

    if not depth_row or not vol_row:
        return None

    # Seleccionar columna de depth según el umbral calculado
    if slippage_pct <= 0.05:
        max_book = depth_row['buy_depth_005'] or 0
    elif slippage_pct <= 0.10:
        max_book = depth_row['buy_depth_010'] or 0
    elif slippage_pct <= 0.20:
        max_book = depth_row['buy_depth_020'] or 0
    else:
        max_book = depth_row['buy_depth_050'] or 0

    volume_24h = vol_row['volume_24h_usdt'] or 0
    oi_usdt    = vol_row['open_interest_usdt'] or 0

    # Techo 2: 1% del volumen 24h
    max_volume = volume_24h * config.VOLUME_RULE_PCT

    # Techo 3: OI ajustado por leverage (más conservador a mayor leverage)
    oi_pct  = config.OI_RULE_BASE_PCT / (leverage / config.OI_BASE_LEVERAGE)
    max_oi  = oi_usdt * oi_pct if oi_usdt else float('inf')

    # Mínimo de los tres = recomendación
    candidates = [
        (max_book,   'book_depth'),
        (max_volume, 'volume_24h'),
        (max_oi,     'open_interest'),
    ]
    recommended, limiting_factor = min(candidates, key=lambda x: x[0])

    # Cap de mercado (solo informativa, no como techo operacional)
    symbol_base = symbol.split('/')[0]
    mkt = db.get_latest_market(symbol_base)
    market_cap = mkt.get('market_cap_usdt')

    return {
        'exchange':             exchange,
        'symbol':               symbol,
        'leverage':             leverage,
        'max_notional_book':    max_book,
        'max_notional_volume':  max_volume,
        'max_notional_oi':      max_oi if max_oi != float('inf') else None,
        'recommended':          recommended,
        'limiting_factor':      limiting_factor,
        'slippage_threshold':   slippage_pct,
        'mid_price':            depth_row['mid_price'],
        'market_cap':           market_cap,
    }


# ── Jobs del scheduler ────────────────────────────────────────────────────────
def job_update_depth():
    """Actualiza order book para todos los pares habilitados (cada 9 min)."""
    pairs = db.get_enabled_pairs()
    slippage = calculate_slippage_threshold()

    for p in pairs:
        try:
            d = fetch_order_book_depth(p['exchange'], p['symbol'])
            db.insert_depth(
                p['exchange'], p['symbol'], d['mid_price'],
                d['buy_005'], d['buy_010'], d['buy_020'], d['buy_050'],
                d['sell_005'], d['sell_010'], d['sell_020'], d['sell_050'],
                None, d['bid_levels'], d['ask_levels']
            )
            # Recalcular recomendación con datos frescos
            rec = calculate_recommendation(
                p['exchange'], p['symbol'], p['leverage'], slippage)
            if rec:
                db.insert_recommendation(
                    rec['exchange'], rec['symbol'], rec['leverage'],
                    rec['max_notional_book'], rec['max_notional_volume'],
                    rec['max_notional_oi'],
                    rec['recommended'], rec['limiting_factor'],
                    rec['slippage_threshold'], rec['mid_price'], rec['market_cap']
                )
                logger.info(f"[depth] {p['exchange']} {p['symbol']} "
                            f"mid={d['mid_price']:.4f} "
                            f"max={rec['recommended']:,.0f} ({rec['limiting_factor']})")
            else:
                logger.info(f"[depth] {p['exchange']} {p['symbol']} "
                            f"mid={d['mid_price']:.4f} "
                            f"(sin recomendación aún — esperando datos de volumen)")
        except Exception as e:
            logger.error(f"[depth] {p['exchange']} {p['symbol']}: {e}", exc_info=True)


def job_update_volume():
    """Actualiza volumen 24h, OI y funding rate (cada 1h)."""
    pairs = db.get_enabled_pairs()
    for p in pairs:
        try:
            v = fetch_volume_data(p['exchange'], p['symbol'], p['symbol_raw'])
            db.insert_volume(
                p['exchange'], p['symbol'],
                v['volume_24h_usdt'], v['open_interest_usdt'],
                v['funding_rate'], v['long_short_ratio']
            )
            logger.info(f"[volume] {p['exchange']} {p['symbol']} "
                        f"vol24h={v['volume_24h_usdt']:,.0f} "
                        f"OI={v['open_interest_usdt']}")
        except Exception as e:
            logger.error(f"[volume] {p['exchange']} {p['symbol']}: {e}", exc_info=True)


def job_update_market():
    """Actualiza cap de mercado desde CoinGecko (cada 12h) en una sola llamada."""
    pairs = db.get_all_pairs()
    bases = list({p['symbol'].split('/')[0] for p in pairs})

    try:
        all_data = fetch_market_caps_batch(bases)
        for base, mkt in all_data.items():
            db.insert_market(
                mkt['symbol_base'], mkt['coingecko_id'],
                mkt['market_cap_usdt'], mkt['circulating_supply'],
                mkt['price_usd'], mkt['price_change_24h']
            )
            logger.info(f"[market] {base} cap={mkt['market_cap_usdt']:,.0f}")
    except Exception as e:
        logger.error(f"[market] batch falló: {e}", exc_info=True)

