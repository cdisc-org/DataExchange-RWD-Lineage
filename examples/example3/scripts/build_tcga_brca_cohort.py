"""
Build the TCGA-BRCA screening cohort.

Mirrors the structure of the MIMIC breast_cancer_cohort SQL query, adapted to
the TCGA-BRCA legacy Biotab clinical files. Each inclusion criterion is applied
as a labeled filter step, and attrition is printed at every step for audit.

Inclusion criteria (from tcga-brca_screening_cohort.xlsx spec):
  1. Female        : gender == 'FEMALE'
  2. Age           : age_at_diagnosis between AGE_MIN and AGE_MAX (inclusive)
  3. Surgery       : surgical_procedure_first NOT in sentinel values
  4. Chemotherapy  : has at least one drug row with
                     pharmaceutical_therapy_type == 'Chemotherapy'

Note: the spec's "Invasive breast cancer" row (histological_type) is omitted
because every patient in TCGA-BRCA is a breast cancer patient by dataset
definition -- confirmed with the user.

Outputs:
  - tcga_brca_cohort_inclusion.xlsx : final cohort (all 4 criteria applied)
  - tcga_brca_cohort_no_surgery_filter.xlsx : optional variant with surgery
                     filter removed (toggle via PRODUCE_NO_SURGERY_VARIANT)

Each output contains the full patient-level row for cohort members, with the
original sentinel strings preserved in text columns. Only age is coerced to
numeric for filtering; the original text column is retained alongside.
"""

from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
UPLOADS = Path("/mnt/user-data/uploads")
OUTPUTS = Path("/mnt/user-data/outputs")
OUTPUTS.mkdir(parents=True, exist_ok=True)

PATIENT_FILE = UPLOADS / "nationwidechildrens_org_clinical_patient_brca.txt"
DRUG_FILE    = UPLOADS / "nationwidechildrens_org_clinical_drug_brca.txt"

# Age bounds -- currently inclusive on both ends (matches MIMIC query).
# Change to strict (>, <) by swapping the comparison operators in step 2.
AGE_MIN = 18
AGE_MAX = 60

# Sentinel values that mean "we don't know if/what surgery they had".
# Per spec: surgical_procedure_first NOT in this set.
SURGERY_SENTINELS = {"[Not Available]", "[Unknown]", "[Discrepancy]"}

# Whether to also produce a second cohort file that skips the surgery filter.
PRODUCE_NO_SURGERY_VARIANT = False

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load_bcr_biotab(path: Path) -> pd.DataFrame:
    """
    Legacy TCGA BCR Biotab files have 3 header rows:
      row 0: harmonized column name  <-- the one we want
      row 1: original BCR column name
      row 2: CDE_ID (may be blank / non-numeric for UUIDs and some barcodes)
    Data starts at row 3. Load everything as string to preserve sentinels like
    "[Not Available]" verbatim; numeric coercion happens per-column downstream.
    """
    return pd.read_csv(path, sep="\t", skiprows=[1, 2], dtype=str)


patients = load_bcr_biotab(PATIENT_FILE)
drugs    = load_bcr_biotab(DRUG_FILE)

print(f"Loaded patients: {len(patients):>5} rows, "
      f"{patients['bcr_patient_barcode'].nunique()} unique barcodes")
print(f"Loaded drugs   : {len(drugs):>5} rows, "
      f"{drugs['bcr_patient_barcode'].nunique()} unique barcodes")
print()

# ---------------------------------------------------------------------------
# Parallel numeric column for age (text column stays untouched)
# ---------------------------------------------------------------------------
patients["_age_numeric"] = pd.to_numeric(
    patients["age_at_diagnosis"], errors="coerce"
)

# ---------------------------------------------------------------------------
# Build the cohort step by step, logging attrition
# ---------------------------------------------------------------------------
def log_step(name: str, df: pd.DataFrame) -> None:
    print(f"  after {name:<25} n = {len(df):>5}")


print("Applying inclusion criteria:")
cohort = patients.copy()
log_step("start", cohort)

# Step 1: Female
cohort = cohort[cohort["gender"] == "FEMALE"]
log_step("female", cohort)

# Step 2: Age at diagnosis
cohort = cohort[
    cohort["_age_numeric"].between(AGE_MIN, AGE_MAX, inclusive="both")
]
log_step(f"age {AGE_MIN}-{AGE_MAX}", cohort)

# Step 3: Surgery -- keep only patients with a known surgical procedure
cohort_with_surgery = cohort[
    ~cohort["surgical_procedure_first"].isin(SURGERY_SENTINELS)
    & cohort["surgical_procedure_first"].notna()
]
log_step("surgery known", cohort_with_surgery)

# Step 4: Chemotherapy -- at least one drug row of type 'Chemotherapy'
#
# NOTE: We deliberately did NOT pre-inspect the distribution of values in
# pharmaceutical_therapy_type before writing this filter. The spec specifies
# exact-string equality with 'Chemotherapy', and we are trusting it.
# Consequences: any casing variants (e.g. 'chemotherapy', 'CHEMOTHERAPY') or
# spacing variants in the source data will silently be excluded from the
# cohort. If the final n looks wrong, this is the first place to check.
chemo_barcodes = set(
    drugs.loc[
        drugs["pharmaceutical_therapy_type"] == "Chemotherapy",
        "bcr_patient_barcode",
    ]
)
final = cohort_with_surgery[
    cohort_with_surgery["bcr_patient_barcode"].isin(chemo_barcodes)
]
log_step("chemotherapy", final)

# ---------------------------------------------------------------------------
# Output: drop helper column, write xlsx
# ---------------------------------------------------------------------------
final_out = final.drop(columns=["_age_numeric"])
out_path = OUTPUTS / "tcga_brca_cohort_inclusion.xlsx"
final_out.to_excel(out_path, index=False)
print(f"\nWrote {out_path} ({len(final_out)} patients)")

# Optional second variant: skip surgery filter
if PRODUCE_NO_SURGERY_VARIANT:
    variant = cohort[cohort["bcr_patient_barcode"].isin(chemo_barcodes)]
    variant_out = variant.drop(columns=["_age_numeric"])
    v_path = OUTPUTS / "tcga_brca_cohort_no_surgery_filter.xlsx"
    variant_out.to_excel(v_path, index=False)
    print(f"Wrote {v_path} ({len(variant_out)} patients)")
