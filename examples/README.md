# Examples

This directory contains worked examples that demonstrate the [RWD-Lineage Data Standard](../documents/RWD-Lineage_Data_Standard_Specification.md) — a machine-readable CDISC data exchange format for capturing the lineage of Real-World Data (RWD) as it is transformed into SDTM datasets.

Each example provides a complete, self-contained package: source EHR data, target SDTM datasets, a Define-XML 2.1 file with the `rwdl` namespace extension, and a companion `rwd-lineage.xml` file that traces every cell in the SDTM output back to its origin in the source data.

---

## Quick Start

```
examples/
├── README.md                  ← You are here
├── RWD-Lineage-Examples.pdf   ← Slide deck: background, motivation, and example walkthroughs
├── example1/                  ← CE domain: diagnoses, vitals, and clinical notes
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
├── example2/                  ← AE + LB domains: lab results and adverse events
│   ├── README.md
│   ├── Example2.xlsx
│   └── data/
│       ├── define/
│       │   ├── define.xml
│       │   └── rwd-lineage.xml
│       ├── sdtm/
│       │   ├── AE.csv
│       │   └── LB.csv
│       └── source/
│           └── LabResults.csv
└── example3/                  ← MH domain: TCGA-BRCA + MIMIC-IV combined real-world data
    ├── README.md
    ├── data/
    │   ├── cohort/
    │   ├── sdtm/
    │   └── define/
    ├── scripts/
    └── reports/
```

`RWD-Lineage-Examples.pdf` is a presentation deck covering the background and motivation for the standard, the RWD Lineage in Define-XML architecture, and annotated walkthroughs of both examples. It is a good starting point for understanding why the standard exists before reading the XML files.

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

### Example 1 — Clinical Events (CE): Hypertension and Myocardial Infarction

**SDTM domain:** CE (Clinical Events)
**Source tables:** `pt_dx` (ICD-10 diagnoses), `vitals` (blood pressure, BMI), `notes` (free-text clinical notes)
**Subjects:** 2 (001, 002) &nbsp;×&nbsp; 2 prespecified conditions = 4 CE records
**Lineage entries:** 20 `<rwdl:MapID>` elements

This example models two prespecified clinical events — **hypertension** and **acute myocardial infarction** — and shows how each `CEOCCUR` determination draws on multiple evidence sources:

| `MethodDefOID` | Count | Description |
|----------------|-------|-------------|
| *(none — direct map)* | 7 | Source record directly supports the target determination; no algorithmic transformation |
| `MT.AFTERIDXDATE` | 5 | Temporal filter — include only source records dated on or after the patient's study index date |
| `MT.NLPEXTRACTION` | 5 | Structured data extracted from free-text clinical notes via NLP |
| `MT.FILTERBYVAL` | 3 | Source vitals filtered by vital type to match the target clinical event |

**Key concepts illustrated:**
- **Multi-source evidence:** a single SDTM cell (`CEOCCUR`) can trace to diagnosis codes, vital-sign measurements, *and* NLP-extracted findings simultaneously.
- **Prespecified event algorithms:** the lineage captures each step of a composite clinical algorithm (diagnosis code check → temporal filter → vitals threshold → NLP confirmation).
- **NLP lineage:** free-text clinical notes are a legitimate source, with `MT.NLPEXTRACTION` referencing the Define-XML `MethodDef` that documents the extraction logic.

→ See [`example1/README.md`](example1/README.md) for the full algorithm definitions.

---

### Example 2 — Labs (LB) and Adverse Events (AE): Elevated Liver Enzyme

**SDTM domains:** LB (Laboratory Test Results), AE (Adverse Events)
**Source table:** `LabResults` (LOINC-coded lab results with raw values in original units)
**Subjects:** 2 (001, 002) &nbsp;×&nbsp; 3 liver-enzyme tests &nbsp;×&nbsp; 2 visits = 12 LB records + 1 AE record
**Lineage entries:** 101 `<rwdl:MapID>` elements

This example traces LOINC-coded EHR lab data through unit conversion into the SDTM LB domain, then derives an adverse event (hepatic enzyme elevation) in the AE domain:

