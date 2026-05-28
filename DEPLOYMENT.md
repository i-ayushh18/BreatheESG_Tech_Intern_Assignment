# Deployment Notes

The assignment requires a live deployed app. This repo is now ready for a typical two-service deployment:

- Backend: Django service from `backend/`
- Frontend: static React build from `frontend/`
- Database: PostgreSQL using `DATABASE_URL`

## Backend

Build command:

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

Start command:

```bash
gunicorn backend.wsgi --log-file -
```

Required environment variables:

```text
DEBUG=False
SECRET_KEY=<generated secret>
DATABASE_URL=<postgres connection string>
ALLOWED_HOSTS=<backend-hostname>
CORS_ALLOWED_ORIGINS=<frontend-url>
CSRF_TRUSTED_ORIGINS=<frontend-url>
```

Run once after deploy:

```bash
python manage.py migrate
python manage.py populate_reference_data
```

## Frontend

Build command:

```bash
npm ci && npm run build
```

Environment variable:

```text
REACT_APP_API_BASE_URL=https://<backend-hostname>/api
```
