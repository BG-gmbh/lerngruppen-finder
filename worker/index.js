// Cloudflare Worker + Container wrapper for the Flask backend.
//
// The Worker is a thin front door: every incoming request to api.group-ly.tech
// is forwarded to a single Container instance running the gunicorn/Flask app
// (see ../Dockerfile). State lives in MongoDB Atlas, so the container is
// stateless and can be scaled/replaced freely.
import { Container, getContainer } from "@cloudflare/containers";

export class Backend extends Container {
  // gunicorn binds 0.0.0.0:8080 (Dockerfile). Must match the port the app
  // listens on inside the container.
  defaultPort = 8080;
  // Keep a warm instance for a while to avoid cold starts between requests,
  // then let it sleep to save resources.
  sleepAfter = "30m";

  constructor(ctx, env, options) {
    super(ctx, env, options);
    // WICHTIG: Worker-Secrets/Vars werden NICHT automatisch in den Container
    // gereicht. Wir uebergeben alle string-wertigen env-Eintraege (MONGODB_URI,
    // FLASK_SECRET_KEY, OPENAI_API_KEY, SMTP_*, SESSION_COOKIE_*,
    // FLASK_ALLOWED_ORIGINS, MONGODB_DB, ...) als Prozess-Umgebung an gunicorn.
    // Nicht-String-Bindings (z. B. das Durable-Object-Binding BACKEND) werden
    // ausgefiltert.
    this.envVars = Object.fromEntries(
      Object.entries(env).filter(([, value]) => typeof value === "string")
    );
  }
}

export default {
  async fetch(request, env) {
    // Route all traffic to the backend container. A fixed instance name keeps
    // requests sticky to one warm instance (fine because sessions are
    // cookie-based and all persistence is external in Atlas).
    return getContainer(env.BACKEND, "backend").fetch(request);
  },
};
