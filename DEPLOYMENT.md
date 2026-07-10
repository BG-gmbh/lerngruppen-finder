# Deployment Guide

## Frontend: GitHub Pages

The static frontend is published from the folder `flutter_app/docs`.

### GitHub settings
- Repository Settings → Pages
- Source: GitHub Actions
- Custom domain: `group-ly.tech`

### Workflow
The workflow at `.github/workflows/github-pages.yml` builds and deploys the static site automatically on pushes to `main`.

## Backend: Render

The Flask app is ready to run with the existing Dockerfile.

### Render setup
1. Create a new Web Service on Render.
2. Connect this repository.
3. Choose the existing Dockerfile.
4. Set the start command to:
   ```bash
   gunicorn --bind 0.0.0.0:${PORT} app:app --workers 2
   ```
5. Set the environment variables:
   - `FLASK_SECRET_KEY=<random-secret>`
   - `FLASK_ALLOWED_ORIGINS=https://group-ly.tech,https://www.group-ly.tech`
   - `FLASK_HOST=0.0.0.0`
   - `FLASK_PORT=8080`

### Backend URL
The frontend default API base is configured in `flutter_app/docs/config.js` as:
- `https://api.group-ly.tech`

If your Render hostname differs, update that value.

## DNS
Create or update the DNS records so:
- `group-ly.tech` → GitHub Pages
- `api.group-ly.tech` → Render backend
