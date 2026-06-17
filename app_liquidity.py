import logging
from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
import config_liquidity as config
import database_liquidity as db
from liquidity_service import (
    job_update_depth, job_update_volume, job_update_market,
    calculate_slippage_threshold, calculate_recommendation
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# ── CORS ──────────────────────────────────────────────────────────────────────
@app.after_request
def add_cors(resp):
    resp.headers['Access-Control-Allow-Origin']  = config.CORS_ORIGIN
    resp.headers['Access-Control-Allow-Headers'] = 'X-Liquidity-Token, Content-Type'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    return resp


def _check_token():
    if not config.API_TOKEN:
        return True
    sent = request.args.get('token') or request.headers.get('X-Liquidity-Token')
    return sent == config.API_TOKEN


# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler()

# Primeras ejecuciones inmediatas al arrancar (sin esperar el intervalo)
scheduler.add_job(job_update_market, 'interval',
                  seconds=config.INTERVAL_MARKET_SEC,
                  id='market', next_run_time=__import__('datetime').datetime.now())
scheduler.add_job(job_update_volume, 'interval',
                  seconds=config.INTERVAL_VOLUME_SEC,
                  id='volume', next_run_time=__import__('datetime').datetime.now())
scheduler.add_job(job_update_depth,  'interval',
                  seconds=config.INTERVAL_DEPTH_SEC,
                  id='depth',  next_run_time=__import__('datetime').datetime.now())

scheduler.start()
logger.info("Scheduler iniciado: depth=%ds, volume=%ds, market=%ds",
            config.INTERVAL_DEPTH_SEC, config.INTERVAL_VOLUME_SEC,
            config.INTERVAL_MARKET_SEC)


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.route('/api/health')
def health():
    return jsonify({'status': 'up',
                    'depth_interval_sec': config.INTERVAL_DEPTH_SEC}), 200


@app.route('/api/capacity', methods=['GET', 'OPTIONS'])
def capacity():
    """
    Capacidad operativa actual por exchange/par.
    Devuelve la tabla principal del dashboard.
    """
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    if not _check_token():
        return jsonify({'error': 'unauthorized'}), 403

    recs = db.get_current_recommendations()

    # Enriquecer con datos de volumen y mercado
    enriched = []
    for r in recs:
        vol  = db.get_latest_volume(r['exchange'], r['symbol'])
        base = r['symbol'].split('/')[0]
        mkt  = db.get_latest_market(base)

        enriched.append({
            'exchange':                 r['exchange'],
            'symbol':                   r['symbol'],
            'timestamp':                r['timestamp'],
            'mid_price':                r['mid_price'],
            'recommended_max_notional': r['recommended_max_notional'],
            'limiting_factor':          r['limiting_factor'],
            'slippage_threshold_pct':   r['slippage_threshold_pct'],
            'max_notional_book_depth':  r['max_notional_book_depth'],
            'max_notional_volume_rule': r['max_notional_volume_rule'],
            'max_notional_oi_rule':     r['max_notional_oi_rule'],
            'leverage':                 r['leverage'],
            # Volumen
            'volume_24h_usdt':          vol.get('volume_24h_usdt'),
            'open_interest_usdt':       vol.get('open_interest_usdt'),
            'funding_rate':             vol.get('funding_rate'),
            'long_short_ratio':         vol.get('long_short_ratio'),
            # Mercado
            'market_cap_usdt':          mkt.get('market_cap_usdt'),
            'price_change_24h_pct':     mkt.get('price_change_24h_pct'),
        })

    return jsonify({'data': enriched,
                    'slippage_threshold_pct': calculate_slippage_threshold()}), 200


@app.route('/api/depth-history', methods=['GET', 'OPTIONS'])
def depth_history():
    """
    Historial de profundidad del book para el gráfico (pestaña 2).
    ?exchange=binance&symbol=APT/USDT&hours=24
    """
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    if not _check_token():
        return jsonify({'error': 'unauthorized'}), 403

    exchange = request.args.get('exchange', 'binance')
    symbol   = request.args.get('symbol',   'APT/USDT')
    hours    = int(request.args.get('hours', 24))

    history = db.get_depth_history(exchange, symbol, hours)
    return jsonify({'exchange': exchange, 'symbol': symbol,
                    'hours': hours, 'data': history}), 200


@app.route('/api/candidates', methods=['GET', 'OPTIONS'])
def candidates():
    """
    Todos los pares (habilitados y no habilitados) con su capacidad
    calculada — para la pestaña de pares candidatos.
    """
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    if not _check_token():
        return jsonify({'error': 'unauthorized'}), 403

    pairs = db.get_all_pairs()
    result = []
    slippage = calculate_slippage_threshold()

    for p in pairs:
        rec = calculate_recommendation(
            p['exchange'], p['symbol'], p['leverage'], slippage)
        base = p['symbol'].split('/')[0]
        mkt  = db.get_latest_market(base)
        vol  = db.get_latest_volume(p['exchange'], p['symbol'])

        result.append({
            'exchange':                 p['exchange'],
            'symbol':                   p['symbol'],
            'enabled':                  p['enabled'],
            'leverage':                 p['leverage'],
            'recommended_max_notional': rec['recommended'] if rec else None,
            'limiting_factor':          rec['limiting_factor'] if rec else None,
            'volume_24h_usdt':          vol.get('volume_24h_usdt'),
            'open_interest_usdt':       vol.get('open_interest_usdt'),
            'market_cap_usdt':          mkt.get('market_cap_usdt'),
            'price_change_24h_pct':     mkt.get('price_change_24h_pct'),
        })

    # Ordenar por capacidad descendente
    result.sort(key=lambda x: x['recommended_max_notional'] or 0, reverse=True)
    return jsonify({'data': result}), 200


@app.route('/api/refresh', methods=['POST'])
def refresh():
    """Fuerza una actualización inmediata de todos los datos."""
    if not _check_token():
        return jsonify({'error': 'unauthorized'}), 403
    scheduler.modify_job('depth',  next_run_time=__import__('datetime').datetime.now())
    scheduler.modify_job('volume', next_run_time=__import__('datetime').datetime.now())
    return jsonify({'status': 'refresh_triggered'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
