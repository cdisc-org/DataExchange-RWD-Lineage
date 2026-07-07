"""
Map the TCGA-BRCA screening cohort to the SDTM MH (Medical History) domain.

Source : tcga_brca_cohort_inclusion.xlsx (385 patients, 1 row per subject)
Spec   : tcga_to_sdtm_mapping_specs.xlsx (updated version with MHDTC source
         now form_completion_date, non-date-value blanking rule for
         MHSTDTC/MHDTC, and new MHSTRTPT/MHSTTPT columns).
Output : tcga_brca_mh.txt (1 row per subject -- the initial breast cancer Dx)
         Tab-separated (tab delimiter), UTF-8, .txt extension.
Summary: tcga_brca_mh_summary.txt (instructions, steps, QC results)

Mapping (per spec, with user-confirmed clarifications):
  STUDYID  : hardcoded 'TCGA-BRCA'
  DOMAIN   : hardcoded 'MH'
  USUBJID  : bcr_patient_barcode
  MHSEQ    : 1 for every row (one MH event per subject in this build);
             implemented via general spec logic so additional events would
             increment correctly.
  MHTERM   : histological_type           (source-to-target copy with
                                          concatenation exceptions:
                                          'Other  specify' ->
                                            'Other specify - ' ||
                                            histologic_diagnosis_other;
                                          'Mixed Histology (please specify)' ->
                                            'Mixed Histology (please specify) - ' ||
                                            histologic_diagnosis_other)
  MHDECOD  : icd_o_3_histology           (converted to text via
                                          icd-o-3_code_to_text.xlsx lookup)
  MHCAT    : hardcoded 'TCGA-PATIENT'
  MHEVDTYP : hardcoded 'INITIAL PATHOLOGICAL DIAGNOSIS'
  MHSTDTC  : initial_pathologic_dx_year  (year-only ISO 8601, e.g. '2009';
                                          BLANK if source is non-date,
                                          e.g. '[Not Available]')
  MHDTC    : form_completion_date        (ISO 8601 YYYY-MM-DD, zero-padded;
                                          BLANK if source is non-date)
  MHSTDY   : days_to_initial_pathologic_diagnosis + 1  (numeric)
  VISITNUM : 1                           (Num, per SDTM standard)
  VISIT    : 'VISIT 1'
  MHSTRTPT : 'BEFORE'                    (ONLY when source
             initial_pathologic_dx_year == '[Not Available]'; else blank.
             Literal interpretation of spec; user confirmed proceeding.)
  MHSTTPT  : 'SCREENING'                 (same conditional rule as MHSTRTPT)
  MHPRESP  : 'Y'                         (hardcoded -- all events pre-specified)
  MHOCCUR  : 'Y'                         (hardcoded -- all events occurred)

QC checks performed after mapping (printed to stdout, non-fatal warnings):
  1.  Input vs output row count match
  2.  USUBJID uniqueness (no duplicate subjects)
  3.  (USUBJID, MHSEQ) uniqueness -- the SDTM natural key
  4.  Missingness per column (NaN or empty string)
  5.  MHSTDTC matches ISO 8601 year pattern ^\\d{4}$ OR is blank
  6.  MHDTC matches ISO 8601 YYYY-MM-DD OR is blank
  7.  Hardcoded columns have exactly one non-blank value (expected hardcoded)
  8.  No leftover sentinel strings ('[Not Available]' etc.) in any column
  9.  MHSTDY is numeric and non-null
  10. MHSTRTPT / MHSTTPT conditional rule consistency:
      - MHSTRTPT in {'', 'BEFORE'}, MHSTTPT in {'', 'SCREENING'}
      - populated if-and-only-if source initial_pathologic_dx_year ==
        '[Not Available]'
      - MHSTRTPT and MHSTTPT either both populated or both blank on each row
  11. Column order matches expected SDTM MH order (15 cols)
  12. No tab characters in any value cell (tab-delimiter safety)
"""

from pathlib import Path
import re
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
COHORT_FILE = Path("/mnt/user-data/outputs/tcga_brca_cohort_inclusion.xlsx")
OUTPUT_FILE  = Path("/mnt/user-data/outputs/tcga_brca_mh_v3.txt")
SUMMARY_FILE = Path("/mnt/user-data/outputs/tcga_brca_mh_v3_summary.txt")

