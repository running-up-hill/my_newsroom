FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    NEWS_DB=/data/news.db

WORKDIR /app

# Dependencies first so this layer is cached until requirements.txt changes
COPY mcp_server/requirements.txt mcp_server/requirements.txt
RUN pip install --no-cache-dir -r mcp_server/requirements.txt

COPY mcp_server/server.py mcp_server/server.py

# Claude launches this with `docker run -i`, talking to it over stdin/stdout
CMD ["python", "mcp_server/server.py"]
