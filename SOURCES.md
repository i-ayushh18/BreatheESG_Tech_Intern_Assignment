# SOURCES.md — Research Behind Each Data Source

For each of the three sources: what real-world format I researched, what I learned,
what my sample data looks like and why, and what would break in a real deployment.

---

## Source 1: SAP — Fuel and Procurement Data

### What I Researched

SAP exposes material document data through several mechanisms. I researched:

- **IDoc (Intermediate Document):** SAP's legacy EDI format. Flat files with
  fixed-width segment records prefixed by segment type codes (e.g. `E1MARAM`).
  Used for system-to-system integration in older SAP ECC installations. Column
  headers appear in German in many configurations: `WERKS` (plant), `MENGE`
  (quantity), `MEINS` (unit of measure), `BLDAT` (document date), `MATNR`
  (material number).

- **SAP S/4HANA OData API — Material Document (`API_MATERIAL_DOCUMENT_SRV`):**
  The strategic REST/OData interface for S/4HANA. Returns JSON with a
  `to_MaterialDocumentItem` array containing line-item details. This is the
  documented production API for S/4HANA 1909 onwards. Fields are in English:
  `Plant`, `Material`, `QuantityInEntryUnit`, `EntryUnit`, `PostingDate`.

- **SE16 / MB51 flat file export:** Many SAP installations allow direct table
  exports via transaction SE16 (table browser) or MB51 (material document list).
  These produce pipe-delimited or tab-delimited files with a header row. Field
  names and order vary by configuration.

### What I Learned

- The same quantity can appear in different units across plants. Plant 0001 might
  record diesel in liters while Plant 0002 records it in gallons — both valid SAP
  configurations.
- Material codes (`MATNR`) are internal identifiers that mean nothing without the
  material master (`MARA` table). A code like `RM-DIESEL-001` tells you nothing
  unless you have the description lookup.
- SAP dates use `YYYYMMDD` format (no separators) in IDoc and flat file exports.
  OData returns ISO 8601.
- The OData response wraps line items in `to_MaterialDocumentItem.results` in
  OData v2 and as a flat array in OData v4 — the parser handles both.

### What My Sample Data Looks Like and Why

My SAP sample data is a JSON file matching the S/4HANA OData v2 Material Document
shape. It contains:

- Four line items across two plants (`0001` and `0002`)
- Mixed units: two rows in `L` (liters), one in `GAL` (gallons), one in `KG`
- Two fuel types inferable from material description (`diesel`, `petrol`), one
  ambiguous description (`RM-LUBRICANT-003`) that triggers a `flagged` status
- Dates in `YYYYMMDD` format to test the date parser
- One row with a German-style plant description to reflect real SAP configurations

The ambiguous material description row is deliberate — it tests the fallback fuel
type inference and the automatic flagging logic.

### What Would Break in a Real Deployment

- **Material master lookup:** Real SAP installations require a separate call to
  the material master to get fuel type from material code. Without it, fuel type
  inference relies on free-text description matching, which fails for coded
  descriptions like `RM-0042-A`.
- **Plant code to location mapping:** `WERKS` codes are meaningless without a
  plant master lookup table. The prototype stores `"Plant 0001"` as the facility
  name. A real deployment would need the plant master (`T001W` table) to map
  codes to location names and geographic regions.
- **German column headers in flat file exports:** Some SAP configurations export
  with German headers. The CSV fallback parser would need a header normalization
  layer mapping `MENGE` → `quantity`, `MEINS` → `unit`, etc.
- **Unit of measure variants:** SAP has hundreds of internal UoM codes. `L`, `LT`,
  and `LTR` can all mean liters in different configurations. The unit conversion
  table covers the most common variants but would need expansion for real clients.

---

## Source 2: Utility — Electricity Data

### What I Researched

- **Green Button API:** A US initiative (adopted by NERC) that standardizes
  utility data exposure via a REST API using the ESPI (Energy Services Provider
  Interface) schema. XML-based. Not widely adopted outside North America.