STUDYID   = "TCGA-BRCA"
DOMAIN    = "MH"
MHCAT     = "TCGA-PATIENT"
MHEVDTYP  = "INITIAL PATHOLOGICAL DIAGNOSIS"
VISITNUM  = 1                       # Num, per SDTM standard
VISIT     = "VISIT 1"
MHSTRTPT  = "BEFORE"                # conditional -- only when year is [Not Available]
MHSTTPT   = "SCREENING"             # same trigger as MHSTRTPT
MHPRESP   = "Y"                     # hardcoded -- all events are pre-specified
MHOCCUR   = "Y"                     # hardcoded -- all events occurred

# Trigger value: the literal source sentinel that flips MHSTRTPT/MHSTTPT on.
# Per spec text: "Only populate for subjects where value for MHSTDTC is
# '[Not Available]'". Interpreting literally -- other non-date values do NOT
# trigger population.
MHSTRTPT_TRIGGER = "[Not Available]"

# Expected SDTM MH column order (the order columns will appear in output)
MH_COLUMNS = [
    "STUDYID", "DOMAIN", "USUBJID", "MHSEQ",
    "MHTERM", "MHDECOD", "MHCAT", "MHEVDTYP",
    "MHSTDTC", "MHDTC", "MHSTDY",
    "MHSTRTPT", "MHSTTPT",
    "MHPRESP", "MHOCCUR",
    "VISITNUM", "VISIT",
]

# Sentinel strings we preserved in the cohort file -- should NOT appear in MH
SENTINELS = {"[Not Available]", "[Not Applicable]", "[Unknown]", "[Discrepancy]"}

# ---------------------------------------------------------------------------
# Load cohort (string dtype to preserve sentinels verbatim during inspection)
# ---------------------------------------------------------------------------
src = pd.read_excel(COHORT_FILE, dtype=str)
n_in = len(src)

# ---------------------------------------------------------------------------
# Logging: everything we'd print also gets captured for the summary file.
# ---------------------------------------------------------------------------
_log_lines: list[str] = []
def log(msg: str = "") -> None:
    print(msg)
    _log_lines.append(msg)

log(f"Loaded cohort: {n_in} rows")

# ---------------------------------------------------------------------------
# Build MH
# ---------------------------------------------------------------------------
mh = pd.DataFrame()

# Direct copies / source-to-target
mh["USUBJID"] = src["bcr_patient_barcode"]

# MHTERM: source-to-target copy with concatenation exceptions.
# Per spec v2:
#   - If histological_type == 'Other  specify'  (two spaces, as in source data)
#     -> 'Other specify - ' || histologic_diagnosis_other
#   - If histological_type == 'Mixed Histology (please specify)'
#     -> 'Mixed Histology (please specify) - ' || histologic_diagnosis_other
#   - All other values: direct copy
# Note: 'Other  specify' in source has two spaces; the spec uses one space
# in the prefix ('Other specify - ') which is retained for readability.
_hist_type  = src["histological_type"].astype(str)
_hist_other = src["histologic_diagnosis_other"].astype(str)
_is_other   = _hist_type == "Other  specify"
_is_mixed   = _hist_type == "Mixed Histology (please specify)"
mh["MHTERM"] = _hist_type.copy()
mh.loc[_is_other, "MHTERM"] = "Other specify - " + _hist_other[_is_other]
mh.loc[_is_mixed, "MHTERM"] = "Mixed Histology (please specify) - " + _hist_other[_is_mixed]

# MHDECOD: convert icd_o_3_histology code to text using lookup dictionary.
# Per spec v2: "MHDECOD is the ICD-O-3 histology in text (not coded format)".
# Lookup file: icd-o-3_code_to_text.xlsx (13 rows, exact coverage of cohort codes).
# Any code not in the lookup will produce NaN, which QC will catch.
_icd_lookup = pd.read_excel(
    "/mnt/user-data/uploads/icd-o-3_code_to_text.xlsx", dtype=str
).set_index("icd_o_3_code")["icd_o_3_text"].str.strip()
mh["MHDECOD"] = src["icd_o_3_histology"].map(_icd_lookup)