| `MethodDefOID` | Count | Description |
|----------------|-------|-------------|
| *(none — direct map)* | 39 | LOINC code → `LBTEST`, visit date → `LBDTC`, `AETERM` → `AEDECOD`/`AELLTCD`, etc. |
| `MT.LABVALPARSING` | 24 | Parse composite result strings (e.g., `"0.3507 µkat/L"`) into numeric value and unit components |
| `MT.UNITCONV` | 24 | Convert original units (µkat/L) to standard units (U/L); results in `LBSTRES`/`LBSTRESU` |
| `MT.ELEVATEDLIVERENZYME` | 12 | Evaluate ALT/AST/ALP against reference range upper limits to derive the AE record |

**Key concepts illustrated:**
- **Multi-step transformations:** a single lab result passes through parsing → conversion → standardization, each step a separate lineage entry.
- **Cross-domain derivation:** the AE domain record is derived from the LB domain, which is itself derived from source EHR data — the lineage captures both hops.
- **High coverage density:** 101 lineage entries across 13 SDTM records demonstrates cell-level traceability at scale, including every standard-range indicator (`LBSTNRLO`, `LBSTNRHI`, `LBNRIND`).

→ See [`example2/README.md`](example2/README.md) for the full algorithm definitions.

---

### Example 3 — Medical History (MH): TCGA-BRCA + MIMIC-IV Combined Real-World Data

**SDTM domain:** MH (Medical History)
**Source data:** TCGA-BRCA BCR Biotab legacy portal export (single-hop) and a pre-mapped MIMIC-IV `MH.xlsx` extract from a PostgreSQL source database (two-hop)
**Subjects:** 385 TCGA-BRCA + 9 MIMIC-IV = 394 combined MH records
**Lineage entries:** 3,218 `MapID` elements

This example combines two independently-sourced real-world datasets — a cancer genomics program and a critical-care database — into a single SDTM MH domain via column union, and traces lineage through each source's own path, including a two-hop path for the MIMIC side (source database → intermediate Excel extract → output).

**Note:** this example's `rwd-lineage.xml` predates the schema conventions used in Examples 1–2 and will not currently pass `tools/validate.py`. See [`example3/README.md`](example3/README.md#️-schema-version-note) for details.

→ See [`example3/README.md`](example3/README.md) for the full scenario, cohort screening criteria, and spec-gap notes.

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

