# Breathe ESG Tech Intern Assignment

This is a Django REST + React prototype for the Breathe ESG intern assignment. It ingests three messy source types, stores the original rows, normalizes activity data into kg CO2e, and gives an analyst a review table for flagged/approved/locked records.

The code is intentionally small. The goal is to show the data model and ingestion decisions clearly, not to build a production carbon platform in four days.

## What It Handles

- SAP S/4HANA Material Document OData JSON for Scope 1 fuel emissions
- Utility electricity CSV exports for Scope 2 electricity emissions
- SAP Concur Itinerary v4 JSON for Scope 3 flights, hotels, and ground transport
- Immutable raw row storage for audit traceability
- Normalized records with activity value, unit, emission factor, CO2e, scope, period, and review status
- Automatic quality flags for outliers, unit changes, impossible flight distances, and negative values
- Analyst actions: approve, flag, bulk approve, lock, and view audit log

## Project Layout

```text
backend/
  manage.py
  backend/
    settings.py
    urls.py
    wsgi.py
    asgi.py
  core/
    models.py                 # database shape
    parsers.py                # source-specific row parsing
    normalizers.py            # unit conversion and CO2e calculation
    quality_checks.py         # review flags
    serializers.py            # API response shapes
    views.py                  # upload and review endpoints
    management/commands/
      populate_reference_data.py

frontend/
  src/
    api.ts
    App.tsx
    components/
      FileUpload.tsx
      RecordsTable.tsx

sample_data/
  sap_material_document_odata_jan2024.json
  utility_electricity_q1_2024.csv
  concur_itinerary_jan2024.json
```

## Local Setup

Backend:

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py populate_reference_data
python manage.py runserver
```

Frontend:

```bash
cd frontend
npm install
npm start
```

The frontend expects the API at `http://localhost:8000/api` by default. For deployment, set:

```text
REACT_APP_API_BASE_URL=https://<backend-host>/api
```

## Useful Commands

```bash
cd backend
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

```bash
cd frontend
npm run build
```

## Main API Endpoints

```text
POST /api/ingest/
GET  /api/records/
POST /api/records/{id}/approve/
POST /api/records/{id}/flag/
POST /api/records/{id}/lock/
GET  /api/records/{id}/audit_log/
GET  /api/raw-records/?invalid_only=true
GET  /api/ingestions/
```

## Data Model Summary

`RawRecord` and `NormalizedRecord` are deliberately separate.

- `RawRecord` stores the uploaded source row exactly as parsed.
- `NormalizedRecord` stores the cleaned activity value, standard unit, emission factor, CO2e, scope, period, and analyst workflow status.
- `DataIngestion` tracks the file upload job.
- `DataQualityFlag` stores automated review flags.
- `AuditLog` records analyst state changes.

See [MODEL.md](MODEL.md), [DECISIONS.md](DECISIONS.md), [TRADEOFFS.md](TRADEOFFS.md), and [SOURCES.md](SOURCES.md) for the reasoning behind the choices.

## Current Tradeoffs

- Uploads are synchronous; large files should move to a background queue.
- Local development uses SQLite; deployed environments should use PostgreSQL through `DATABASE_URL`.
- Authentication is not implemented. The data model keeps `uploaded_by` and `approved_by` fields so auth can be added later.
- Some reference data is intentionally small: limited airport coordinates, simple ground-distance estimation, and fixed 2023 emission factors.

## Deployment

The assignment requires a live deployed app. See [DEPLOYMENT.md](DEPLOYMENT.md) for Render/Railway-style backend and frontend settings.