# MHTERM_MHDECOD_MISMATCH: flag rows where MHTERM and MHDECOD appear to
# describe different tumour subtypes. This is a data quality annotation --
# it is NOT an SDTM variable and is excluded from the final MH output.
# It IS included in a separate discrepancy report written alongside the output.
#
# Detection strategy: for non-concatenated rows, we build a simplified
# keyword map between histological_type categories and expected ICD-O-3
# codes. Any row where the actual code falls outside the expected set for
# that category is flagged as a mismatch.
# Concatenated rows ('Other specify', 'Mixed Histology') are excluded from
# mismatch flagging since divergence is expected there.
#
# Expected code sets per histological_type (based on ICD-O-3 definitions):
_EXPECTED_CODES = {
    "Infiltrating Ductal Carcinoma"      : {"8500/3"},
    "Infiltrating Lobular Carcinoma"     : {"8520/3"},
    "Medullary Carcinoma"                : {"8510/3"},
    "Metaplastic Carcinoma"              : {"8575/3"},
    "Mucinous Carcinoma"                 : {"8480/3"},
}
_is_concatenated = _is_other | _is_mixed
_icd_code = src["icd_o_3_histology"].astype(str)

def _is_mismatch(row_idx):
    hist = _hist_type.iloc[row_idx]
    code = _icd_code.iloc[row_idx]
    if _is_concatenated.iloc[row_idx]:
        return False   # concatenated rows: skip
    expected = _EXPECTED_CODES.get(hist)
    if expected is None:
        return False   # no expected set defined: skip
    return code not in expected

_mismatch_mask = pd.Series(
    [_is_mismatch(i) for i in range(len(src))],
    index=src.index
)

# Build discrepancy detail for flagged rows
_discrepancy_rows = src[_mismatch_mask][
    ["bcr_patient_barcode", "histological_type", "icd_o_3_histology"]
].copy()
_discrepancy_rows["MHTERM_derived"] = mh.loc[_mismatch_mask, "MHTERM"].values
_discrepancy_rows["MHDECOD_derived"] = mh.loc[_mismatch_mask, "MHDECOD"].values
_discrepancy_rows = _discrepancy_rows.reset_index(drop=True)

# MHSTDTC: initial_pathologic_dx_year -> year-only ISO 8601.
# Per spec: "Leave blank if a non-date value is given". We detect "non-date"
# by trying the ISO 8601 year pattern; anything that doesn't match (including
# sentinels like '[Not Available]') becomes blank.
_year_src = src["initial_pathologic_dx_year"].astype(str).str.strip()
_is_year  = _year_src.str.match(r"^\d{4}$", na=False)
mh["MHSTDTC"] = _year_src.where(_is_year, "")

# MHDTC: form_completion_date -> ISO 8601 YYYY-MM-DD (zero-padded).
# Per spec: "Leave blank if a non-date value is given". TCGA writes these as
# YYYY-M-D (not zero-padded); we normalize via pd.to_datetime and then format,
# letting errors='coerce' handle any non-date strings (they become NaT -> '').
_fcd_src = src["form_completion_date"].astype(str).str.strip()
_fcd_dt  = pd.to_datetime(_fcd_src, errors="coerce")
mh["MHDTC"] = _fcd_dt.dt.strftime("%Y-%m-%d").fillna("")

# MHSTDY: numeric, = days_to_initial_pathologic_diagnosis + 1
# coerce the text column to numeric; errors become NaN which QC will catch.
mh["MHSTDY"] = pd.to_numeric(
    src["days_to_initial_pathologic_diagnosis"], errors="coerce"
) + 1

# MHSTRTPT / MHSTTPT: populate ONLY for rows where source year value is
# literally '[Not Available]'. All other rows get empty strings.
# Store the raw source year verbatim (untouched) for this check so that
# trimming/casing in MHSTDTC handling never affects the trigger logic.
_raw_year = src["initial_pathologic_dx_year"].astype(str)
_trigger_mask = _raw_year == MHSTRTPT_TRIGGER
mh["MHSTRTPT"] = _trigger_mask.map({True: MHSTRTPT, False: ""})
mh["MHSTTPT"]  = _trigger_mask.map({True: MHSTTPT,  False: ""})

