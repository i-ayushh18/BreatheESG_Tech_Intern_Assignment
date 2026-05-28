# MODEL.md — Data Model Design

## Overview

The data model is built around one core principle: **never mutate source data**.
Every ingested row exists in two forms — the raw original (immutable, forever) and
the normalized derivative (editable, auditable). This separation is what makes the
system trustworthy to auditors.

---

## Entity Map

```
Client
  └── DataIngestion          (one upload job per file)
        └── RawRecord        (one row per source row, immutable)
              └── NormalizedRecord   (one per raw row for SAP/utility,
                                      one per segment for travel)
                    ├── DataQualityFlag   (N flags per record)
                    └── AuditLog          (N log entries per record)

EmissionFactor               (reference table, versioned by year)
UnitConversion               (reference table, per source type)
```

---

## Multi-Tenancy

Every record that carries business data — `DataIngestion`, `NormalizedRecord` —
has a `client` foreign key. This is a **shared-schema, row-level isolation** approach:
all clients live in the same PostgreSQL database and tables, separated only by the
`client_id` column.

**Why shared schema over schema-per-tenant:**
- Simpler migrations — one `manage.py migrate` applies to all clients
- Easier cross-client analytics for Breathe ESG internally
- Sufficient for a prototype; a production system would add row-level security
  policies in PostgreSQL or move to schema-per-tenant for stronger isolation

**Known limitation:** The API currently trusts the `client_id` query parameter.
In production this would be replaced by deriving the client from the authenticated
user's session — never from a user-supplied parameter.

---

## Scope 1 / 2 / 3 Categorization

Scope is assigned at normalization time, not at ingestion time, and is determined
by source type:

| Source | Scope | Rationale |
|--------|-------|-----------|
| SAP fuel/procurement | 1 | Direct combustion by the reporting entity |
| Utility electricity | 2 | Purchased electricity — indirect, but facility-controlled |
| Corporate travel | 3 | Value-chain emissions — caused by the entity, owned by third parties |

The `scope` field on `NormalizedRecord` is an integer (1, 2, 3) rather than a string
to allow numeric filtering and aggregation in queries without string matching.

---

## Source-of-Truth Tracking

Every `NormalizedRecord` links to a `RawRecord` via a non-nullable foreign key.
Every `RawRecord` links to a `DataIngestion` job. This chain means for any computed
CO2e figure you can answer:

- Which file produced this number? (`DataIngestion.filename`)
- When was it uploaded? (`DataIngestion.uploaded_at`)
- Who uploaded it? (`DataIngestion.uploaded_by`)
- What did the original row look like? (`RawRecord.raw_data` — a JSON blob of the
  unmodified parsed row)
- Was the normalized record ever edited? (`NormalizedRecord.is_edited`,
  `NormalizedRecord.edit_reason`)
- What changed, when, and why? (`AuditLog`)

`RawRecord.raw_data` is stored as a JSONField and is **never updated after creation**.
It is the permanent record of what the source system sent.
 
Note: original uploaded files are not persisted by this service — only parsed rows are stored; add file storage and a `DataIngestion.file_hash` field if you need durable file retention.

---

## Unit Normalization

Raw data arrives in inconsistent units:
- SAP: liters, gallons, kilograms, cubic meters (and German variants)
- Utility: kWh or MWh
- Travel: km, miles, or nothing (only cost)

All activity values are normalized before CO2e is computed:
- Fuel → liters (or m³ for natural gas)
- Electricity → kWh
- Flights → km (via Haversine formula from IATA airport coordinates)
- Hotels → room-nights
- Ground → km (from actual distance if available, estimated from cost if not)

Conversion factors live in the `UnitConversion` table (not hardcoded) so they can
be updated without a code deployment. Each conversion is scoped to a `source_type`
because the same unit symbol can mean different things across sources.

---

## Emission Factor Design

`EmissionFactor` is a versioned reference table with `valid_from` and `valid_to`
year fields. This matters because DEFRA and IEA publish updated factors annually —
a factor used for 2023 data should not silently change when 2024 factors are loaded.

Each `NormalizedRecord` stores:
- `emission_factor` — the numeric value used at computation time (snapshot)
- `emission_factor_source` — the publication it came from (e.g. "DEFRA 2023")

Storing the factor value directly on the record (rather than a foreign key to
`EmissionFactor`) means historical records remain stable even if the reference table
is updated. This is intentional.

---

## Audit Trail

`AuditLog` records every field-level change to a `NormalizedRecord`:

| Field | Purpose |
|-------|---------|
| `record` | Which normalized record was changed |
| `changed_by` | The Django user who made the change |
| `changed_at` | Timestamp (auto, server-side) |
| `field_name` | Which field changed (e.g. "status", "activity_value") |
| `old_value` | Previous value as text |
| `new_value` | New value as text |
| `reason` | Free-text justification required on edit |

Audit entries are **append-only** — there is no update or delete path on `AuditLog`.
The approve, flag, and lock actions in `views.py` all write an audit entry before
mutating the record.

**Reviewer UX & Performance note:** Bulk reviewer actions (approve multiple
records) are implemented to avoid N+1 database queries: audit log rows are
created with `AuditLog.objects.bulk_create(...)` and records updated with a
single `NormalizedRecord.objects.filter(id__in=...).update(...)`. This keeps
review operations efficient for hundreds-to-thousands of records.

---

## Workflow States

`NormalizedRecord.status` follows a deliberate state machine:

```
pending ──→ flagged ──→ approved ──→ locked
   └──────────────────→ approved ──→ locked
```

- **pending**: freshly normalized, not yet reviewed
- **flagged**: either auto-flagged by `DataQualityChecker` or manually flagged
  by an analyst with a reason
- **approved**: analyst has reviewed and signed off
- **locked**: approved record sealed for audit — no further edits permitted

Transitions are enforced in the API: you cannot approve a locked record, cannot
lock a non-approved record.

---

## Data Quality Flags

`DataQualityFlag` is separate from `NormalizedRecord` (not just a boolean field)
because a single record can have multiple independent quality issues simultaneously.
Each flag has:
- `flag_type`: outlier | unit_mismatch | gap | duplicate
- `severity`: warning | error
- `description`: human-readable explanation for the analyst

The `DataQualityChecker` runs three checks automatically at normalization time:
1. **Outlier**: value > 3× rolling 90-day average for same facility and activity type
2. **Unit mismatch**: unit differs from previous record for same facility
3. **Impossible value**: negative consumption, or flight distance under 100 km

If any flag exists, the record status is set to `flagged` automatically so it
surfaces in the analyst review queue without manual triage.

---

## What I Would Add With More Time

- **Re-ingestion deduplication**: if the same file is uploaded twice, the current
  model creates duplicate records. A `file_hash` on `DataIngestion` and a unique
  constraint would prevent this.
- **Schema-per-tenant**: for enterprise clients with strict data isolation
  requirements, row-level isolation is insufficient. PostgreSQL schemas or a
  separate database per tenant would be the right approach.
- **Emission factor versioning as FK**: rather than snapshotting the factor value,
  a FK to a specific `EmissionFactor` row (with the version locked at computation
  time) would be cleaner and allow re-computation if a factor was wrong.
- **Billing period alignment**: utility records currently store billing periods
  as-reported (e.g. "Jan 3 – Feb 1"). Aligning these to calendar months for
  period-over-period comparison requires a separate aggregation step not yet built.