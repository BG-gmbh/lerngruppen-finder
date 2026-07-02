# lerngruppen finder

**Normale Webseiten** (HTML/CSS/JS) im Ordner `docs/` — Start, Login, Registrierung, Dashboard. Damit Konten und Passwörter sicher bleiben, läuft dazu ein kleiner **Python-Server** (`app.py`), der nur Formulare, Session und die Datenbank übernimmt.

| Pfad | Inhalt |
|------|--------|
| `docs/index.html` | Startseite |
| `docs/login.html` | Login-Formular |
| `docs/register.html` | Registrierung |
| `docs/dashboard.html` | Bereich nach Login (wird nur ausgeliefert, wenn du eingeloggt bist) |

Die Seiten kannst du im Editor bearbeiten wie jede andere Website. **Nicht** nur die HTML-Dateien auf einen rein statischen Webspace legen, wenn du Login brauchst — dann ginge die Anmeldung nicht. Auf dem Pi: Server starten, im Browser die URLs öffnen (siehe unten).

## Schnellstart: Web-App starten

Einmalig installieren:

```bash
cd /Users/admin/benjamin/lerngruppen-finder
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Danach starten:

```bash
cd /Users/admin/benjamin/lerngruppen-finder
source venv/bin/activate
python app.py
```

Öffnen:

- Lokal: `http://127.0.0.1:5000/`
- Im WLAN: `http://<SERVER-IP>:5000/`

## Schnellstart: Flutter-App starten

Zuerst Backend starten:

```bash
cd /Users/admin/benjamin/lerngruppen-finder
source venv/bin/activate
python app.py
```

Dann Flutter Web starten:

```bash
cd /Users/admin/benjamin/lerngruppen-finder/flutter_app
flutter pub get
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:5000
```

Im Netzwerk erreichbar (nicht nur localhost):

```bash
cd /Users/admin/benjamin/lerngruppen-finder/flutter_app
flutter pub get
flutter run -d web-server --web-hostname group-ly.tech --web-port 8080 --dart-define=API_BASE_URL=http://127.0.0.1:5000
```

Android-Emulator:

```bash
cd /Users/admin/benjamin/lerngruppen-finder/flutter_app
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:5000
```

Echtes Handy im gleichen WLAN:

```bash
cd /Users/admin/benjamin/lerngruppen-finder/flutter_app
flutter pub get
flutter run --dart-define=API_BASE_URL=http://<SERVER-IP>:5000
```

Native Plattformordner ergänzen, falls Flutter sie braucht:

```bash
cd /Users/admin/benjamin/lerngruppen-finder/flutter_app
flutter create --platforms=android,ios,web .
```

Flutter prüfen:

```bash
flutter doctor
flutter --version
```

Hinweis: Der vorhandene Flutter-SDK-Pfad auf diesem Mac meldet, dass diese
Flutter-Version mindestens macOS 14 braucht. Auf macOS 13 entweder Flutter auf
eine kompatible Version wechseln oder auf einem neueren System ausführen.

## Auf dem Raspberry Pi hosten

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
cd lerngruppen-finder
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# In .env mindestens FLASK_SECRET_KEY setzen; für Laden-E-Mails die SMTP_*-Variablen.
python3 app.py
```

- Auf dem Pi: `http://127.0.0.1:5000/` → zeigt `docs/index.html`
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
| `FLASK_ALLOWED_ORIGINS` | Kommagetrennte erlaubte Web-Origins fuer CORS, z. B. `https://app.example.com` |

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

#### Gmail

1. Im Google-Konto **Zwei-Faktor-Authentifizierung** aktivieren.
2. Unter [App-Passwörter](https://myaccount.google.com/apppasswords) ein Passwort für „Mail“ erzeugen (16 Zeichen, Leerzeichen beim Einfügen weglassen).
3. In `.env` (siehe **`.env.example`**): `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER` und `SMTP_FROM` = deine Gmail-Adresse, `SMTP_PASSWORD` = **nur** das App-Passwort (nie das normale Anmeldepasswort).
4. Server neu starten, damit `.env` geladen wird.

**Workspace (eigene Domain):** gleicher Host `smtp.gmail.com`, `SMTP_USER` / `SMTP_FROM` = deine `@schule.de`-Adresse, ebenfalls App-Passwort falls von der Organisation erlaubt.

Empfänger sind in der Admin-Oberfläche hinterlegte **Lehrer-Kontakte** plus Nutzer mit **Laden-E-Mail-Benachrichtigung** in den Einstellungen.

### Mail-Server Schnellanleitung (5 Minuten)

1. Datei `.env` anlegen (falls noch nicht da):  
   `cp .env.example .env`
2. In `.env` folgende Werte setzen (Beispiel Gmail mit STARTTLS/587):
   - `SMTP_HOST=smtp.gmail.com`
   - `SMTP_PORT=587`
   - `SMTP_USER=deine.adresse@gmail.com`
   - `SMTP_PASSWORD=<dein-app-passwort>`
   - `SMTP_FROM=deine.adresse@gmail.com`
3. Server neu starten:
   - laufenden Prozess stoppen (`CTRL+C`)
   - neu starten mit `python3 app.py` (oder venv: `python app.py`)
4. In `Admin -> Lehrer (E-Mail)` mindestens eine Lehrer-Adresse eintragen.
5. Test: Einen Punkte-Kauf im Laden auslösen.  
   Im Admin-Tab `Laden` im Protokoll muss danach bei E-Mail entweder **gesendet** stehen oder eine konkrete Fehlermeldung.

#### Typische Fehlerbilder

- `smtp_not_configured`: `SMTP_HOST` fehlt oder ist leer.
- `smtp_no_from`: `SMTP_FROM` und `SMTP_USER` sind leer.
- Auth-Fehler (z. B. `535`): meist falsches Passwort oder kein App-Passwort.
- Timeout/Verbindungsfehler: Port/Firewall/Provider blockiert SMTP.

Benutzer liegen in `users.db` (SQLite).
