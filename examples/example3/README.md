# Example 3 — Medical History (MH) from TCGA-BRCA and MIMIC-IV Real-World Data

This example demonstrates RWD lineage traceability for the **SDTM MH (Medical History)** domain, built by harmonizing two independent public real-world datasets — the TCGA-BRCA cancer genomics program and the MIMIC-IV critical care database — into a single combined MH dataset with cell-level lineage back to both sources.

## Scenario

A screening cohort of breast cancer patients is derived from TCGA-BRCA clinical data, then mapped to the SDTM MH domain. A second, independently-sourced set of MH records is pulled from MIMIC-IV (a pre-mapped Excel extract of ICD-coded malignancy history) for a small cohort of matching patients. The two MH datasets are combined into one target table, and lineage is traced back through each source's own path — a single BCR Biotab flat file for TCGA, and a two-hop path (source database → intermediate Excel extract → output file) for MIMIC.

### Cohort Screening (TCGA-BRCA)

`data/cohort/tcga_brca_cohort_inclusion.txt` / `.xlsx` — 385 subjects selected from 1,099 TCGA-BRCA patients using:

1. **Female** — `gender == 'FEMALE'`
2. **Age** — age at diagnosis between 18 and 60, inclusive
3. **Surgery known** — `surgical_procedure_first` not missing/unknown/discrepant
4. **Chemotherapy recorded** — at least one drug row with `pharmaceutical_therapy_type == 'Chemotherapy'`

The spec's "invasive breast cancer / histological_type" criterion was intentionally **not** applied as a filter — every TCGA-BRCA patient is a breast cancer patient by definition of the dataset, so the criterion is tautological and would not narrow the cohort.

### Target Data

| Table | Columns | Records | Description |
|-------|---------|---------|--------------|
| `MH.txt` | 19 | 394 | Combined SDTM MH domain — 385 TCGA-BRCA subjects + 9 MIMIC-IV subjects |

Column union across the two sources:

- **Shared (14):** `STUDYID`, `DOMAIN`, `USUBJID`, `MHSEQ`, `MHTERM`, `MHDECOD`, `MHCAT`, `MHEVDTYP`, `MHOCCUR`, `MHPRESP`, `MHSTDTC`, `MHDTC`, `VISITNUM`, `VISIT`
- **TCGA-only (3):** `MHSTDY`, `MHSTRTPT`, `MHSTTPT` — blank for MIMIC rows
- **MIMIC-only (2):** `MHSTAT`, `MHDY` — null in the MIMIC source itself, always blank in the combined output

Notable mixed-precision columns: `MHSTDTC`/`MHDTC` hold year-only or date-only values for TCGA (e.g. `2009`, `2011-05-27`) alongside full datetimes for MIMIC (e.g. `2149-01-29T22:09:00`); `MHTERM` holds free-text histological-type strings for TCGA versus raw ICD code strings for MIMIC (e.g. `C50919`).

---

## Lineage Overview

`rwd_lineage_combined_mh_celllevel.xml` contains **3,218 `MapID`** elements tracing every populated cell in the combined MH file back to its source:

- **TCGA path:** single-hop — `nationwidechildrens_org_clinical_patient_brca.txt` (BCR Biotab, tab-delimited, 3-row header: harmonized name / BCR original name / CDE_ID) → `MH.txt`
- **MIMIC path:** two-hop — source PostgreSQL database → intermediate pre-mapped `MH.xlsx` extract → `MH.txt`

A small set of columns (`STUDYID`, `DOMAIN`, `MHSEQ`, `MHCAT`, `MHEVDTYP`, `MHPRESP` for TCGA rows) are hardcoded/assigned constants or derived sequence numbers with no single addressable source cell. These are documented in an `OmittedColumns` block in the lineage file with a spec-gap note, rather than silently mapped — the RWD-Lineage v1 Draft spec has no `AssignedValue`/protocol-origin coordinate type to represent them. Full details are in `reports/rwdl_spec_gaps_combined.txt`.

---

