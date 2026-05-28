# Deployment (local / prototype)

This repository includes a minimal Docker-based deployment for running the
prototype locally (Postgres, Django backend, built frontend served by nginx).

Quick start (requires Docker & Docker Compose):

```bash
# build images
docker compose build

# create .env with DB config (example in .env.example)
docker compose up
```

Notes:
- The backend reads environment variables from `.env`. Ensure `DATABASE_URL`
  or the standard `POSTGRES_*` variables are set.
- This setup is intended for local testing and lightweight demos only. For
  production you should use a managed Postgres instance, a proper secrets
  store, TLS termination, and a CI pipeline that builds and scans images.

What I added:
- `backend/Dockerfile` — builds the Django app and runs `gunicorn`.
- `frontend/Dockerfile` — builds the React app and serves it with nginx.
- `docker-compose.yml` — lightweight dev/prototype compose file.

Render deployment:
- `render.yaml` — manifest for Render to auto-create a backend web service
  (Docker) and a frontend static site. You can deploy directly from GitHub by
  connecting this repository in the Render dashboard.

Render quick steps:
1. Sign in to Render and create a new Web Service.
   - For the backend choose "Docker" and point to `backend/Dockerfile`.
   - Set `SECRET_KEY` and `DATABASE_URL` (Render offers a managed Postgres you
     can provision and then copy its `DATABASE_URL` here).
2. Create a new Static Site in Render for the frontend.
   - Set build command: `cd frontend && npm ci && npm run build`
   - Set publish directory: `frontend/build`
3. (Alternative) Use the provided `render.yaml` manifest: in Render choose
   "New from repo" and Render will attempt to apply the manifest automatically.

Notes on secrets and DB:
- Do not commit secret values into the repo. Use Render's dashboard to set
  environment variables securely.
- After provisioning the managed Postgres on Render, copy the `DATABASE_URL`
  into the backend service environment so Django connects to the managed DB.


Next recommended steps before publishing:
- Add `ALLOWED_HOSTS`, secret management, and a production-ready settings
  configuration for Django.
- Add a CI pipeline (GitHub Actions) that runs linting, tests, and builds images.
- Replace local Postgres with a managed DB for production.
