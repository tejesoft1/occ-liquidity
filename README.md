# deploy.md

El dashboard responde una sola pregunta: ¿Cuánto soporta este mercado?
Layout final, limpio:
┌─────────────────────────────────────────────────────────────────────────────┐
│ CAPACIDAD OPERATIVA DE MERCADO                    Actualizado: 14:23  [↺]   │
├──────────────┬────────────┬────────────┬────────────┬──────────┬────────────┤
│ Exchange/Par │ Máx. orden │ Limitante  │ Vol 24h    │ OI       │ Cap. Mdo.  │
├──────────────┼────────────┼────────────┼────────────┼──────────┼────────────┤
│ ▼ BINANCE    │            │            │            │          │            │
│   APT/USDT   │ $43,200    │ Book depth │ $127M      │ $48M     │ $1.48B     │
│   AAVE/USDT  │ $18,500    │ Book depth │ $43M       │ $21M     │ $2.1B      │
├──────────────┼────────────┼────────────┼────────────┼──────────┼────────────┤
│ ▼ BYBIT      │            │            │            │          │            │
│   APT/USDT   │ $38,700    │ Vol 24h    │ $89M       │ $31M     │ $1.48B     │
└──────────────┴────────────┴────────────┴────────────┴──────────┴────────────┘


Tres pestañas:

Capacidad (esta tabla)
Historial de liquidez (gráfico book depth últimas 24h por par/exchange)
Pares candidatos (pares monitoreados no activos, ordenados por liquidez)

Genero todo ahora — SQL, backend, HTML con las 3 pestañas.Se crearon 8 archivosSe crearon 8 archivosAhora el dashboard HTML con las 3 pestañas:Creó un archivo, ejecutó un comando, archivo leídoCreó un archivo, ejecutó un comando, archivo leídoResumen de lo generado:
Backend (occ-liquidity, puerto 5005, red occ-net): 3 schedulers independientes (depth cada 9min, volumen/OI/funding cada 1h, cap de mercado cada 12h), ccxt para multi-exchange, CoinGecko para cap de mercado, 4 tablas en Postgres (liquidity_depth, liquidity_volume, liquidity_market, liquidity_recommendations) más una vista liquidity_current para lectura directa desde otros servicios. 4 endpoints: /api/capacity, /api/depth-history, /api/candidates, /api/refresh.
Dashboard (index.html, GitHub Pages): tabla colapsable por exchange con barras visuales de los 3 techos, badges de factor limitante, historial de profundidad con gráfico de línea, y pestaña de pares candidatos.
Para agregar un exchange nuevo: una línea en liquidity_service.py (get_exchange) y un INSERT en liquidity_pairs. El resto del código es agnóstico al exchange.
Pasos para desplegar cuando el droplet esté listo:

Crear tablas: docker exec -it db psql -U odoo -d occ_trader -f create_liquidity_tables.sql
Crear .env.liquidity desde el ejemplo
docker compose up -d --build
Subir index.html a un repo de GitHub Pages (o al repo occ-trader-dashboard existente en una subcarpeta)

