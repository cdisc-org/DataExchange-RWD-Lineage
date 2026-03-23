# Example 1 — Clinical Events from EHR Diagnoses, Vitals, and Notes

This example demonstrates RWD lineage traceability for the **SDTM CE (Clinical Events)** domain, where the occurrence of two prespecified conditions — hypertension and acute myocardial infarction — is determined by combining evidence from three distinct EHR source tables: structured diagnosis codes, vital-sign measurements, and free-text clinical notes.

## Scenario

A study tracks two prespecified clinical events across two subjects. Each event's occurrence (`CEOCCUR = Y/N`) is determined by a multi-source algorithm that draws on ICD-10 diagnosis codes, blood pressure readings, and NLP-extracted findings from clinical notes. The lineage captures every piece of evidence that contributes to each determination.

### Source Data

| Table | Columns | Records | Description |
|-------|---------|---------|-------------|
| `pt_dx.csv` | `PT_ID`, `DATE`, `ICD10`, `TERM` | 8 | ICD-10 diagnosis codes from the EHR problem list |
| `vitals.csv` | `Patno`, `Date`, `Vital`, `Value` | 8 | Vital signs including blood pressure and BMI |
| `notes.csv` | `PT_ID`, `DATE`, `TEXT` | 72 | Free-text clinical notes (modified from [mtsamples.com](https://mtsamples.com)) |

### Target Data

| Table | Columns | Records | Description |
|-------|---------|---------|-------------|
| `ce.csv` | `USUBJID`, `CESEQ`, `CETERM`, `CEPRESP`, `CEOCCUR` | 4 | SDTM CE domain — 2 subjects × 2 prespecified conditions |

### SDTM Output Summary

| USUBJID | CESEQ | CETERM | CEPRESP | CEOCCUR |
|---------|-------|--------|---------|---------|
| 001 | 1 | MYOCARDIAL INFARCTION | Y | Y |
| 001 | 2 | HYPERTENSION | Y | Y |
| 002 | 1 | MYOCARDIAL INFARCTION | Y | N |
| 002 | 2 | HYPERTENSION | Y | Y |

---

## Algorithms

### Hypertension

Patient experiences *hypertension* after the index event within the follow-up period:

1. Patient is assigned an ICD-10 diagnosis code I10–I16 (Hypertensive diseases)
2. Patient has at least two elevated blood pressure measurements over the course of a 3-month period within the follow-up period
3. Patient has diagnosed hypertension in clinical notes

### Acute Myocardial Infarction

Patient experiences *acute myocardial infarction* after the index event within the follow-up period:

1. Patient is assigned a diagnosis code I21 (Acute myocardial infarction) or I22 (Subsequent ST elevation (STEMI) and non-ST elevation (NSTEMI) myocardial infarction)
2. Patient has records of acute myocardial infarction in notes within the follow-up period

---

## Lineage Overview

The `rwd-lineage.xml` file contains **20 `<MapID>` elements** tracing source EHR data to SDTM CE. All 20 mappings target the `CEOCCUR` column, reflecting the fact that the clinical event occurrence flag is the outcome of a multi-source evidence evaluation.

### Transformation Types

| Type | Count | Description |
|------|-------|-------------|
| `DirectMap` | 7 | One-to-one value mapping (e.g., ICD-10 code or vital type used as evidence) |
| `AfterIndexDate` | 5 | Temporal filter confirming the source event falls within the study follow-up window |
| `NLPExtraction` | 5 | Structured finding extracted from free-text clinical notes |
| `FilterByValue` | 3 | Conditional filter based on source value (e.g., blood pressure exceeding a threshold) |

### Lineage by CE Record

**Subject 001 — Myocardial Infarction (`CEOCCUR = Y`, CE row 1)**
Three lineage entries trace to `pt_dx.csv` row 1 (ICD-10 code I21.3): a `DirectMap` on the ICD-10 code, a `DirectMap` on the diagnosis term, and an `AfterIndexDate` filter on the date. Two additional `NLPExtraction` entries link to `notes.csv` confirming the finding in clinical text.

**Subject 002 — Hypertension (`CEOCCUR = Y`, CE row 4)**
Fifteen lineage entries converge on this single cell from all three source tables. Diagnosis evidence comes from `pt_dx.csv` (3 entries: ICD-10 code, term, and date filter). Blood pressure evidence comes from `vitals.csv` across three visits (9 entries: 3 rows × vital type + value filter + date filter each). NLP evidence comes from `notes.csv` (3 entries across 2 note records).

---

## Contents

```
example1/
├── README.md                        # This file
├── Example1.xlsx                    # Companion workbook (SDTM CE, Source PT_DX, Source VITALS, Source NOTES, RWDLineage-Table)
└── data/
    ├── sdtm/
    │   └── ce.csv                   # SDTM CE domain (4 records: subjects 001/002 × 2 conditions)
    ├── source/
    │   ├── pt_dx.csv                # EHR diagnoses table — 8 rows (PT_ID, DATE, ICD10, TERM)
    │   ├── vitals.csv               # EHR vitals table — 8 rows (Patno, Date, Vital, Value)
    │   └── notes.csv                # EHR clinical notes — 72 rows (PT_ID, DATE, TEXT)
    └── define/
        ├── define.xml               # Define-XML 2.1 with rwdl namespace extension referencing rwd-lineage.xml
        └── rwd-lineage.xml          # RWD-Lineage XML — 20 MapID elements linking source EHR data to SDTM CE
```

---

## Validation

From the repository root:

```bash
# Validate the RWD-Lineage XML structure
python3 tools/validate.py rwd-lineage examples/example1/data/define/rwd-lineage.xml

# Validate the Define-XML against CDISC XSD (requires lxml)
python3 tools/validate.py define-xml examples/example1/data/define/define.xml

# Check that every SDTM cell has lineage coverage
python3 tools/validate.py coverage examples/example1/data/sdtm examples/example1/data/define/rwd-lineage.xml
```

---

## Key Concepts Demonstrated

- **Multi-source evidence**: A single SDTM cell (`CEOCCUR`) traces back to diagnosis codes, vital signs, *and* NLP-extracted findings — the lineage captures all contributing sources.
- **Composite algorithms**: The hypertension determination requires evidence from all three source types; the lineage documents each step.
- **NLP as a lineage source**: Free-text clinical notes are a first-class source in the lineage, with `NLPExtraction` documenting the transformation from unstructured text to structured evidence.
- **Temporal filtering**: `AfterIndexDate` entries explicitly record that a source event was validated against the study's follow-up window.
