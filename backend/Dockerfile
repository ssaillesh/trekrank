FROM python:3.12-slim

# psycopg2 + GeoAlchemy/PostGIS client + Pillow build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

EXPOSE 8000
# Runs migrations + badge seed, then starts uvicorn on $PORT (8000 local).
CMD ["./start.sh"]
