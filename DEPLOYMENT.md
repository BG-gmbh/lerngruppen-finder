# Deployment Guide

```
group-ly.tech        -> Cloudflare Pages   (static site, flutter_app/docs)
api.group-ly.tech    -> Render             (Docker: gunicorn/Flask)
                          └─ MongoDB Atlas  (app data)
```

The Flask app is stateless (all data lives in MongoDB Atlas), so the backend is
a plain Docker web service with no persistent disk.

## Database: MongoDB Atlas

1. Create a free (M0) cluster at https://cloud.mongodb.com.
2. **Database Access** → add a user + password.
3. **Network Access** → allow `0.0.0.0/0` (Render egress IPs vary; use a strong
   password), or add Render's static outbound IPs if you pin them.
4. **Connect → Drivers → Python** → copy the URI (`mongodb+srv://…`).
5. One-time data import from the old SQLite DB:
   ```bash
   MONGODB_URI="mongodb+srv://…" MONGODB_DB=grouply \
       python migrate_sqlite_to_mongo.py users.db
   ```
   Remaps integer ids to ObjectIds and rewrites all foreign keys. Refuses to run
   over non-empty collections unless you pass `--force`.

Indexes are created automatically on app startup (`init_db()` → `ensure_indexes()`).

## Backend: Render (`api.group-ly.tech`)

Render builds the existing `Dockerfile` (gunicorn on `$PORT`). Config is in
`render.yaml`; secrets are set in the Render dashboard (never in the repo).

Environment variables (Render → service → Environment):
- `MONGODB_URI` — the Atlas connection string  ⚠️ required
- `MONGODB_DB` — `grouply` (already defaulted in render.yaml)
- `FLASK_SECRET_KEY` — Render can generate it (render.yaml `generateValue`)
- `SESSION_COOKIE_SECURE=1`, `SESSION_COOKIE_DOMAIN=.group-ly.tech`
- `FLASK_ALLOWED_ORIGINS=https://group-ly.tech,https://www.group-ly.tech`
- `OPENAI_API_KEY`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`

Render auto-deploys on push (`autoDeploy: true`). The optional
`.github/workflows/backend-deploy.yml` also pokes the Render deploy API
(`RENDER_API_KEY` + `RENDER_SERVICE_ID` secrets).

Point `api.group-ly.tech` at the Render service (Render dashboard → Custom
Domains → add `api.group-ly.tech`, then create the DNS record).

## Frontend: Cloudflare Pages (`group-ly.tech`)

Static site = `flutter_app/docs`. Deploy via
`.github/workflows/pages-deploy.yml` (`wrangler pages deploy flutter_app/docs`)
or a Pages project connected to the repo.

- Create a Pages project named `lerngruppen-finder`.
- Add custom domain `group-ly.tech`.
- `flutter_app/docs/js/config.js` auto-targets `https://api.group-ly.tech` in
  production and stays same-origin on localhost.

## Cross-subdomain login

Site and API are different subdomains, so the Flask session cookie is issued
`SameSite=None; Secure; Domain=.group-ly.tech` (via the `SESSION_COOKIE_*` env
vars) and CORS sends `Access-Control-Allow-Credentials: true`. Frontend fetches
use `credentials: "include"`.

⚠️ If `api.group-ly.tech` is proxied through Cloudflare (orange cloud), turn OFF
**Bot Fight Mode** (Security → Bots) for the zone, or add a WAF rule to skip the
Managed Challenge for `api.group-ly.tech` — otherwise API/`fetch` calls get the
"Just a moment…" challenge instead of your JSON.

## Local development

```bash
pip install -r requirements.txt
# needs a MongoDB — local mongod or an Atlas dev cluster
MONGODB_URI="mongodb://localhost:27017" MONGODB_DB=grouply python app.py
```
Do NOT set `SESSION_COOKIE_*` locally (they force Secure cookies, which browsers
drop over http://localhost).
