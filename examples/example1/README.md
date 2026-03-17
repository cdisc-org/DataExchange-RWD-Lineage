# Example 1

Contains a simplified example of input RWD from EHR and output SDTM.

**SDTM: CE** contains an excerpt of a CE table with two prespecified events, *hypertension* and *acute myocardial infarction*.
The **source** tables contain source tables corresponding to patient diagnoses, vital signs, and clinical notes.
Notes are modified from mtsamples.com.

### Algorithm

**Hypertension**
Patient experiences *hypertension* after the index event within the followup period:
1. Patient is assigned ICDI0 diagnosis code I10–I16 (Hypertensive diseases)
2. Patient has at least two elevated blood pressure measurements over the course of a 3-month period within the followup period
3. Patient has diagnosed hypertension in clinical notes

**Myocardial Infarction**
Patient experiences *acute myocardial infarction* after the index event within the followup period:
1. Patient is assigned a diagnosis code I21 (Acute myocardial infarction) or I122 (Subsequent ST elevation (STEMI) and non-ST elevation (NSTEMI) myocardial infarction) 
2. Patient has records of acute myocardial infarction in notes within the followup period


## Contents

```
example1/
├── README.md                        # This file
├── Example1.xlsx                    # Source workbook (SDTM CE, Source PT_DX, Source VITALS, Source NOTES, RWDLineage-Table)
└── data/
    ├── sdtm/
    │   └── ce.csv                   # SDTM CE domain (4 records: subjects 001/002 x 2 conditions)
    ├── source/
    │   ├── pt_dx.csv                # EHR diagnoses table (PT_ID, DATE, ICD10, TERM)
    │   ├── vitals.csv               # EHR vitals table (Patno, Date, Vital, Value)
    │   └── notes.csv                # EHR clinical notes table (PT_ID, DATE, TEXT)
    └── define/
        ├── define.xml               # Define-XML 2.1 describing the CE domain with RWD lineage reference
        └── rwd-lineage.xml          # RWD-Lineage XML with 20 MapID elements linking source EHR data to SDTM CE
```
