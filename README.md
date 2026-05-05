# schul-tinder

Kleine Web-App mit **Registrierung** und **Login**. Läuft mit **Python** und **SQLite** — gut geeignet für einen **Raspberry Pi** (ARM, wenig RAM, kein extra Datenbank-Server).

## Auf dem Raspberry Pi starten

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

Im Browser auf dem Pi: `http://127.0.0.1:5000`  
Vom Handy/PC im gleichen WLAN (Pi-IP ermitteln mit `hostname -I`): `http://<PI-IP>:5000`

Der Server bindet standardmäßig an alle Interfaces (`0.0.0.0`), damit du im Netzwerk zugreifen kannst.

## Konfiguration (optional)

| Umgebungsvariable   | Bedeutung                          |
|--------------------|-------------------------------------|
| `FLASK_SECRET_KEY` | Geheimer Schlüssel für Sessions (in Produktion setzen!) |
| `FLASK_HOST`       | Standard: `0.0.0.0`                 |
| `FLASK_PORT`       | Standard: `5000`                    |
| `FLASK_DEBUG`      | `true` nur zum Entwickeln           |

Benutzer werden in `users.db` (SQLite) gespeichert.