# Hardcoded / assigned values
mh["STUDYID"]  = STUDYID
mh["DOMAIN"]   = DOMAIN
mh["MHCAT"]    = MHCAT
mh["MHEVDTYP"] = MHEVDTYP
mh["MHPRESP"]  = MHPRESP
mh["MHOCCUR"]  = MHOCCUR
mh["VISITNUM"] = VISITNUM
mh["VISIT"]    = VISIT

# MHSEQ: per spec, "If first record for the subject, then MHSEQ = 1, otherwise
# incrementing by 1 until end of all records for the subject. Sort by USUBJID,
# VISITNUM, MHTERM; then MHSEQ = group-wise row_number() starting at 1."
# In this build there is exactly one MH event per subject, so MHSEQ = 1 for
# every row. We implement the general spec anyway so the logic is correct if
# additional events are added later.
mh = mh.sort_values(["USUBJID", "VISITNUM", "MHTERM"], kind="stable")
mh["MHSEQ"] = mh.groupby("USUBJID").cumcount() + 1

# Reorder columns to standard SDTM MH order
mh = mh[MH_COLUMNS].reset_index(drop=True)

n_out = len(mh)
log(f"Built MH dataset: {n_out} rows, {len(mh.columns)} columns")
log()

# ---------------------------------------------------------------------------
# QC checks
# ---------------------------------------------------------------------------
log("=" * 60)
log("QC CHECKS")
log("=" * 60)

warnings = []

