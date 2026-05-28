# DECISIONS.md — Design Decisions and Resolved Ambiguities

Every ambiguous choice made during this build is documented here: what I chose,
why, what I ruled out, and what I would ask the PM if I could.

---

## Source 1: SAP — Format Choice

**Decision: SAP S/4HANA Material Document OData JSON, with CSV fallback.**

SAP exposes data in several ways: IDoc flat files, OData services, BAPIs, and
direct database exports. I chose OData JSON for the following reasons:

- IDoc is the legacy EDI format. It is still common but requires a dedicated IDoc
  parser that handles fixed-width segment records and EDI control envelopes. The
  realistic scenario for a new client onboarding is that their IT team exposes an
  OData endpoint or exports a JSON payload from S/4HANA — not that they hand over
  raw IDoc files.
- BAPI is a function call interface, not an export format. It requires live SAP
  connectivity and RFC libraries — not appropriate for a file-upload ingestion model.
- OData is the strategic API direction for SAP S/4HANA. The Material Document API
  (`API_MATERIAL_DOCUMENT_SRV`) is a standard S/4HANA OData service. Its JSON shape
  is documented and consistent across clients.

The parser handles the `to_MaterialDocumentItem` nesting structure that SAP uses
for line items, including both the `results` wrapper (OData v2) and the flat array
form (OData v4). A CSV fallback is included for clients whose IT teams export
via SE16 or similar transaction — this is common at smaller or older installations.

**What I ignored:** German column headers (WERKS, MENGE, MEINS) in the CSV variant.
In the OData variant these are abstracted away by the API layer. For a CSV-only
implementation I would need a column header mapping table, which I noted as a
known gap.

**What I would ask the PM:** Does the client's SAP system expose OData services, or
are they doing manual exports? If manual exports, what transaction are they using
(SE16, MB51, or something custom)? This determines whether the OData parser or the
CSV fallback is the primary path.

---

## Source 2: Utility — Format Choice

**Decision: Portal CSV export.**

Utility data reaches facilities teams in three ways: PDF bills, portal CSV exports,
and Green Button API (where available). I chose CSV for the following reasons:

- PDF parsing is fragile. Utility bill layouts differ between providers and change
  without notice. A PDF parser that works for Tata Power will break for MSEB or
  BSES. The maintenance cost is too high for a prototype.
- Green Button API is a US-centric standard. It is not universally available in
  India and requires per-utility OAuth integration. Not realistic for a first
  onboarding.
- Portal CSV is the path facilities teams actually use today. Every major utility
  portal (Tata Power, MSEB, ConEd, National Grid) offers a CSV download. The format
  is messier than an API but predictable enough to parse reliably.

**Billing period handling:** Utility billing periods do not align with calendar
months. A billing period might run Jan 3 – Feb 1 (29 days) or Jan 28 – Mar 5
(36 days). I store the billing period as-reported (`billing_start`, `billing_end`)
on the raw record and derive `reporting_period` as the start month (YYYY-MM) for
grouping. This means a record billed Jan 3 – Feb 1 is reported under January.
This is an approximation — a full implementation would prorate consumption across
the months the billing period spans.

**What I ignored:** Demand charges (a fixed capacity fee that appears as a row in
some utility CSVs). These are not energy consumption and should not be included in
CO2e calculations. The parser currently skips them by only reading the `consumption`
field — rows where consumption is non-numeric are rejected by the validator.

**What I would ask the PM:** Do clients have multiple meters per facility? If so,
should we aggregate at the facility level before computing emissions, or keep
meter-level granularity for the analyst? Currently we keep meter-level granularity
(`meter_id` is stored on the raw record).

---

## Source 3: Travel — Format Choice

**Decision: SAP Concur Itinerary v4 JSON, with simplified JSON fallback.**

Corporate travel data comes from platforms like Concur, Navan, TravelPerk, or
internal booking tools. I chose to model the SAP Concur Itinerary v4 API shape
because:

- Concur is the dominant enterprise travel management platform globally. Most
  large companies that use SAP for ERP also use Concur for travel.
- The Concur Itinerary API v4 is publicly documented. The `Bookings.Segments`
  structure with `Air`, `Hotel`, `Ride`, and `Car` sub-arrays is the actual
  production shape.
- Navan's API shape is similar but less documented. Modeling Concur covers the
  majority of the enterprise market.

Since live OAuth credentials are not available for a prototype, I ingest a JSON
file that matches the Concur API response shape. This is realistic — a production
system would call the Concur API on a schedule and write the response to the same
ingestion pipeline.

**Flight distance:** Concur provides origin and destination as IATA airport codes,
not distances. I compute distance using the Haversine formula against a lookup table
of airport coordinates. The lookup table in this prototype covers 6 airports (DEL,
BOM, BLR, CCU, HYD, SFO). Unknown airport codes raise a ValueError rather than
returning 0 silently — a silent 0 would produce a plausible-looking but wrong CO2e
figure.

**Ground transport distance:** When only cost is available (no distance field),
I estimate distance as `cost_usd / 2` (assuming $2/km as a rough global average
for taxis). This estimate is flagged as uncertain — I would add a `DataQualityFlag`
for estimated ground distances in a follow-up iteration.

**What I ignored:** Multi-leg itineraries with stopovers (e.g. DEL → DXB → LHR).
Currently each air segment is treated independently, which is correct — each leg
gets its own emission calculation. The issue is with connection flights where the
indirect routing adds distance. This is handled correctly by the segment-level
model but not explicitly called out to the analyst.

