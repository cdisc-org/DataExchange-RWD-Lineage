# Examples

This directory contains worked examples that demonstrate the [RWD-Lineage Data Standard](../documents/RWD-Lineage_Data_Standard_Specification.md) — a machine-readable CDISC data exchange format for capturing the lineage of Real-World Data (RWD) as it is transformed into SDTM datasets.

Each example provides a complete, self-contained package: source EHR data, target SDTM datasets, a Define-XML 2.1 file with the `rwdl` namespace extension, and a companion `rwd-lineage.xml` file that traces every cell in the SDTM output back to its origin in the source data.

---

## Quick Start

```
examples/
├── README.md              ← You are here
├── example1/              ← CE domain: diagnoses, vitals, and clinical notes
│   ├── README.md
│   ├── Example1.xlsx
│   └── data/
│       ├── define/
│       │   ├── define.xml
│       │   └── rwd-lineage.xml
│       ├── sdtm/
│       │   └── ce.csv
│       └── source/
│           ├── pt_dx.csv
│           ├── vitals.csv
│           └── notes.csv
└── example2/              ← AE + LB domains: lab results and adverse events
    ├── README.md
    ├── Example2.xlsx
    └── data/
        ├── define/
        │   ├── define.xml
        │   └── rwd-lineage.xml
        ├── sdtm/
        │   ├── AE.csv
        │   └── LB.csv
        └── source/
            └── LabResults.csv
```

### Validating an example

From the repository root:

```bash
# Validate the RWD-Lineage XML
python3 tools/validate.py rwd-lineage examples/example1/data/define/rwd-lineage.xml

# Validate the Define-XML (requires lxml)
python3 tools/validate.py define-xml examples/example1/data/define/define.xml

# Check that every SDTM cell has lineage coverage
python3 tools/validate.py coverage examples/example1/data/sdtm examples/example1/data/define/rwd-lineage.xml
```

See the [repository README](../README.md) for full validation instructions and requirements.

---

## Example Summaries

### Example 1 — Clinical Events (CE) from EHR Diagnoses, Vitals, and Notes

**SDTM domain:** CE (Clinical Events)
**Source tables:** `pt_dx` (ICD-10 diagnoses), `vitals` (blood pressure, BMI), `notes` (free-text clinical notes)
**Subjects:** 2 (001, 002) &nbsp;×&nbsp; 2 prespecified conditions = 4 CE records
**Lineage entries:** 20 `<MapID>` elements

This example models two prespecified clinical events — **hypertension** and **acute myocardial infarction** — and shows how each `CEOCCUR` determination draws on multiple evidence sources:

| Transformation Type | Count | Description |
|---------------------|-------|-------------|
| `DirectMap`         | 7     | One-to-one mapping of a source value to a target field (e.g., ICD-10 code → `CEOCCUR` evidence) |
| `AfterIndexDate`    | 5     | Temporal filter ensuring the source event falls within the study follow-up period |
| `NLPExtraction`     | 5     | Structured data extracted from free-text clinical notes via NLP |
| `FilterByValue`     | 3     | Conditional inclusion based on a source value (e.g., blood pressure ≥ threshold) |

**Key concepts illustrated:**
- Multi-source evidence: a single SDTM cell (`CEOCCUR`) can trace to diagnosis codes, vital-sign measurements, *and* NLP-extracted findings simultaneously.
- Prespecified event algorithms: the lineage captures each step of a composite clinical algorithm (diagnosis code check → temporal filter → vitals threshold → NLP confirmation).
- NLP lineage: free-text clinical notes are treated as a legitimate source, with the `NLPExtraction` transformation type documenting the extraction.

→ See [`example1/README.md`](example1/README.md) for the full algorithm definitions.

---

### Example 2 — Laboratory Results (LB) and Adverse Events (AE) from EHR Labs

**SDTM domains:** LB (Laboratory Test Results), AE (Adverse Events)
**Source table:** `LabResults` (LOINC-coded lab results with raw values in original units)
**Subjects:** 2 (001, 002) &nbsp;×&nbsp; 3 liver-enzyme tests &nbsp;×&nbsp; 2 visits = 12 LB records + 1 AE record
**Lineage entries:** 99 `<MapID>` elements

This example traces LOINC-coded EHR lab data through unit conversion into the SDTM LB domain, then derives an adverse event (hepatic enzyme elevation) in the AE domain:

| Transformation Type      | Count | Description |
|--------------------------|-------|-------------|
| `DirectMap`              | 39    | One-to-one mappings (LOINC → `LBTESTCD`, visit date → `LBDTC`, patient ID → `USUBJID`, etc.) |
| `LabValueParsing`        | 24    | Parsing composite result strings (e.g., `"0.3507 µkat/L"`) into numeric value and unit components |
| `UnitConversion`         | 24    | Converting original units (µkat/L) to standard units (U/L) with stored results in `LBSTRES`/`LBSTRESU` |
| `ElevatedLiverEnzyme`    | 12    | Algorithmic derivation identifying elevated ALT/AST/ALP to produce the AE record |