- **Portal CSV exports:** Available from most major utilities globally. I
  specifically looked at the export formats from:
  - Tata Power (Mumbai) — exports meter ID, billing period, consumption in kWh,
    tariff code
  - MSEB/Mahavitaran — similar structure, adds demand charge rows
  - ConEd (New York) — includes interval data (15-minute reads) in addition to
    billing totals
  - National Grid (UK) — half-hourly settlement data, different structure entirely

- **PDF utility bills:** Reviewed the layout of bills from Tata Power and MSEB.
  Consumption appears in inconsistent positions, sometimes split across pages,
  sometimes combined with demand charges in a single line.

### What I Learned

- Billing periods are never exactly one calendar month. They run 28–35 days
  depending on when the meter reader visited. This means you cannot GROUP BY
  month on the raw billing period dates.
- Large facilities have multiple meters. A campus might have one meter for HVAC,
  one for lighting, one for data center load. These appear as separate rows in
  the CSV with the same `facility_name` but different `meter_id`.
- Demand charge rows appear in some utility CSVs as a separate line item with a
  cost but no kWh value. These rows fail the numeric consumption validation and
  are stored as invalid raw records — the correct behaviour, since demand charges
  are not energy consumption.
- Units are inconsistently `kWh` or `MWh` even within the same file. Large
  industrial consumers are sometimes billed in MWh.
- Some utilities include reactive power consumption (`kVARh`) which is irrelevant
  for carbon accounting.

### What My Sample Data Looks Like and Why

My utility sample CSV contains:

- Two meter IDs for the same facility (tests multi-meter handling)
- One row in `MWh`, the rest in `kWh` (tests unit normalization)
- Billing periods that cross month boundaries (Jan 3 – Feb 1, Feb 1 – Mar 5)
- One demand charge row with no consumption value (tests validator rejection)
- A billing period gap of 47 days between two rows for the same meter (would
  trigger a gap flag in a more complete quality checker)

### What Would Break in a Real Deployment

- **Tariff structure complexity:** Some tariffs have tiered pricing where the
  first 500 kWh is billed at one rate and the next 500 at another. The CSV
  sometimes has one row per tier. The current parser sums all consumption rows
  for the same billing period — this is correct for carbon accounting (total kWh
  is what matters, not which tier) but requires the parser to handle multiple
  rows per billing period per meter.
- **Billing period proration:** Attributing a 29-day billing period entirely to
  the start month introduces a small systematic error. A production system would
  prorate: `(days in month / total days) × consumption` for each calendar month
  the period spans.
- **Sub-national grid factors:** India has five regional grids with different
  emission intensities (southern grid is cleaner than northern). The current
  implementation uses the national average (0.716 kg CO2e/kWh). A client with
  facilities in both Tamil Nadu and Uttar Pradesh should use different factors.
  IEA does not publish sub-national factors for India; this would require CEA
  (Central Electricity Authority) data.
- **PDF bills:** If a facilities team cannot export CSV and only has PDF bills,
  the current ingestion pipeline has no path for them. This would require a PDF
  extraction layer (pdfplumber or similar) which is fragile and out of scope.

---

## Source 3: Corporate Travel — Flights, Hotels, Ground Transport

### What I Researched

- **SAP Concur Itinerary API v4:** Reviewed the official Concur developer
  documentation at developer.concur.com. The Itinerary v4 API returns a
  `Bookings` array where each booking contains a `Segments` object with `Air`,
  `Hotel`, `Ride`, and `Car` sub-arrays. Air segments include `StartCityCode`
  and `EndCityCode` (IATA codes), `StartDateLocal`, and `Cabin`/`ClassOfService`.
  Hotel segments include `StartCity`, `StartDateLocal`, `EndDateLocal`. Ride
  segments include `Rate` and optionally `Miles`.

- **Navan (formerly TripActions) API:** Less publicly documented. The response
  shape groups trips by traveller with a flat segment list. Similar fields but
  different nesting structure.

- **ICAO Carbon Emissions Calculator methodology:** Reviewed ICAO Doc 9889
  (Airport Air Quality Manual) and the ICAO carbon calculator methodology for
  how aviation emissions are computed. Key finding: a radiative forcing index
  (RFI) multiplier of approximately 2× should be applied to account for the
  warming effect of contrails and NOx emissions at altitude. DEFRA 2023 factors
  already incorporate this multiplier.

