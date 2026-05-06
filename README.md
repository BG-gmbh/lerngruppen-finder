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
export FLASK_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
python3 app.py
```

- Auf dem Pi: `http://127.0.0.1:5000/` → zeigt `web/index.html`
- Im WLAN: `http://<PI-IP>:5000/` (IP z. B. mit `hostname -I`)

Der Server bindet an `0.0.0.0`, damit andere Geräte zugreifen können.

## Konfiguration (optional)

| Umgebungsvariable   | Bedeutung |
|--------------------|-----------|
| `FLASK_SECRET_KEY` | Pflicht sinnvoll ab „mehr als nur ich“ — sicherer Session-Schlüssel |
| `FLASK_HOST`       | Standard: `0.0.0.0` |
| `FLASK_PORT`       | Standard: `5000` |
| `FLASK_DEBUG`      | `true` nur zum Entwickeln |

Benutzer liegen in `users.db` (SQLite).