**Key concepts illustrated:**
- Multi-step transformations: a single lab result passes through parsing → conversion → standardization, each step recorded as a separate lineage entry.
- Cross-domain derivation: the AE domain record is derived from the LB domain, which is itself derived from source EHR data — the lineage captures both hops.
- High coverage density: 99 lineage entries across 13 SDTM records demonstrates cell-level traceability at scale, including every standard-range indicator (`LBSTNRLO`, `LBSTNRHI`, `LBNRIND`).

→ See [`example2/README.md`](example2/README.md) for the full algorithm definitions.

---

## Anatomy of an Example

Every example follows the same internal structure:

```
exampleN/
├── README.md            # Scenario description, algorithm definitions, file inventory
├── ExampleN.xlsx        # Human-readable workbook with all tables and lineage in spreadsheet form
└── data/
    ├── define/
    │   ├── define.xml       # Define-XML 2.1 with rwdl namespace extension
    │   └── rwd-lineage.xml  # RWD-Lineage XML: the cell-level lineage map
    ├── sdtm/
    │   └── *.csv            # Target SDTM domain datasets
    └── source/
        └── *.csv            # Source EHR/RWD tables
```

### `define.xml`

A standard [CDISC Define-XML 2.1](https://www.cdisc.org/standards/data-exchange/define-xml) file with one addition — the `rwdl` namespace extension that references the companion lineage file:

```xml
<ODM xmlns:rwdl="http://www.cdisc.org/ns/rwd-lineage/v1" ...>
  <Study>
    <MetaDataVersion>
      <rwdl:lineage>
        <rwdl:ref leafID="LF.RWDLINEAGE">rwd-lineage.xml</rwdl:ref>
      </rwdl:lineage>
      <!-- Standard ItemGroupDef / ItemDef elements follow -->
    </MetaDataVersion>
  </Study>
</ODM>
```

### `rwd-lineage.xml`

The core deliverable. Each `<MapID>` element represents one source-to-target cell mapping:

```xml
<RWDLineage xmlns="http://www.cdisc.org/ns/rwd-lineage/v1" ...>
  <MapID uuid="35060134-fc2f-4cdf-9abe-491924739bd5">
    <Transformation type="DirectMap">Direct Map</Transformation>
    <Source>
      <Coordinate storage="Filesystem" structure="Tabular">
        <URI>...source/pt_dx.csv</URI>
        <RowIndex>4</RowIndex>
        <ColumnName>ICD10</ColumnName>
      </Coordinate>
    </Source>
    <Target>
      <Coordinate storage="Filesystem" structure="Tabular">
        <URI>...sdtm/ce.csv</URI>
        <RowIndex>2</RowIndex>
        <ColumnName>CEOCCUR</ColumnName>
      </Coordinate>
    </Target>
  </MapID>
  <!-- ... -->
</RWDLineage>
```

Key attributes are documented in the [RWD-Lineage Data Standard Specification](../documents/RWD-Lineage_Data_Standard_Specification.md).

### `ExampleN.xlsx`

A companion Excel workbook containing all source tables, SDTM output tables, and the lineage mappings in tabular form. This is provided for human review and is not a normative artifact — the XML files are the machine-readable standard.

---

## Transformation Types Used Across Examples

| Type | Example 1 | Example 2 | Description |
|------|-----------|-----------|-------------|
| `DirectMap` | ✓ | ✓ | One-to-one value copy from source to target |
| `AfterIndexDate` | ✓ | | Temporal filter relative to a study index date |
| `FilterByValue` | ✓ | | Conditional inclusion based on source data value |
| `NLPExtraction` | ✓ | | Value extracted from unstructured text via NLP |
| `LabValueParsing` | | ✓ | Numeric/unit parsing from composite lab result strings |
| `UnitConversion` | | ✓ | Conversion between measurement unit systems |
| `ElevatedLiverEnzyme` | | ✓ | Algorithmic derivation of adverse events from lab data |

---

## Contributing a New Example

New examples are welcome. To maintain consistency:

1. Create a directory named `exampleN/` following the structure above.
2. Include a `README.md` with the scenario description, algorithm, and file inventory.
3. Provide both CSV data files and a companion `.xlsx` workbook.
4. Ensure the `rwd-lineage.xml` passes validation:
   ```bash
   python3 tools/validate.py rwd-lineage examples/exampleN/data/define/rwd-lineage.xml
   ```
5. Ensure full lineage coverage of all SDTM cells:
   ```bash
   python3 tools/validate.py coverage examples/exampleN/data/sdtm examples/exampleN/data/define/rwd-lineage.xml
   ```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for general contribution guidelines.
