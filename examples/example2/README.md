# Example 2

Contains a simplified example of input RWD from EHR lab results and output SDTM.

**SDTM: LB** contains an excerpt of a laboratory test results table derived from raw EHR lab data.
**SDTM: AE** contains an adverse event record for a subject with elevated liver enzymes, derived from the LB domain.
**LabResults** contains raw lab results from an EHR system including LOINC-coded lab tests, visit dates, and results in original units.

### Algorithm

**Laboratory Test Results (LB)**
Lab results from the EHR are mapped to the SDTM LB domain through the following steps:
1. LOINC codes and lab test names from the source are mapped directly to `LBTESTCD`/`LBTEST`
2. Visit dates are mapped directly to `LBDTC`
3. Raw lab result strings (e.g. `0.3507 µkat/L`) are parsed to extract numeric values into `LBORRES`/`LBORRESU` (Lab Value Parsing)
4. Original units (µkat/L) are converted to standard units (U/L) and stored in `LBSTRES`/`LBSTRESU` (Unit Conversion)

**Adverse Events (AE)**
A hepatic enzyme elevation adverse event is derived from the LB domain:
1. LB records with `LBNRIND = HIGH` for ALT, AST, or ALP are identified (Elevated Liver Enzyme)
2. The dictionary-derived term `AEDECOD` is populated from the elevated lab test names
3. The adverse event start date `AESTDTC` is taken from the earliest elevated lab result date


## Contents

```
example2/
├── README.md                        # This file
├── Example2.xlsx                    # Source workbook (SDTM AE, SDTM LB, Source LabResults, RWDLineage-Table)
└── data/
    ├── sdtm/
    │   ├── AE.csv                   # SDTM AE domain (1 record: subject 002 hepatic enzyme elevation)
    │   └── LB.csv                   # SDTM LB domain (12 records: subjects 001/002 x 3 tests x 2 visits)
    ├── source/
    │   └── LabResults.csv           # LabResults table (PATID, LOINC Code, Lab Test, Visit Date, Lab Result)
    └── define/
        ├── define.xml               # Define-XML 2.1 describing the AE and LB domains with RWD lineage reference
        └── rwd-lineage.xml          # RWD-Lineage XML with 99 MapID elements linking source EHR data to SDTM AE and LB
```