A standard [CDISC Define-XML 2.1](https://www.cdisc.org/standards/data-exchange/define-xml) file extended with two additions:

1. **`MethodDef` elements** — one per non-direct transformation, describing the algorithm applied. Each `MethodDefOID` in `rwd-lineage.xml` resolves to one of these.
2. **`rwdl:LineageRef`** — points to the companion lineage file via a standard `def:leaf` reference.

```xml
<ODM xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0"
     xmlns:def="http://www.cdisc.org/ns/def/v2.1" ...>
  <Study>
    <MetaDataVersion>

      <!-- Transformation definitions referenced by MethodDefOID in rwd-lineage.xml -->
      <MethodDef OID="MT.AFTERIDXDATE" Name="After Index Date filter" Type="Computation">
        <Description>
          <TranslatedText xml:lang="en">Include source records only when the source date
          falls on or after the patient's index date.</TranslatedText>
        </Description>
      </MethodDef>
      <!-- ... additional MethodDef elements ... -->

      <!-- Lineage file reference: def:leaf declares the file; rwdl:LineageRef points to it -->
      <def:leaf ID="LF.RWDLINEAGE" xlink:href="rwd-lineage.xml">
        <def:title>RWD Lineage Traceability</def:title>
      </def:leaf>
      <rwdl:LineageRef leafID="LF.RWDLINEAGE"/>

      <!-- Standard ItemGroupDef / ItemDef elements follow -->
    </MetaDataVersion>
  </Study>
</ODM>
```

### `rwd-lineage.xml`

The core deliverable. The document has two top-level layers inside `rwdl:Lineage`:

- **`rwdl:SourceMetadata`** (optional) — assertions about the source systems: their names, data models, and the controlled terminologies their coded values are encoded in.
- **`rwdl:LineageTrail`** — the forensic record: an array of `rwdl:MapID` elements, each a Source→Target pair.

Each `rwdl:MapID` element represents one source-to-target data point mapping:

```xml
<rwdl:Lineage xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">

  <!-- LAYER 1: Assertions about the source systems -->
  <rwdl:SourceMetadata>
    <rwdl:SourceSystem OID="SRC.CSV.1"
                 Name="Example 1 Clinical Source CSV Files"
                 Description="CSV exports from clinical source system">
      <rwdl:ExternalCodeList Dictionary="ICD-10-CM" Version="2024"
                             AppliesTo="pt_dx.csv ICD10"/>
    </rwdl:SourceSystem>
  </rwdl:SourceMetadata>

  <!-- LAYER 2: Forensic trail — Source -> Target pairs -->
  <rwdl:LineageTrail>

    <!-- Direct map: no MethodDefOID -->
    <rwdl:MapID UUID="35060134-fc2f-4cdf-9abe-491924739bd5">
      <rwdl:Source>
        <rwdl:Coordinate Storage="FILESYSTEM" Structure="TABULAR" Format="CSV">
          <rwdl:URI>.../source/pt_dx.csv</rwdl:URI>
          <rwdl:RowIndex>4</rwdl:RowIndex>
          <rwdl:ColumnName>ICD10</rwdl:ColumnName>
        </rwdl:Coordinate>
      </rwdl:Source>
      <rwdl:Target>
        <rwdl:Coordinate Storage="FILESYSTEM" Structure="TABULAR" Format="CSV">
          <rwdl:URI>.../sdtm/ce.csv</rwdl:URI>
          <rwdl:RowIndex>2</rwdl:RowIndex>
          <rwdl:ColumnName>CEOCCUR</rwdl:ColumnName>
        </rwdl:Coordinate>
      </rwdl:Target>
    </rwdl:MapID>

    <!-- Non-direct map: MethodDefOID references the MethodDef in define.xml -->
    <rwdl:MapID UUID="7e376beb-7dad-4f5c-a212-88283ac22eba"
                MethodDefOID="MT.AFTERIDXDATE">
      <rwdl:Source>
        <rwdl:Coordinate Storage="FILESYSTEM" Structure="TABULAR" Format="CSV">
          <rwdl:URI>.../source/pt_dx.csv</rwdl:URI>
          <rwdl:RowIndex>4</rwdl:RowIndex>
          <rwdl:ColumnName>DATE</rwdl:ColumnName>
        </rwdl:Coordinate>
      </rwdl:Source>
      <rwdl:Target>
        <rwdl:Coordinate Storage="FILESYSTEM" Structure="TABULAR" Format="CSV">
          <rwdl:URI>.../sdtm/ce.csv</rwdl:URI>
          <rwdl:RowIndex>2</rwdl:RowIndex>
          <rwdl:ColumnName>CEOCCUR</rwdl:ColumnName>
        </rwdl:Coordinate>
      </rwdl:Target>
    </rwdl:MapID>

    <!-- ... -->
  </rwdl:LineageTrail>

</rwdl:Lineage>
```

Key attributes and elements are documented in the [RWD-Lineage Data Standard Specification](../documents/RWD-Lineage_Data_Standard_Specification.md).

### `ExampleN.xlsx`

A companion Excel workbook containing all source tables, SDTM output tables, and the lineage mappings in tabular form. This is provided for human review and is not a normative artifact — the XML files are the machine-readable standard.

---

## Transformations Across Examples

Transformations are expressed via the `MethodDefOID` attribute on `rwdl:MapID`, which references a `MethodDef` element in `define.xml`. Direct maps — where the source record directly supports the target without an algorithmic transformation — carry no `MethodDefOID`.

| `MethodDefOID` | Example 1 | Example 2 | Description |
|----------------|-----------|-----------|-------------|
| *(none)* | ✓ | ✓ | Direct map — no transformation applied |
| `MT.AFTERIDXDATE` | ✓ | | Temporal filter relative to the patient's study index date |
| `MT.FILTERBYVAL` | ✓ | | Conditional inclusion based on source vital type value |
| `MT.NLPEXTRACTION` | ✓ | | Concept extracted from free-text clinical notes via NLP |
| `MT.LABVALPARSING` | | ✓ | Numeric value and unit parsed from a composite lab result string |
| `MT.UNITCONV` | | ✓ | Conversion between measurement unit systems (µkat/L → U/L) |
| `MT.ELEVATEDLIVERENZYME` | | ✓ | Algorithmic derivation of an AE record from elevated lab results |

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
