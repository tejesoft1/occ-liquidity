-- insert_pairs.sql
-- Insertar todos los pares a monitorear en Binance Futures.
-- APT y AAVE ya existen, los demás se agregan.
-- Leverages por grupo:
--   5x: BTC, ETH (mayor liquidez, menor volatilidad relativa)
--   3x: SOL, AVAX, ADA, APT, AAVE, ARB, LTC

-- Actualizar AAVE (ya existe, habilitar)
UPDATE liquidity_pairs SET enabled=true, leverage=3
WHERE symbol='AAVE/USDT' AND exchange='binance';

-- Actualizar APT (ya existe, confirmar leverage)
UPDATE liquidity_pairs SET enabled=true, leverage=3
WHERE symbol='APT/USDT' AND exchange='binance';

-- Agregar los nuevos
INSERT INTO liquidity_pairs (exchange, symbol, symbol_raw, market_type, enabled, leverage, created_at)
VALUES
    ('binance', 'BTC/USDT',  'BTCUSDT',  'future', true, 5, NOW()::text),
    ('binance', 'ETH/USDT',  'ETHUSDT',  'future', true, 5, NOW()::text),
    ('binance', 'SOL/USDT',  'SOLUSDT',  'future', true, 3, NOW()::text),
    ('binance', 'ADA/USDT',  'ADAUSDT',  'future', true, 3, NOW()::text),
    ('binance', 'LTC/USDT',  'LTCUSDT',  'future', true, 3, NOW()::text),
    ('binance', 'ARB/USDT',  'ARBUSDT',  'future', true, 3, NOW()::text),
    ('binance', 'AVAX/USDT', 'AVAXUSDT', 'future', true, 3, NOW()::text)
ON CONFLICT (exchange, symbol) DO NOTHING;

-- Verificar resultado final
SELECT exchange, symbol, enabled, leverage FROM liquidity_pairs ORDER BY leverage DESC, symbol;


-- ── BYBIT ─────────────────────────────────────────────────────────────────────
INSERT INTO liquidity_pairs (exchange, symbol, symbol_raw, market_type, enabled, leverage, created_at)
VALUES
    ('bybit', 'BTC/USDT',  'BTCUSDT',  'future', true, 5, NOW()::text),
    ('bybit', 'ETH/USDT',  'ETHUSDT',  'future', true, 5, NOW()::text),
    ('bybit', 'SOL/USDT',  'SOLUSDT',  'future', true, 3, NOW()::text),
    ('bybit', 'ADA/USDT',  'ADAUSDT',  'future', true, 3, NOW()::text),
    ('bybit', 'AVAX/USDT', 'AVAXUSDT', 'future', true, 3, NOW()::text),
    ('bybit', 'APT/USDT',  'APTUSDT',  'future', true, 3, NOW()::text),
    ('bybit', 'AAVE/USDT', 'AAVEUSDT', 'future', true, 3, NOW()::text),
    ('bybit', 'LTC/USDT',  'LTCUSDT',  'future', true, 3, NOW()::text)
ON CONFLICT (exchange, symbol) DO NOTHING;

-- ── BINGX ─────────────────────────────────────────────────────────────────────
INSERT INTO liquidity_pairs (exchange, symbol, symbol_raw, market_type, enabled, leverage, created_at)
VALUES
    ('bingx', 'BTC/USDT',  'BTC-USDT',  'swap', true, 5, NOW()::text),
    ('bingx', 'ETH/USDT',  'ETH-USDT',  'swap', true, 5, NOW()::text),
    ('bingx', 'SOL/USDT',  'SOL-USDT',  'swap', true, 3, NOW()::text),
    ('bingx', 'ADA/USDT',  'ADA-USDT',  'swap', true, 3, NOW()::text),
    ('bingx', 'AVAX/USDT', 'AVAX-USDT', 'swap', true, 3, NOW()::text),
    ('bingx', 'APT/USDT',  'APT-USDT',  'swap', true, 3, NOW()::text),
    ('bingx', 'AAVE/USDT', 'AAVE-USDT', 'swap', true, 3, NOW()::text),
    ('bingx', 'LTC/USDT',  'LTC-USDT',  'swap', true, 3, NOW()::text)
ON CONFLICT (exchange, symbol) DO NOTHING;
