# Deployment Guide

Everything runs on **Cloudflare**; data lives in **MongoDB Atlas**.

```
group-ly.tech        -> Cloudflare Pages     (static site, flutter_app/docs)
api.group-ly.tech    -> Cloudflare Worker    (worker/index.js)
                          └─ Cloudflare Container (Dockerfile: gunicorn/Flask)
                               └─ MongoDB Atlas (app data)
```

## Database: MongoDB Atlas

1. Create a free (M0) cluster at https://cloud.mongodb.com.
2. Create a DB user and copy the Python connection string (`mongodb+srv://…`).
3. Network access: allow Cloudflare egress (simplest: `0.0.0.0/0` with a strong
   password, or configure specific ranges / PrivateLink).
4. One-time data import from the old SQLite DB:
   ```bash
   MONGODB_URI="mongodb+srv://…" MONGODB_DB=grouply \
       python migrate_sqlite_to_mongo.py users.db
   ```
   The script remaps every integer id to a MongoDB `ObjectId` and rewrites all
   foreign-key references. It refuses to run over non-empty collections unless
   you pass `--force`.

Indexes are created automatically on app startup (`init_db()` → `ensure_indexes()`).

## Backend: Cloudflare Containers (`api.group-ly.tech`)

Config: `wrangler.jsonc` (Worker + Container), `worker/index.js` (routes traffic
to the container), `Dockerfile` (gunicorn/Flask on port 8080), `package.json`.

Set secrets once (not stored in the repo):
```bash
npx wrangler secret put MONGODB_URI
npx wrangler secret put FLASK_SECRET_KEY
npx wrangler secret put OPENAI_API_KEY
npx wrangler secret put SMTP_HOST
npx wrangler secret put SMTP_PORT
npx wrangler secret put SMTP_USER
npx wrangler secret put SMTP_PASSWORD
npx wrangler secret put SMTP_FROM
```
Non-secret defaults (`MONGODB_DB`, `SESSION_COOKIE_*`, `FLASK_ALLOWED_ORIGINS`)
are in `wrangler.jsonc` under `vars`.

Deploy:
```bash
npm install
npx wrangler deploy
```
CI: `.github/workflows/backend-deploy.yml` runs `wrangler deploy` on push to
`main` using the `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` secrets.

Add the custom domain `api.group-ly.tech` to the Worker (Cloudflare dashboard →
Workers → Triggers/Custom Domains, or a route).

## Frontend: Cloudflare Pages (`group-ly.tech`)

The static site is `flutter_app/docs`. CI: `.github/workflows/pages-deploy.yml`
runs `wrangler pages deploy flutter_app/docs` on push to `main`.

- Create a Pages project named `lerngruppen-finder`.
- Add the custom domain `group-ly.tech` on the Pages project.
- `flutter_app/docs/js/config.js` auto-points the frontend at
  `https://api.group-ly.tech` in production and stays same-origin on localhost.

## Cross-subdomain login

Because the site and API are on different subdomains, the Flask session cookie is
issued with `SameSite=None; Secure; Domain=.group-ly.tech` (enabled by
`SESSION_COOKIE_SECURE=1` + `SESSION_COOKIE_DOMAIN=.group-ly.tech` in the
container env) and CORS sends `Access-Control-Allow-Credentials: true`. Frontend
fetches use `credentials: "include"`.

## DNS

- `group-ly.tech` → Cloudflare Pages
- `api.group-ly.tech` → Cloudflare Worker

## Local development

```bash
pip install -r requirements.txt
# needs a MongoDB — either a local mongod or an Atlas dev cluster
MONGODB_URI="mongodb://localhost:27017" MONGODB_DB=grouply python app.py
```
Do NOT set the `SESSION_COOKIE_*` vars locally (they force Secure cookies, which
browsers drop over http://localhost).
