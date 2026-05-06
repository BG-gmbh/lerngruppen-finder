# lerngruppen finder

**Normale Webseiten** (HTML/CSS/JS) im Ordner `web/` — Start, Login, Registrierung, Dashboard. Damit Konten und Passwörter sicher bleiben, läuft dazu ein kleiner **Python-Server** (`app.py`), der nur Formulare, Session und die Datenbank übernimmt.

| Pfad | Inhalt |
|------|--------|
| `web/index.html` | Startseite |
| `web/login.html` | Login-Formular |
| `web/register.html` | Registrierung |
| `web/dashboard.html` | Bereich nach Login (wird nur ausgeliefert, wenn du eingeloggt bist) |

Die Seiten kannst du im Editor bearbeiten wie jede andere Website. **Nicht** nur die HTML-Dateien auf einen rein statischen Webspace legen, wenn du Login brauchst — dann ginge die Anmeldung nicht. Auf dem Pi: Server starten, im Browser die URLs öffnen (siehe unten).

## Auf dem Raspberry Pi hosten

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
cd schul-tinder
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# In .env mindestens FLASK_SECRET_KEY setzen; für Laden-E-Mails die SMTP_*-Variablen.
python3 app.py
```

- Auf dem Pi: `http://127.0.0.1:5000/` → zeigt `web/index.html`
- Im WLAN: `http://<PI-IP>:5000/` (IP z. B. mit `hostname -I`)

Der Server bindet an `0.0.0.0`, damit andere Geräte zugreifen können.

## Konfiguration (optional)

Werte in einer Datei **`.env`** im Projektordner (Vorlage: **`.env.example`**). Beim Start lädt `app.py` sie automatisch (`python-dotenv`).

| Umgebungsvariable   | Bedeutung |
|--------------------|-----------|
| `FLASK_SECRET_KEY` | Pflicht sinnvoll ab „mehr als nur ich“ — sicherer Session-Schlüssel |
| `FLASK_HOST`       | Standard: `0.0.0.0` |
| `FLASK_PORT`       | Standard: `5000` |
| `FLASK_DEBUG`      | `true` nur zum Entwickeln |

### SMTP (Lehrer-Benachrichtigung bei Laden-Käufen)

| Variable | Bedeutung |
|----------|-----------|
| `SMTP_HOST` | Server, z. B. `smtp.gmail.com` — ohne Eintrag wird keine Mail gesendet |
| `SMTP_PORT` | Standard `587` (STARTTLS) |
| `SMTP_USER` / `SMTP_PASSWORD` | Anmeldung beim Provider (bei Gmail oft **App-Passwort**) |
| `SMTP_FROM` | Absender; leer = wie `SMTP_USER` |
| `SMTP_USE_SSL` | `1` für **SMTP_SSL**, typisch mit Port **465** |
| `SMTP_STARTTLS` | `0` deaktiviert STARTTLS (nur bei Bedarf) |
| `SMTP_TIMEOUT` | Sekunden (Standard 30) |

Empfänger sind in der Admin-Oberfläche hinterlegte **Lehrer-Kontakte** plus Nutzer mit **Laden-E-Mail-Benachrichtigung** in den Einstellungen.

Benutzer liegen in `users.db` (SQLite).
