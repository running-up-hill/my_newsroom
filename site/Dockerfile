FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    NEWS_DB=/data/news.db \
    SITE_OUT=/out \
    SITE_INTERVAL=300

WORKDIR /app

# Standard library only, so there is no pip step
COPY site/build_site.py site/build_site.py

# Rebuild the page every 5 minutes; it only rewrites the file when a digest has changed
CMD ["sh", "-c", "while true; do python site/build_site.py; sleep ${SITE_INTERVAL}; done"]
