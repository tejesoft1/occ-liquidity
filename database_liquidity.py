import psycopg2
import psycopg2.extras
import config_liquidity as config
from datetime import datetime, timezone


def get_conn():
    return psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT, dbname=config.DB_NAME,
        user=config.DB_USER, password=config.DB_PASSWORD,
    )

def _cur(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def now_utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


# ── Pares habilitados ─────────────────────────────────────────────────────────
def get_enabled_pairs():
    conn = get_conn(); c = _cur(conn)
    c.execute('''
        SELECT exchange, symbol, symbol_raw, market_type, leverage
        FROM liquidity_pairs WHERE enabled = true ORDER BY exchange, symbol
    ''')
    rows = [dict(r) for r in c.fetchall()]
    c.close(); conn.close()
    return rows

def get_all_pairs():
    conn = get_conn(); c = _cur(conn)
    c.execute('''
        SELECT exchange, symbol, symbol_raw, market_type, leverage, enabled
        FROM liquidity_pairs ORDER BY exchange, symbol
    ''')
    rows = [dict(r) for r in c.fetchall()]
    c.close(); conn.close()
    return rows


# ── Insertar snapshots ────────────────────────────────────────────────────────
def insert_depth(exchange, symbol, mid_price,
                 buy_005, buy_010, buy_020, buy_050,
                 sell_005, sell_010, sell_020, sell_050,
                 slippage_last, bid_levels, ask_levels):
    conn = get_conn(); c = conn.cursor()
    c.execute('''
        INSERT INTO liquidity_depth
            (timestamp, exchange, symbol, mid_price,
             buy_depth_005, buy_depth_010, buy_depth_020, buy_depth_050,
             sell_depth_005, sell_depth_010, sell_depth_020, sell_depth_050,
             slippage_last_order_pct, raw_bid_levels, raw_ask_levels)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ''', (now_utc(), exchange, symbol, mid_price,
          buy_005, buy_010, buy_020, buy_050,
          sell_005, sell_010, sell_020, sell_050,
          slippage_last, bid_levels, ask_levels))
    conn.commit(); c.close(); conn.close()


def insert_volume(exchange, symbol, volume_24h, open_interest,
                  funding_rate, long_short_ratio):
    conn = get_conn(); c = conn.cursor()
    c.execute('''
        INSERT INTO liquidity_volume
            (timestamp, exchange, symbol, volume_24h_usdt,
             open_interest_usdt, funding_rate, long_short_ratio)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    ''', (now_utc(), exchange, symbol, volume_24h,
          open_interest, funding_rate, long_short_ratio))
    conn.commit(); c.close(); conn.close()


def insert_market(symbol_base, coingecko_id, market_cap,
                  circulating_supply, price_usd, price_change_24h):
    conn = get_conn(); c = conn.cursor()
    c.execute('''
        INSERT INTO liquidity_market
            (timestamp, symbol_base, coingecko_id, market_cap_usdt,
             circulating_supply, price_usd, price_change_24h_pct)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    ''', (now_utc(), symbol_base, coingecko_id, market_cap,
          circulating_supply, price_usd, price_change_24h))
    conn.commit(); c.close(); conn.close()


def insert_recommendation(exchange, symbol, leverage,
                           max_book, max_volume, max_oi,
                           recommended, limiting_factor,
                           slippage_threshold, mid_price, market_cap):
    conn = get_conn(); c = conn.cursor()
    c.execute('''
        INSERT INTO liquidity_recommendations
            (timestamp, exchange, symbol, leverage,
             max_notional_book_depth, max_notional_volume_rule, max_notional_oi_rule,
             recommended_max_notional, limiting_factor,
             slippage_threshold_pct, mid_price, market_cap_usdt)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ''', (now_utc(), exchange, symbol, leverage,
          max_book, max_volume, max_oi,
          recommended, limiting_factor,
          slippage_threshold, mid_price, market_cap))
    conn.commit(); c.close(); conn.close()


# ── Lecturas para el dashboard ────────────────────────────────────────────────
def get_current_recommendations():
    """Vista actual: último registro por exchange/symbol."""
    conn = get_conn(); c = _cur(conn)
    c.execute('SELECT * FROM liquidity_current ORDER BY exchange, symbol')
    rows = [dict(r) for r in c.fetchall()]
    c.close(); conn.close()
    return rows


def get_latest_volume(exchange, symbol):
    conn = get_conn(); c = _cur(conn)
    c.execute('''
        SELECT * FROM liquidity_volume
        WHERE exchange=%s AND symbol=%s
        ORDER BY id DESC LIMIT 1
    ''', (exchange, symbol))
    row = c.fetchone(); c.close(); conn.close()
    return dict(row) if row else {}


def get_latest_market(symbol_base):
    conn = get_conn(); c = _cur(conn)
    c.execute('''
        SELECT * FROM liquidity_market
        WHERE symbol_base=%s
        ORDER BY id DESC LIMIT 1
    ''', (symbol_base,))
    row = c.fetchone(); c.close(); conn.close()
    return dict(row) if row else {}


def get_depth_history(exchange, symbol, hours=24):
    """Historial de profundidad del book para el gráfico."""
    conn = get_conn(); c = _cur(conn)
    c.execute('''
        SELECT timestamp, mid_price,
               buy_depth_010, sell_depth_010,
               buy_depth_020, sell_depth_020
        FROM liquidity_depth
        WHERE exchange=%s AND symbol=%s
          AND timestamp >= NOW() - INTERVAL '%s hours'
        ORDER BY id ASC
    ''', (exchange, symbol, hours))
    rows = [dict(r) for r in c.fetchall()]
    c.close(); conn.close()
    return rows


def get_stats_for_slippage(account_name='owner'):
    """Lee stats de trades para calcular el umbral de slippage dinámico."""
    conn = get_conn(); c = _cur(conn)
    c.execute('''
        SELECT
            COUNT(*) AS total_trades,
            SUM(CASE WHEN pnl_usdt > 0 THEN 1 ELSE 0 END) AS winners,
            AVG(CASE WHEN pnl_pct > 0 THEN pnl_pct END)   AS avg_win_pct,
            AVG(CASE WHEN pnl_pct < 0 THEN pnl_pct END)   AS avg_loss_pct
        FROM trades
        WHERE status='closed' AND account_name=%s
    ''', (account_name,))
    row = c.fetchone(); c.close(); conn.close()
    return dict(row) if row else {}
