-- create_liquidity_tables.sql
-- Correr una vez contra el Postgres de producción (contenedor "db"):
--   docker exec -it db psql -U occ -d occ_trader -f /ruta/create_liquidity_tables.sql
--
-- Las tablas viven en la misma base de datos (occ_trader) para que
-- occ-trader-multi pueda leer de ellas directamente en el futuro.

-- ── Configuración de pares a monitorear ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS liquidity_pairs (
    id          SERIAL PRIMARY KEY,
    exchange    TEXT NOT NULL,          -- 'binance', 'bybit', 'okx', etc.
    symbol      TEXT NOT NULL,          -- 'APT/USDT' (formato ccxt)
    symbol_raw  TEXT NOT NULL,          -- 'APTUSDT' (formato nativo del exchange)
    market_type TEXT NOT NULL DEFAULT 'future',  -- 'future' | 'spot'
    enabled     BOOLEAN NOT NULL DEFAULT true,
    leverage    INTEGER NOT NULL DEFAULT 3,
    created_at  TEXT NOT NULL,
    UNIQUE (exchange, symbol)
);

-- ── Snapshots de profundidad del order book (cada 9 min) ─────────────────────
CREATE TABLE IF NOT EXISTS liquidity_depth (
    id              SERIAL PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    exchange        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    mid_price       DOUBLE PRECISION NOT NULL,
    -- Notional disponible (en USDT) para BUY a distintos % de slippage
    buy_depth_005   DOUBLE PRECISION,  -- 0.05%
    buy_depth_010   DOUBLE PRECISION,  -- 0.10%
    buy_depth_020   DOUBLE PRECISION,  -- 0.20%
    buy_depth_050   DOUBLE PRECISION,  -- 0.50%
    -- Notional disponible para SELL
    sell_depth_005  DOUBLE PRECISION,
    sell_depth_010  DOUBLE PRECISION,
    sell_depth_020  DOUBLE PRECISION,
    sell_depth_050  DOUBLE PRECISION,
    -- Slippage estimado para el notional de la última orden real
    slippage_last_order_pct DOUBLE PRECISION,
    raw_bid_levels  INTEGER,           -- número de niveles en el bid
    raw_ask_levels  INTEGER            -- número de niveles en el ask
);
CREATE INDEX IF NOT EXISTS idx_depth_exchange_symbol_ts
    ON liquidity_depth (exchange, symbol, timestamp DESC);

-- ── Snapshots de volumen y open interest (cada 1h) ───────────────────────────
CREATE TABLE IF NOT EXISTS liquidity_volume (
    id                  SERIAL PRIMARY KEY,
    timestamp           TEXT NOT NULL,
    exchange            TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    volume_24h_usdt     DOUBLE PRECISION NOT NULL,
    open_interest_usdt  DOUBLE PRECISION,
    funding_rate        DOUBLE PRECISION,   -- tasa de financiamiento actual
    long_short_ratio    DOUBLE PRECISION    -- ratio long/short de cuentas (si disponible)
);
CREATE INDEX IF NOT EXISTS idx_volume_exchange_symbol_ts
    ON liquidity_volume (exchange, symbol, timestamp DESC);

-- ── Snapshots de capitalización de mercado (cada 12h) ────────────────────────
CREATE TABLE IF NOT EXISTS liquidity_market (
    id                  SERIAL PRIMARY KEY,
    timestamp           TEXT NOT NULL,
    symbol_base         TEXT NOT NULL,      -- 'APT', 'AAVE', etc.
    coingecko_id        TEXT NOT NULL,      -- 'aptos', 'aave'
    market_cap_usdt     DOUBLE PRECISION,
    circulating_supply  DOUBLE PRECISION,
    price_usd           DOUBLE PRECISION,
    price_change_24h_pct DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_market_symbol_ts
    ON liquidity_market (symbol_base, timestamp DESC);

-- ── Recomendaciones calculadas (vista materializada, actualizada cada 9min) ──
CREATE TABLE IF NOT EXISTS liquidity_recommendations (
    id                          SERIAL PRIMARY KEY,
    timestamp                   TEXT NOT NULL,
    exchange                    TEXT NOT NULL,
    symbol                      TEXT NOT NULL,
    leverage                    INTEGER NOT NULL,
    -- Los tres techos
    max_notional_book_depth     DOUBLE PRECISION,  -- Techo 1
    max_notional_volume_rule    DOUBLE PRECISION,  -- Techo 2 (1% vol 24h)
    max_notional_oi_rule        DOUBLE PRECISION,  -- Techo 3 (0.5%/leverage * OI)
    -- Resultado
    recommended_max_notional    DOUBLE PRECISION,
    limiting_factor             TEXT,              -- 'book_depth'|'volume_24h'|'open_interest'
    slippage_threshold_pct      DOUBLE PRECISION,  -- umbral calculado dinámicamente
    -- Contexto
    mid_price                   DOUBLE PRECISION,
    market_cap_usdt             DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_rec_exchange_symbol_ts
    ON liquidity_recommendations (exchange, symbol, timestamp DESC);

-- ── Vista para lectura fácil desde occ-trader-multi ─────────────────────────
CREATE OR REPLACE VIEW liquidity_current AS
SELECT DISTINCT ON (exchange, symbol)
    exchange,
    symbol,
    timestamp,
    recommended_max_notional,
    limiting_factor,
    slippage_threshold_pct,
    max_notional_book_depth,
    max_notional_volume_rule,
    max_notional_oi_rule,
    mid_price,
    leverage
FROM liquidity_recommendations
ORDER BY exchange, symbol, timestamp DESC;

-- ── Permisos para occ_reader (dashboard read-only) ───────────────────────────
GRANT SELECT ON liquidity_pairs TO occ_reader;
GRANT SELECT ON liquidity_depth TO occ_reader;
GRANT SELECT ON liquidity_volume TO occ_reader;
GRANT SELECT ON liquidity_market TO occ_reader;
GRANT SELECT ON liquidity_recommendations TO occ_reader;
GRANT SELECT ON liquidity_current TO occ_reader;

-- ── Datos iniciales: pares a monitorear ──────────────────────────────────────
INSERT INTO liquidity_pairs (exchange, symbol, symbol_raw, market_type, enabled, leverage, created_at)
VALUES
    ('binance', 'APT/USDT', 'APTUSDT', 'future', true, 3, NOW()::text),
    ('binance', 'AAVE/USDT', 'AAVEUSDT', 'future', false, 3, NOW()::text)
ON CONFLICT (exchange, symbol) DO NOTHING;
