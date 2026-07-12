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

# Kein --preload: jeder Worker importiert die App nach dem Fork und legt seinen
# EIGENEN MongoClient an -> fork-sicher (ein im Master erzeugter Client waere es
# nicht). init_db() (Index-Anlegen) laeuft dadurch pro Worker, ist aber idempotent.
# Der Datenbank-Zustand liegt extern in MongoDB Atlas; der Container ist zustandslos.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} app:app --workers 2"]