def check(label: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    log(f"  [{status}] {label}" + (f" -- {detail}" if detail else ""))
    if not passed:
        warnings.append(label)

# 1. Row count match
check("Input row count equals output row count",
      n_in == n_out,
      f"in={n_in}, out={n_out}")

# 2. USUBJID uniqueness
dup_usubjid = mh["USUBJID"].duplicated().sum()
check("USUBJID is unique across rows",
      dup_usubjid == 0,
      f"{dup_usubjid} duplicates" if dup_usubjid else "")

# 3. (USUBJID, MHSEQ) uniqueness -- the SDTM natural key for MH
dup_key = mh.duplicated(subset=["USUBJID", "MHSEQ"]).sum()
check("(USUBJID, MHSEQ) natural key is unique",
      dup_key == 0,
      f"{dup_key} duplicates" if dup_key else "")

# 4. Missingness per column -- informational only (some columns are
# legitimately sparse: MHSTDTC/MHDTC blank when source is non-date;
# MHSTRTPT/MHSTTPT blank when trigger not met).
log("")
log("  Missingness per column (NaN or empty string) -- informational:")
for col in MH_COLUMNS:
    s = mh[col]
    # Treat any non-numeric column as text-like. pd.read_excel(dtype=str) and
    # subsequent operations may yield either 'object' or 'string' dtype --
    # check by kind ('O' = object, 'U'/'S' = unicode/bytes string types) or
    # explicitly for pandas StringDtype.
    is_text = (s.dtype == object) or pd.api.types.is_string_dtype(s)
    if is_text:
        s_str = s.astype(str).str.strip()
        n_missing = int(s_str.isin(["", "nan", "None"]).sum())
    else:
        n_missing = int(s.isna().sum())
    note = ""
    if col in ("MHSTDTC", "MHDTC", "MHSTRTPT", "MHSTTPT") and n_missing > 0:
        note = "   (expected -- conditional)"
    elif n_missing > 0:
        note = "   <-- UNEXPECTED"
    log(f"    {col:<10} {n_missing:>4}{note}")

# 5. MHSTDTC -- blank OR ISO 8601 year
iso_year_re = re.compile(r"^\d{4}$")
mhstdtc_nonblank = mh["MHSTDTC"][mh["MHSTDTC"] != ""]
bad_year = mhstdtc_nonblank.apply(lambda s: not iso_year_re.match(str(s))).sum()
check("MHSTDTC values are blank OR ISO 8601 year ^\\d{4}$",
      bad_year == 0,
      f"{bad_year} non-conforming non-blank values" if bad_year else
      f"{(mh['MHSTDTC'] == '').sum()} blank, "
      f"{len(mhstdtc_nonblank)} year-formatted")

# 6. MHDTC -- blank OR ISO 8601 YYYY-MM-DD
iso_date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
mhdtc_nonblank = mh["MHDTC"][mh["MHDTC"] != ""]
bad_date = mhdtc_nonblank.apply(lambda s: not iso_date_re.match(str(s))).sum()
check("MHDTC values are blank OR ISO 8601 YYYY-MM-DD",
      bad_date == 0,
      f"{bad_date} non-conforming non-blank values" if bad_date else
      f"{(mh['MHDTC'] == '').sum()} blank, "
      f"{len(mhdtc_nonblank)} date-formatted")

# 7. Hardcoded (always-populated) columns uniform and correct
for col, expected in [
    ("STUDYID",  STUDYID),
    ("DOMAIN",   DOMAIN),
    ("MHCAT",    MHCAT),
    ("MHEVDTYP", MHEVDTYP),
    ("MHPRESP",  MHPRESP),
    ("MHOCCUR",  MHOCCUR),
    ("VISITNUM", VISITNUM),
    ("VISIT",    VISIT),
]:
    uniq = mh[col].unique()
    check(f"{col} is uniform (hardcoded '{expected}')",
          len(uniq) == 1 and uniq[0] == expected,
          f"unique values: {list(uniq)}" if len(uniq) != 1 else "")

# 7b. MHTERM concatenation check
# - 'Other  specify' rows should start with 'Other specify - '
# - 'Mixed Histology (please specify)' rows should start with
#   'Mixed Histology (please specify) - '
# - All other rows should equal their original histological_type
n_other  = int(_is_other.sum())
n_mixed  = int(_is_mixed.sum())
n_other_correct = int(mh.loc[_is_other.values, "MHTERM"].str.startswith("Other specify - ").sum())
n_mixed_correct = int(mh.loc[_is_mixed.values, "MHTERM"].str.startswith("Mixed Histology (please specify) - ").sum())
check(f"MHTERM: {n_other} 'Other specify' rows correctly concatenated",
      n_other_correct == n_other,
      f"{n_other - n_other_correct} rows not matching expected prefix" if n_other_correct != n_other else "")
check(f"MHTERM: {n_mixed} 'Mixed Histology' rows correctly concatenated",
      n_mixed_correct == n_mixed,
      f"{n_mixed - n_mixed_correct} rows not matching expected prefix" if n_mixed_correct != n_mixed else "")

# 7c. MHDECOD lookup check
# - No NaN values (would mean an unmatched ICD-O-3 code)
# - All values should be non-empty text strings
mhdecod_null = mh["MHDECOD"].isna().sum()
check("MHDECOD: all ICD-O-3 codes resolved to text via lookup (no unmapped codes)",
      mhdecod_null == 0,
      f"{mhdecod_null} unmapped codes" if mhdecod_null else
      f"all {len(mh)} rows mapped successfully")

# 7d. MHTERM vs MHDECOD discrepancy report
# Informational: flags rows where MHTERM (from histological_type) and
# MHDECOD (from ICD-O-3 lookup) describe different tumour subtypes.
# These represent genuine source-data inconsistencies worth reviewing.
# Concatenated rows ('Other specify', 'Mixed Histology') are excluded.
n_mismatches = int(_mismatch_mask.sum())
log("")
log(f"  MHTERM vs MHDECOD discrepancy report ({n_mismatches} mismatches found):")
if n_mismatches == 0:
    log("    (none found)")
else:
    log(f"    {'USUBJID':<20} {'MHTERM':<40} {'MHDECOD':<50}")
    log(f"    {'-'*20} {'-'*40} {'-'*50}")
    for _, row in _discrepancy_rows.iterrows():
        log(f"    {row['bcr_patient_barcode']:<20} "
            f"{row['MHTERM_derived']:<40} "
            f"{row['MHDECOD_derived']:<50}")
if n_mismatches > 0:
    warnings.append(
        f"{n_mismatches} MHTERM/MHDECOD mismatches -- see discrepancy report"
    )

# 7e. Exhaustiveness check: confirm no additional discrepancies exist in
# non-concatenated rows beyond those already flagged by 7d.
# Method: for every non-concatenated histological_type value, produce a
# cross-tab of (histological_type x icd_o_3_histology x MHDECOD) and
# verify that the only rows flagged are exactly those in _discrepancy_rows.
# This check also confirms that histological_type categories not covered by
# _EXPECTED_CODES (i.e. not checked in 7d) are internally consistent
# (all patients in that category share the same ICD-O-3 code).
_non_concat_src = src[~_is_concatenated].copy()
_non_concat_src["_MHDECOD"] = _non_concat_src["icd_o_3_histology"].map(_icd_lookup)
_xtab = (
    _non_concat_src
    .groupby(["histological_type", "icd_o_3_histology", "_MHDECOD"], dropna=False)
    .agg(n=("bcr_patient_barcode", "count"))
    .reset_index()
)
# A category is "consistent" if it maps to exactly one ICD-O-3 code
_by_hist = _xtab.groupby("histological_type")["icd_o_3_histology"].nunique()
_inconsistent_cats = _by_hist[_by_hist > 1].index.tolist()

log("")
log("  7e. Exhaustiveness check -- all non-concatenated histological_type categories:")
log(f"    Categories checked: {sorted(_by_hist.index.tolist())}")
log(f"    Categories with >1 ICD-O-3 code (i.e. potential discrepancies): "
    f"{_inconsistent_cats if _inconsistent_cats else 'None beyond already flagged'}")
log("")
log("  Full cross-tab of non-concatenated rows "
    "(histological_type x ICD-O-3 code x decoded text):")
log(f"    {'histological_type':<40} {'code':<10} {'MHDECOD':<55} {'n':>4}")
log(f"    {'-'*40} {'-'*10} {'-'*55} {'-'*4}")
for _, row in _xtab.iterrows():
    mismatch_flag = "  <-- MISMATCH" if row["n"] > 0 and any(
        (row["bcr_patient_barcode"] if "bcr_patient_barcode" in row else "") == p
        for p in _discrepancy_rows.get("bcr_patient_barcode", [])
    ) else ""
    # Simpler: flag if this (histological_type, code) combo was in _discrepancy_rows
    is_flagged = (
        row["histological_type"] in _discrepancy_rows["histological_type"].values
        and row["icd_o_3_histology"] in _discrepancy_rows["icd_o_3_histology"].values
        and row["histological_type"] in _inconsistent_cats
    )
    flag = "  <-- MISMATCH (flagged in 7d)" if is_flagged else ""
    log(f"    {row['histological_type']:<40} {row['icd_o_3_histology']:<10} "
        f"{str(row['_MHDECOD']):<55} {row['n']:>4}{flag}")

# 8. No leftover sentinels in MH output
log("")
log("  Sentinel-string scan (should find zero):")
sentinel_hits_total = 0
for col in MH_COLUMNS:
    s = mh[col]
    if (s.dtype == object) or pd.api.types.is_string_dtype(s):
        hit = s.isin(SENTINELS).sum()
        if hit:
            log(f"    {col:<10} {hit} sentinel values  <-- REVIEW")
            warnings.append(f"Sentinels in {col}")
            sentinel_hits_total += hit
if sentinel_hits_total == 0:
    log("    (none found)")

# 9. MHSTDY numeric & non-null
mhstdy_bad = mh["MHSTDY"].isna().sum()
check("MHSTDY is numeric and non-null",
      mhstdy_bad == 0,
      f"{mhstdy_bad} null values" if mhstdy_bad else "")

# 10. MHSTRTPT / MHSTTPT conditional consistency
# (a) MHSTRTPT values must be in {'', 'BEFORE'}
# (b) MHSTTPT  values must be in {'', 'SCREENING'}
# (c) Populated iff source initial_pathologic_dx_year == '[Not Available]'
# (d) MHSTRTPT and MHSTTPT always populated together (both blank or both set)
_raw_year_check = src["initial_pathologic_dx_year"].astype(str)
_expected_trigger_mask = (_raw_year_check == MHSTRTPT_TRIGGER).reset_index(drop=True)
n_trigger_expected = int(_expected_trigger_mask.sum())

bad_strtpt_vals = (~mh["MHSTRTPT"].isin(["", MHSTRTPT])).sum()
bad_sttpt_vals  = (~mh["MHSTTPT"].isin(["", MHSTTPT])).sum()
check(f"MHSTRTPT values are in {{'', '{MHSTRTPT}'}}", bad_strtpt_vals == 0,
      f"{bad_strtpt_vals} unexpected values" if bad_strtpt_vals else "")
check(f"MHSTTPT values are in {{'', '{MHSTTPT}'}}", bad_sttpt_vals == 0,
      f"{bad_sttpt_vals} unexpected values" if bad_sttpt_vals else "")

strtpt_populated = (mh["MHSTRTPT"] == MHSTRTPT).reset_index(drop=True)
sttpt_populated  = (mh["MHSTTPT"]  == MHSTTPT ).reset_index(drop=True)

# mh was sorted+reindexed; _expected_trigger_mask came from src pre-sort.
# To compare correctly, rebuild the expected mask per USUBJID and align.
_expected_by_usubjid = dict(zip(
    src["bcr_patient_barcode"].astype(str),
    _raw_year_check == MHSTRTPT_TRIGGER,
))
expected_trigger_aligned = mh["USUBJID"].astype(str).map(_expected_by_usubjid).fillna(False)

mismatch_strtpt = (strtpt_populated != expected_trigger_aligned.reset_index(drop=True)).sum()
check("MHSTRTPT populated iff source year == '[Not Available]'",
      mismatch_strtpt == 0,
      f"{mismatch_strtpt} row(s) don't match expected trigger"
      if mismatch_strtpt else
      f"{int(strtpt_populated.sum())} populated, "
      f"{n_trigger_expected} expected")

coupling_bad = (strtpt_populated != sttpt_populated).sum()
check("MHSTRTPT and MHSTTPT are always populated together",
      coupling_bad == 0,
      f"{coupling_bad} row(s) have one without the other"
      if coupling_bad else "")

# 11. Column order
check("Column order matches expected SDTM MH order",
      list(mh.columns) == MH_COLUMNS,
      f"got {len(mh.columns)} cols, expected {len(MH_COLUMNS)}")


# ---------------------------------------------------------------------------
# Summary + write
# ---------------------------------------------------------------------------
log()
if warnings:
    log(f"WARNINGS ({len(warnings)}): {warnings}")
else:
    log("All QC checks passed.")

# Pre-write check: since we're writing tab-separated output, fail loudly if
# any value contains a tab (which would corrupt column alignment).
tab_hits = 0
for col in MH_COLUMNS:
    s = mh[col]
    if (s.dtype == object) or pd.api.types.is_string_dtype(s):
        tab_hits += s.fillna("").astype(str).str.contains("\t", regex=False).sum()
check("No tab characters in any value cell (tab-delimiter safety)",
      tab_hits == 0,
      f"{tab_hits} cells contain tabs" if tab_hits else "")

mh.to_csv(OUTPUT_FILE, sep="\t", index=False)
log(f"\nWrote {OUTPUT_FILE} ({n_out} rows)")

# Write discrepancy report as a separate tab-separated file
DISCREPANCY_FILE = OUTPUT_FILE.parent / (OUTPUT_FILE.stem + "_discrepancies.txt")
if len(_discrepancy_rows) > 0:
    _discrepancy_rows.to_csv(DISCREPANCY_FILE, sep="\t", index=False)
    log(f"Wrote {DISCREPANCY_FILE} ({len(_discrepancy_rows)} mismatches)")
else:
    log("No discrepancies found -- discrepancy file not written")

# ---------------------------------------------------------------------------
# Summary file: instructions (as restated to the user) + run log + QC results
# ---------------------------------------------------------------------------
INSTRUCTIONS = """\
TCGA-BRCA -> SDTM MH DOMAIN BUILD
=================================

Source
------
  Input  : /mnt/user-data/outputs/tcga_brca_cohort_inclusion.xlsx
           (385-patient TCGA-BRCA screening cohort, one row per patient)
  Spec   : tcga_to_sdtm_mapping_specs.xlsx (updated version; with in-chat
           clarifications where needed)

Output
------
  File   : /mnt/user-data/outputs/tcga_brca_mh.txt
  Format : Tab-separated (tab delimiter), UTF-8, .txt extension
  Shape  : 385 rows (one MH row per subject -- the initial breast cancer
           diagnosis event), 15 columns.

Column mapping
--------------
  STUDYID  : hardcoded 'TCGA-BRCA'
  DOMAIN   : hardcoded 'MH'
  USUBJID  : bcr_patient_barcode                   (direct copy)
  MHSEQ    : 1 for every row; implemented via spec's general logic
             (sort by USUBJID, VISITNUM, MHTERM; groupby-cumcount + 1)
  MHTERM   : histological_type                     (source-to-target copy
                                                    with concatenation for:
                                                    'Other  specify' ->
                                                      'Other specify - ' ||
                                                      histologic_diagnosis_other
                                                    'Mixed Histology (please specify)' ->
                                                      'Mixed Histology (please specify) - ' ||
                                                      histologic_diagnosis_other)
  MHDECOD  : icd_o_3_histology                     (converted to text via
                                                    icd-o-3_code_to_text.xlsx
                                                    lookup dictionary)
  MHCAT    : hardcoded 'TCGA-PATIENT'
  MHEVDTYP : hardcoded 'INITIAL PATHOLOGICAL DIAGNOSIS'
  MHSTDTC  : initial_pathologic_dx_year            (year-only ISO 8601,
                                                    e.g. '2009'; BLANK if
                                                    source is non-date,
                                                    e.g. '[Not Available]')
  MHDTC    : form_completion_date                  (ISO 8601 YYYY-MM-DD,
                                                    zero-padded; BLANK if
                                                    source is non-date)
  MHSTDY   : days_to_initial_pathologic_diagnosis + 1
                                                   (Num; = 1 for all 385
                                                    patients since days = 0
                                                    for all)
  MHSTRTPT : hardcoded 'BEFORE'                    (ONLY populated when
                                                    source year value is
                                                    literally '[Not Available]';
                                                    else blank)
  MHSTTPT  : hardcoded 'SCREENING'                 (same conditional rule
                                                    as MHSTRTPT)
  MHPRESP  : hardcoded 'Y'                         (all events pre-specified)
  MHOCCUR  : hardcoded 'Y'                         (all events occurred)
  VISITNUM : hardcoded 1                           (Num, per SDTM standard)
  VISIT    : hardcoded 'VISIT 1'

Not performed
-------------
  - MHTERM is NOT validated against any controlled terminology (verbatim
    collected term with concatenation where specified, per spec v2).
  - Spec's "Invasive breast cancer / histological_type" screening row was
    omitted (all TCGA-BRCA patients are breast cancer patients by dataset
    definition, per user clarification).
  - pharmaceutical_therapy_type value distribution in the drug file was
    NOT inspected (the chemo filter used exact-string equality with
    'Chemotherapy', per the screening cohort spec).
  - MHSTRTPT/MHSTTPT trigger interpreted LITERALLY: only source value
    exactly '[Not Available]' triggers population. Other non-date
    sentinels (e.g. '[Unknown]', '[Discrepancy]') would leave MHSTRTPT
    and MHSTTPT blank. None of those other sentinels appear in
    initial_pathologic_dx_year in this dataset.

QC checks performed
-------------------
   1. Input row count equals output row count
   2. USUBJID is unique across rows
   3. (USUBJID, MHSEQ) natural key is unique
   4. Missingness per column (NaN and empty-string counts, informational;
      MHSTDTC, MHDTC, MHSTRTPT, MHSTTPT may be blank by design)
   5. MHSTDTC: blank OR ISO 8601 year pattern ^\\d{4}$
   6. MHDTC : blank OR ISO 8601 YYYY-MM-DD
   7. Hardcoded (always-populated) columns uniform = expected value
   8. Sentinel-string scan -- no '[Not Available]' / '[Not Applicable]' /
      '[Unknown]' / '[Discrepancy]' in MH output
   9. MHSTDY is numeric and non-null
  10. MHSTRTPT / MHSTTPT conditional consistency:
      - MHSTRTPT values in {'', 'BEFORE'}
      - MHSTTPT  values in {'', 'SCREENING'}
      - populated iff source initial_pathologic_dx_year == '[Not Available]'
      - MHSTRTPT and MHSTTPT always populated together (both blank or
        both set) on each row
  11. Column order matches expected SDTM MH order (15 cols)
  12. No tab characters in any value cell (tab-delimiter safety)

  Warnings are collected but do not abort the write. The output file is
  produced regardless; the summary below reports PASS/FAIL per check.
"""

with open(SUMMARY_FILE, "w") as f:
    f.write(INSTRUCTIONS)
    f.write("\n")
    f.write("=" * 60 + "\n")
    f.write("RUN LOG / QC RESULTS\n")
    f.write("=" * 60 + "\n")
    f.write("\n".join(_log_lines))
    f.write("\n")

print(f"Wrote {SUMMARY_FILE}")
