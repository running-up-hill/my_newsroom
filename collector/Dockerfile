FROM python:3.12-slim

# Show print() output in `docker compose logs` straight away
ENV PYTHONUNBUFFERED=1 \
    NEWS_DB=/data/news.db \
    INTERVAL_SECONDS=14400

WORKDIR /app

# Install dependencies first: this layer is cached until requirements.txt changes
COPY collector/requirements.txt collector/requirements.txt
RUN pip install --no-cache-dir -r collector/requirements.txt

# Then copy the code, schema and starter data
COPY collector/collect.py collector/collect.py
COPY schema.sql schema.sql
COPY config/ config/

# Run once, sleep, repeat (default every 4 hours)
CMD ["sh", "-c", "while true; do python collector/collect.py; sleep ${INTERVAL_SECONDS}; done"]
