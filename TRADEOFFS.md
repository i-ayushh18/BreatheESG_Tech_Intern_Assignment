# TRADEOFFS.md — What I Deliberately Did Not Build

Three things I chose not to build, why, and what the cost of that choice is.

---

## 1. Asynchronous Ingestion Pipeline

**What I did not build:** A task queue (Celery + Redis) to process uploaded files
in the background.

**What I built instead:** Synchronous ingestion — the file is parsed, validated,
normalized, and flagged within the HTTP request cycle before the API responds.

**Why I made this choice:**
The synchronous approach is significantly simpler to deploy and debug. For the
prototype's sample data (tens to low hundreds of rows), it completes in under a
second. Adding Celery would require Redis as a broker, a separate worker process,
job status polling on the frontend, and a more complex deployment configuration —
none of which add value at this data scale.

**The real cost of this tradeoff:**
A real enterprise client's SAP export might contain 50,000–200,000 rows. A utility
client with 300 meters across 50 facilities generates thousands of rows per billing
cycle. At that scale, synchronous ingestion will hit the HTTP request timeout
(typically 30–60 seconds on most hosting providers) and the entire upload will fail
with no partial progress saved.

The fix is well-understood: move processing into a Celery task, return a job ID
immediately, and let the frontend poll `/ingestions/{id}/` for status. The ingestion
pipeline code itself does not change — only the trigger mechanism. This is a
deliberate seam I left in the architecture.

**Signal in the code:** `DataIngestion.status` already has `processing`,
`completed`, and `failed` states. The field exists precisely to support async
status polling when the task queue is added.

---

## 2. Re-ingestion Deduplication

**What I did not build:** Detection and handling of duplicate file uploads.

**What I built instead:** Each upload creates a new `DataIngestion` job and new
`RawRecord` rows unconditionally. If the same file is uploaded twice, the database
will contain two copies of every row with identical data but different primary keys.

**Why I made this choice:**
Deduplication is operationally complex because "duplicate" is not always obvious.
Is a re-upload of the same filename a duplicate? What if the client corrected three
rows and re-exported? What if two different facilities happen to produce files with
the same name? Resolving these cases requires a product decision, not just a
technical one — I would need the PM's answer to DECISIONS.md question #1 before
implementing this correctly.

Building a naive hash-based deduplication (reject if SHA-256 of file content
matches a previous upload) would be straightforward but would block legitimate
re-uploads of corrected files, which is probably the most common real-world case.

**The real cost of this tradeoff:**
An analyst who uploads a file twice will see doubled emission figures in the summary
panel without any warning. This is a data integrity issue that would be caught in
review but is still a significant gap for a production system.

**How I would fix it:**
Store `file_hash` (SHA-256) on `DataIngestion`. On upload, check for an existing
ingestion with the same hash and client. If found, warn the analyst and require
explicit confirmation to proceed. If the client wants to replace rather than append,
soft-delete the previous ingestion's normalized records and re-run normalization
on the new file.

Note: original uploaded files are not persisted by this service — only parsed rows are stored; add file storage and a `DataIngestion.file_hash` field if you need durable file retention.

---

## 3. Emission Factor Versioning as a Relationship

**What I did not build:** A foreign key from `NormalizedRecord` to the specific
`EmissionFactor` row used in its calculation.

**What I built instead:** A snapshot approach — the factor value and source string
are copied directly onto the `NormalizedRecord` at computation time
(`emission_factor = 2.68`, `emission_factor_source = "DEFRA 2023"`).

**Why I made this choice:**
The snapshot approach is simpler and has one important correctness property: a
historical record's CO2e figure never changes when the reference table is updated.
If DEFRA publishes 2024 factors and someone loads them into `EmissionFactor`, records
computed with 2023 factors are not silently recalculated. For an audit trail this
is the right default behavior.

A FK approach would be cleaner for traceability (you could query "all records that
used this specific factor version") but introduces the risk of accidentally
recalculating historical records if the FK target is updated rather than versioned
correctly.

**The real cost of this tradeoff:**
If an emission factor was loaded incorrectly (wrong value, typo) and used to compute
100 records, there is no easy query to find all affected records and trigger
recomputation. With a FK approach you could do:
`NormalizedRecord.objects.filter(emission_factor_fk=bad_factor_id)` and recompute.
With the snapshot approach you have to search by value and source string, which is
fragile.

**How I would fix it:**
Add `emission_factor_fk = ForeignKey(EmissionFactor, null=True)` alongside the
existing snapshot fields. Populate both at computation time. The snapshot fields
remain the source of truth for the displayed value; the FK enables bulk recomputation
queries when needed. Keep both — they serve different purposes.

---

## Honourable Mentions (not the main three, but worth noting)

**No pagination on the frontend:** The records table fetches all records in one
request. At scale this would be unusable. Django REST Framework pagination is
configured on the backend but the React table does not implement page controls.

**No authentication:** The API has no login system. Any request can read or modify
any client's data. This was intentional for prototype speed — adding Django's
session auth or SimpleJWT would take a few hours but adds significant setup
complexity for a reviewer trying to run the app locally.

**No billing period proration:** Utility consumption is attributed to the month
the billing period starts, not prorated across the months it spans. January 3 –
February 1 consumption is reported entirely under January. This overstates January
and understates February by roughly one day's worth of consumption per billing
period — small in absolute terms but methodologically imprecise.