- **GHG Protocol Scope 3 Standard, Category 6 (Business Travel):** The GHG
  Protocol guidance recommends distance-based emission factors (kg CO2e/km) over
  spend-based factors (kg CO2e/USD) because distance-based is more accurate and
  consistent across currencies and time.

### What I Learned

- Concur does not provide flight distances. Origin and destination are IATA codes
  only. Distance must be computed from airport coordinates.
- Business class factors are approximately 3× economy for long-haul flights
  because business seats occupy more cabin space per passenger (larger seats,
  fewer passengers per aircraft).
- The short-haul / long-haul threshold used by DEFRA is 3,700 km. Below this,
  the per-km factor is lower because short-haul flights spend proportionally more
  time in fuel-intensive climb phase, but the total distance is smaller.
- Hotel emission factors vary significantly by region. A room-night in the US
  (35.8 kg CO2e) emits more than double a room-night in France (14.2 kg CO2e)
  because US hotels are larger, less energy efficient, and on a dirtier grid.
- Ground transport data from Concur is the least reliable. Ride segments often
  have a cost but no distance. Car rental segments sometimes have `EstimatedMiles`
  but this is self-reported by the booking platform and often missing.

### What My Sample Data Looks Like and Why

My travel sample JSON matches the Concur Itinerary v4 shape. It contains:

- One itinerary with three bookings: a flight, a hotel, and a ground segment
- Flight: DEL → BOM (economy, short-haul) — tests distance calculation and
  short-haul factor selection
- Hotel: 2 nights in Mumbai — tests hotel factor and nights calculation
- Ground: taxi with cost only, no distance — tests cost-based distance estimation
- One additional flight with an unknown airport code (`XYZ`) — tests that the
  parser raises a ValueError rather than silently computing 0 km

The unknown airport code row is intentional — it produces an invalid raw record
that surfaces in the analyst dashboard's failed rows panel.

### What Would Break in a Real Deployment

- **Airport coordinate coverage:** The prototype lookup table has 6 airports.
  A real deployment needs all ~10,000 IATA-coded airports. The open-source
  OurAirports dataset (ourairports.com) provides this as a freely downloadable
  CSV and would be the right data source.
- **Connecting flights:** A DEL → DXB → LHR itinerary appears as two separate
  air segments in Concur. The current model handles this correctly (each segment
  gets its own emission calculation) but does not flag to the analyst that this
  is an indirect routing that may have been longer than a direct flight.
- **Non-Concur platforms:** Navan, TravelPerk, and internal booking tools each
  have different API shapes. Supporting multiple platforms requires either a
  platform-specific parser per source or a normalisation layer that maps each
  platform's shape to the internal segment format.
- **Currency conversion for ground transport:** Cost-based distance estimation
  uses $2/km. This breaks immediately for ground transport booked in INR, EUR,
  or GBP. A real implementation would need a currency conversion step before the
  distance estimate.
- **Radiative forcing for non-DEFRA factors:** If a client requires ICAO
  methodology instead of DEFRA, the RFI multiplier must be applied separately.
  DEFRA 2023 factors already include RFI; ICAO base factors do not.

---

## Reference Sources

| Source | URL | Used For |
|--------|-----|----------|
| DEFRA 2023 Conversion Factors | gov.uk/government/collections/government-conversion-factors-for-company-reporting | Fuel, flight, hotel, ground factors |
| IEA Emissions Factors 2023 | iea.org/data-and-statistics/data-product/emissions-factors-2023 | Grid electricity factors by country |
| SAP Material Document OData API | api.sap.com/api/API_MATERIAL_DOCUMENT_SRV | SAP OData field names and structure |
| SAP Concur Itinerary API v4 | developer.concur.com/api-reference/travel/itinerary-tmc-thirdparty | Travel segment structure |
| GHG Protocol Scope 3 Standard | ghgprotocol.org/scope-3-standard | Scope categorisation methodology |
| ICAO Carbon Calculator | icao.int/environmental-protection/CarbonOffset | Aviation emission methodology |
| OurAirports dataset | ourairports.com/data | Airport IATA codes and coordinates |