## ⚠️ Schema Version Note

The `rwd_lineage_combined_mh_celllevel.xml` and `define_combined_mh.xml` in this example were built against an earlier reading of the RWD-Lineage Data Standard Specification v1 Draft, **before** this repository's `example1`/`example2` and `tools/validate.py` established the current canonical element names. Specifically:

| This example uses | Repo's current schema (example1/example2) |
|---|---|
| `<rwdl:lineage>` (lowercase root) | `<rwdl:Lineage>` |
| `<rwdl:sourceMetadata>` / `<rwdl:source>` | `<rwdl:SourceMetadata>` / `<rwdl:SourceSystem>` |
| Flat `<rwdl:Column>`-based `OmittedColumns` block | *(no direct equivalent yet)* |

As a result, **`rwd_lineage_combined_mh_celllevel.xml` will not currently pass `tools/validate.py rwd-lineage` or the repo's `rwd-lineage.xsd`** as-is. It's included here as a real-world worked example of the underlying traceability problem (multi-source, mixed-precision, two-hop lineage) and as a concrete case study for the spec-gap issues in `reports/rwdl_spec_gaps_combined.txt`, not as a schema-conformant submission. Reconciling it to the current schema is a follow-up task, not done in this commit.

---

## Contents

```
example3/
├── README.md                                  # This file
├── data/
│   ├── cohort/
│   │   ├── tcga_brca_cohort_inclusion.txt      # 385-subject screening cohort (129 columns)
│   │   └── tcga_brca_cohort_inclusion.xlsx     # Same, as workbook
│   ├── sdtm/
│   │   └── MH.txt          # Combined SDTM MH — 394 rows, 19 columns
│   └── define/
│       ├── define_combined_mh.xml              # Define-XML 2.1 (combined target)
│       ├── define_combined_mh.csv              # Flat rendering of define_combined_mh.xml
│       ├── rwd_lineage_combined_mh_celllevel.xml   # RWD-Lineage — 3,218 MapID elements
│       └── rwd_lineage_combined_mh_celllevel.csv   # Flat rendering of the lineage XML
├── scripts/
│   ├── build_tcga_brca_cohort.py               # Screening cohort build
│   ├── build_tcga_brca_mh_v3.py                # TCGA-only MH build (intermediate step)
│   ├── build_tcga_mimic_combined_mh.py          # Combines TCGA MH + MIMIC MH.xlsx
│   └── build_combined_mh_xmls.py                # Builds define_combined_mh.xml + lineage XML
└── reports/
    ├── cohort_build_summary.txt                # Cohort attrition funnel + criteria detail
    ├── tcga_brca_mh_v3_summary.txt              # TCGA-only MH build summary
    ├── tcga_brca_mh_v3_discrepancies.txt        # MHTERM/MHDECOD discrepancy report (4 subjects)
    ├── tcga_mimic_mh_combined_report.txt        # Combined build report + QC results
    ├── rwdl_spec_gaps_combined.txt              # RWDL v1 Draft spec-gap notes (OmittedColumns rationale)
    └── build_xml_report_combined.txt            # Define-XML / lineage build report
```

---

## Key Concepts Demonstrated

- **Cross-source harmonization**: two structurally different real-world sources (a tab-delimited legacy flat-file export and a pre-mapped Excel extract from a relational database) combined into one SDTM domain via column union, with source-specific columns left blank where the other source has no equivalent.
- **Two-hop lineage**: the MIMIC path traces through an intermediate artifact (`MH.xlsx`) rather than directly from the original source database, illustrating multi-hop provenance.
- **Mixed-precision date handling**: `MHSTDTC`/`MHDTC` hold year-only or date-only values from TCGA alongside full datetimes from MIMIC — handled in Define-XML via `CommentDef` rather than a uniform `DataType`.
- **Honest gap documentation**: columns with no addressable single-cell source (hardcoded constants, derived sequence numbers) are explicitly called out as an `OmittedColumns` block with a spec-gap rationale, instead of being silently omitted or fabricated a source for.
