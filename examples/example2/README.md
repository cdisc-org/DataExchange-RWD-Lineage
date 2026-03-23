# Example 2 — Laboratory Results and Adverse Events from EHR Lab Data

This example demonstrates RWD lineage traceability for two SDTM domains — **LB (Laboratory Test Results)** and **AE (Adverse Events)** — derived from a single EHR source table of LOINC-coded lab results. It showcases multi-step transformations (value parsing, unit conversion) and cross-domain derivation (lab abnormalities triggering an adverse event record).

## Scenario

A study collects liver-enzyme lab panels (ALT, AST, ALP) for two subjects across two visits each. Raw EHR lab results arrive as composite strings with values and units combined (e.g., `"0.3507 µkat/L"`). These are parsed, converted to standard units, and mapped into the SDTM LB domain. When a subject's results cross the normal range threshold, a hepatic enzyme elevation adverse event is derived in the AE domain.

### Source Data

| Table | Columns | Records | Description |
|-------|---------|---------|-------------|
| `LabResults.csv` | `PATID`, `LOINC Code`, `Lab Test`, `Visit Date`, `Lab Result` | 12 | Raw LOINC-coded lab results from the EHR, with results as composite value+unit strings |

### Target Data

| Table | Columns | Records | Description |
|-------|---------|---------|-------------|
| `LB.csv` | `USUBJID`, `LBSEQ`, `LBTESTCD`, `LBTEST`, `LBDTC`, `LBORRES`, `LBORRESU`, `LBSTRES`, `LBSTRESU`, `LBSTNRLO`, `LBSTNRHI`, `LBNRIND` | 12 | SDTM LB domain — 2 subjects × 3 tests × 2 visits |
| `AE.csv` | `USUBJID`, `AESEQ`, `AETERM`, `AEDECOD`, `AELLTCD`, `AESER`, `AEREL`, `AESTDTC` | 1 | SDTM AE domain — 1 hepatic enzyme elevation event for subject 002 |

### Lab Tests Covered

| LOINC Code | Test Name | SDTM `LBTESTCD` |
|------------|-----------|------------------|
| 1742-6 | Alanine Aminotransferase | ALT |
| 1920-8 | Aspartate Aminotransferase | AST |
| 1775-6 | Alkaline Phosphatase | ALP |

---

## Algorithms

### Laboratory Test Results (LB)

Lab results from the EHR are mapped to the SDTM LB domain through the following steps:

1. **Direct mapping**: LOINC codes and lab test names are mapped to `LBTESTCD`/`LBTEST`; visit dates are mapped to `LBDTC`
2. **Lab value parsing**: Raw result strings (e.g., `"0.3507 µkat/L"`) are parsed to extract the numeric value into `LBORRES` and the unit into `LBORRESU`
3. **Unit conversion**: Original units (µkat/L) are converted to standard units (U/L), with results stored in `LBSTRES`/`LBSTRESU`
4. **Normal range evaluation**: Standard results are compared against reference ranges (`LBSTNRLO`, `LBSTNRHI`) to determine the normal-range indicator (`LBNRIND`)

### Adverse Events (AE)

A hepatic enzyme elevation adverse event is derived from the LB domain:

1. LB records where `LBNRIND = HIGH` for ALT, AST, or ALP are identified
2. The dictionary-derived term `AEDECOD` is populated as "Hepatic enzyme increased"
3. The adverse event start date `AESTDTC` is taken from the earliest elevated lab result date

In this example, subject 002's second visit (2025-11-06) shows all three liver enzymes elevated above normal range, producing a single AE record.

---

## Lineage Overview

The `rwd-lineage.xml` file contains **99 `<MapID>` elements** tracing source EHR lab data to the SDTM LB and AE domains.

### Transformation Types

| Type | Count | Target Domain | Description |
|------|-------|---------------|-------------|
| `DirectMap` | 36 | LB | One-to-one mapping (LOINC code → `LBTEST`, visit date → `LBDTC`, patient ID → `USUBJID`, etc.) |
| `LabValueParsing` | 24 | LB | Parsing composite result strings into numeric value and unit components |
| `UnitConversion` | 24 | LB | Converting original units (µkat/L) to standard units (U/L) |
| `DirectMap` | 3 | AE | Direct mappings for AE fields derived from LB data |
| `ElevatedLiverEnzyme` | 12 | AE | Algorithmic derivation identifying elevated lab values to produce the adverse event |

### Lineage by Domain

**LB domain (84 lineage entries across 12 records)**
Each of the 12 LB records receives 7 lineage entries covering 5 target columns: `LBTEST` (DirectMap), `LBDTC` (DirectMap), `LBORRES` (LabValueParsing × 2 — one for value, one for unit source), `LBORRESU` (LabValueParsing × 2), and `LBSTRES`/`LBSTRESU` (UnitConversion × 2 each). This pattern demonstrates the multi-step transformation pipeline where a single raw result string undergoes parsing and then conversion.

**AE domain (15 lineage entries for 1 record)**
The single AE record for subject 002 traces to 12 `ElevatedLiverEnzyme` entries (one per source lab result contributing to the elevated-enzyme determination) plus 3 `DirectMap` entries for the derived fields (`AEDECOD`, `AESTDTC`). This demonstrates cross-domain derivation: the AE record's lineage points back through the LB transformation pipeline to the original EHR source.

---

## Contents

```
example2/
├── README.md                        # This file
├── Example2.xlsx                    # Companion workbook (SDTM AE, SDTM LB, Source LabResults, RWDLineage-Table)
└── data/
    ├── sdtm/
    │   ├── AE.csv                   # SDTM AE domain — 1 record (subject 002 hepatic enzyme elevation)
    │   └── LB.csv                   # SDTM LB domain — 12 records (2 subjects × 3 tests × 2 visits)
    ├── source/
    │   └── LabResults.csv           # EHR lab results — 12 rows (PATID, LOINC Code, Lab Test, Visit Date, Lab Result)
    └── define/
        ├── define.xml               # Define-XML 2.1 with rwdl namespace extension referencing rwd-lineage.xml
        └── rwd-lineage.xml          # RWD-Lineage XML — 99 MapID elements linking source EHR data to SDTM AE and LB
```

---

## Validation

From the repository root:

```bash
# Validate the RWD-Lineage XML structure
python3 tools/validate.py rwd-lineage examples/example2/data/define/rwd-lineage.xml

# Validate the Define-XML against CDISC XSD (requires lxml)
python3 tools/validate.py define-xml examples/example2/data/define/define.xml

# Check that every SDTM cell has lineage coverage
python3 tools/validate.py coverage examples/example2/data/sdtm examples/example2/data/define/rwd-lineage.xml
```

---

## Key Concepts Demonstrated

- **Multi-step transformations**: A single lab result passes through parsing → unit conversion → range evaluation, with each step recorded as a separate lineage entry.
- **Cross-domain derivation**: The AE record is derived from LB domain data, which is itself derived from source EHR data — the lineage captures both hops.
- **High coverage density**: 99 lineage entries across 13 SDTM records demonstrate cell-level traceability at scale, covering every column including standard-range metadata (`LBSTNRLO`, `LBSTNRHI`, `LBNRIND`).
- **Composite string parsing**: The `LabValueParsing` transformation type documents how a single source field (`"0.3507 µkat/L"`) fans out into multiple target fields (numeric value + unit).
