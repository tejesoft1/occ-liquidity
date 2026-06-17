
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config_liquidity.py database_liquidity.py liquidity_service.py app_liquidity.py gunicorn_conf.py ./
EXPOSE 5000
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app_liquidity:app"]