**What I would ask the PM:** Does the client use Concur, Navan, or another platform?
If Navan, the segment structure differs (no `Bookings` wrapper). Does the client
want individual employee-level tracking, or aggregated by department or cost center?

---

## Emission Factor Source

**Decision: DEFRA 2023 for fuel and travel, IEA 2023 for electricity grid factors.**

DEFRA (UK Department for Environment, Food and Rural Affairs) publishes the most
widely used conversion factor dataset globally, covering fuel combustion, flights,
hotels, and ground transport. IEA (International Energy Agency) publishes country-
level grid emission factors which DEFRA does not cover comprehensively.

Both sources are used by the Big Four accounting firms for carbon assurance
engagements. Citing them signals that the numbers are audit-defensible.

**India grid factor:** 0.716 kg CO2e/kWh (IEA 2023). This is the national average.
Regional variation exists (southern grid is cleaner than northern grid) but
sub-national factors are not published by IEA. National average is the standard
for Scope 2 location-based reporting.

**Hardcoded default:** The normalizer defaults to the India grid (`IN`) for
electricity records that do not specify a region. This is appropriate for the
demo client but would need to be configurable per client or per facility in
production.

---

## Ingestion Mechanism — File Upload over API Pull

**Decision: File upload for all three sources.**

A production system would pull data via scheduled API calls (Concur OAuth, utility
Green Button, SAP OData with refresh tokens). For a prototype with a 4-day timeline,
file upload is the correct choice because:

- It decouples the ingestion pipeline from third-party authentication complexity
- It is actually how many enterprise clients transfer data today (SFTP drops,
  email attachments, shared drives)
- The pipeline code — parse, validate, normalize, flag — is identical whether the
  file arrives via upload or API pull. Switching to API pull later requires changing
  only the ingestion trigger, not the pipeline.

---

## Multi-Tenancy Implementation

**Decision: Shared schema with client FK, no authentication enforcement on API.**

The `client` foreign key exists on all business data models. In the current
prototype the API trusts the `client_id` query parameter. In production:

- Authentication would use Django's session or JWT token system
- The authenticated user would have a `client` foreign key on their profile
- All queryset filtering would derive `client_id` from `request.user.client`,
  never from a user-supplied parameter

This is documented as a known gap, not an oversight.

## Analyst Edits & Audit Trail

**Decision:** Analysts must be able to correct normalized records before locking. Edits are recorded at the field level in `AuditLog` and the `NormalizedRecord` stores `is_edited` and `edit_reason` for quick reference.

**Why:** The assignment requires an analyst review step where values can be corrected (e.g. a wrongly inferred fuel type or manually-entered flight distance). Replacing a normalized value with no trace would break auditability.

**Implementation note:** The API exposes a `PATCH /records/{id}/edit/` action that accepts changed fields and an `edit_reason`. Each changed field is appended to `AuditLog` and the record is marked `is_edited=True`. Bulk approvals use `AuditLog.objects.bulk_create` and a bulk `update()` on `NormalizedRecord` to avoid N+1 query patterns during reviewer operations.

## Unit Conversion Decisions (mass ↔ volume)

**Decision:** Mass-to-volume conversions for fuels are fuel-type-specific and must not be represented by a single generic `KG -> L` factor.

**Why:** Different fuels have different densities (diesel ≈ 0.85 kg/L, petrol ≈ 0.75–0.78 kg/L, LPG ≈ 0.5–0.6 kg/L). Using one factor produces material errors in CO2e for fuel records.

**Implementation note:** The prototype avoids seeding a generic `KG->L` conversion. Production options:
- Add `fuel_type` to `UnitConversion` and populate separate mass↔volume rows per fuel
- Or require ingestion to annotate fuel `fuel_type` earlier (material master lookup) and apply the correct conversion

**Trade-off:** The current prototype may need a manual step when onboarding a client whose SAP exports record mass instead of volume. Document this in onboarding notes.

---

## Normalization Failures — Store, Don't Discard

**Decision: Invalid rows are stored as RawRecords with no NormalizedRecord, not
discarded.**

When a row fails validation (missing quantity, non-numeric consumption, no travel
segments), the raw record is still written to the database. The analyst dashboard
surfaces these as "rows that did not create normalized records" with a specific
error message per row.

Discarding invalid rows would be wrong for an audit context — the auditor needs to
know that the source file contained 200 rows and 3 of them were invalid, not that
the source file contained 197 rows.

---

## Questions I Would Ask the PM

1. When a client re-uploads a corrected version of a file already ingested, how
   should conflicts be handled? Replace the previous ingestion? Append and let the
   analyst reconcile? This is the most important unanswered question for production.

2. Should the reporting period be the billing period start date (current approach)
   or should utility consumption be prorated across the calendar months it spans?

3. Is employee-level travel tracking required, or is department/cost-center
   aggregation sufficient? This affects whether we store `employee_id` on normalized
   records or anonymize at ingestion.

4. What is the expected file size? If clients upload SAP exports with 100,000 rows,
   synchronous ingestion will time out. This would require an async task queue
   (Celery + Redis) which is currently not built.

5. Do clients need to compare their emissions against a baseline year? If so, the
   data model needs a `baseline_year` concept on the Client model and the reporting
   period filtering needs to support multi-year queries.