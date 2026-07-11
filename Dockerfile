FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
ENV PORT=8080
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# --preload: App wird einmalig im Master importiert -> seed_db_if_empty()/init_db()
# laufen genau einmal, bevor die Worker geforkt werden. Ohne --preload wuerde jeder
# Worker die DB-Migration parallel ausfuehren -> SQLite "disk I/O error" /
# "attempt to write a readonly database" auf der /data-Disk.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} app:app --workers 2 --preload"]
