"""
build_tcga_mimic_combined_mh.py
================================
Combine the TCGA-BRCA MH domain output (tcga_brca_mh_v3.txt) with the
MIMIC-IV MH domain output (MH.xlsx) into a single tab-separated combined
file: tcga_mimic_mh_combined.txt.

Inputs
------
  tcga_brca_mh_v3.txt   -- TCGA-BRCA SDTM MH output (17 cols, 385 rows)
  MH.xlsx               -- MIMIC-IV pre-mapped SDTM MH (16 cols, 9 rows)

Output
------
  tcga_mimic_mh_combined.txt   -- combined MH (19 cols, 394 rows)
  tcga_mimic_mh_combined_report.txt -- structural report + QC

Column union notes
------------------
  TCGA-only columns  : MHSTDY, MHSTRTPT, MHSTTPT  (blank for MIMIC rows)
  MIMIC-only columns : MHSTAT, MHDY               (blank for TCGA rows)

  MHSTDTC / MHDTC differ in precision across studies:
    TCGA  -> year-only (MHSTDTC) and YYYY-MM-DD (MHDTC)
    MIMIC -> full ISO8601 datetime for both

  Column order in combined file follows SDTM MH variable ordering convention.

QC checks performed
-------------------
  1.  Row count = TCGA rows + MIMIC rows
  2.  STUDYID uniform within each study partition
  3.  No unexpected STUDYID values
  4.  USUBJID unique across TCGA rows (each TCGA subject = 1 MH record here)
  5.  (STUDYID, USUBJID, MHSEQ) natural key unique across combined file
  6.  Column union: all expected columns present
  7.  TCGA-only columns blank for MIMIC rows
  8.  MIMIC-only columns blank for TCGA rows
  9.  Missingness per column per study (informational)
  10. No tab characters in any value cell (tab-delimiter safety)
  11. Sentinel string scan for TCGA rows
"""

from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OUTPUTS   = Path("/mnt/user-data/outputs")
UPLOADS   = Path("/mnt/user-data/uploads")

TCGA_FILE  = OUTPUTS / "tcga_brca_mh_v3.txt"
MIMIC_FILE = UPLOADS / "MH.xlsx"
OUT_FILE   = OUTPUTS / "tcga_mimic_mh_combined.txt"
REPORT_FILE= OUTPUTS / "tcga_mimic_mh_combined_report.txt"

# Expected SDTM MH column order for combined file
COMBINED_COLS = [
    "STUDYID", "DOMAIN", "USUBJID", "MHSEQ",
    "MHTERM", "MHDECOD", "MHCAT", "MHEVDTYP",
    "MHPRESP", "MHOCCUR", "MHSTAT",
    "MHSTDTC", "MHDTC",
    "MHSTDY",    # TCGA only: Study Day of Start of Event
    "MHDY",      # MIMIC only: Study Day of Collection (all null in source)
    "MHSTRTPT", "MHSTTPT",
    "VISITNUM", "VISIT",
]

TCGA_ONLY_COLS  = ["MHSTDY", "MHSTRTPT", "MHSTTPT"]
MIMIC_ONLY_COLS = ["MHSTAT", "MHDY"]
SENTINELS = {"[Not Available]", "[Not Applicable]", "[Unknown]", "[Discrepancy]"}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log: list[str] = []
def log(msg: str = "") -> None:
    print(msg)
    _log.append(msg)

_qc: list[tuple[str, bool, str]] = []
def qc(label: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    line = f"  [{status}] {label}" + (f" -- {detail}" if detail else "")
    log(line)
    _qc.append((label, passed, detail))

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
log("=" * 60)
log("BUILD: tcga_mimic_mh_combined.txt")
log("=" * 60)

tcga  = pd.read_csv(TCGA_FILE,  sep="\t", dtype=str, keep_default_na=False)
mimic = pd.read_excel(MIMIC_FILE, dtype=str)
# Preserve MIMIC sentinel NaN as empty string
mimic = mimic.fillna("")

n_tcga  = len(tcga)
n_mimic = len(mimic)

log(f"  Loaded TCGA  : {n_tcga} rows, {len(tcga.columns)} cols  ({TCGA_FILE.name})")
log(f"  Loaded MIMIC : {n_mimic} rows, {len(mimic.columns)} cols ({MIMIC_FILE.name})")
log(f"  TCGA columns : {list(tcga.columns)}")
log(f"  MIMIC columns: {list(mimic.columns)}")
log()

# ---------------------------------------------------------------------------
# Combine
# ---------------------------------------------------------------------------
combined = (
    pd.concat([tcga, mimic], ignore_index=True, sort=False)
    .fillna("")
)

# Enforce SDTM column order; add any missing columns as blank
for col in COMBINED_COLS:
    if col not in combined.columns:
        combined[col] = ""
combined = combined[COMBINED_COLS]

n_combined = len(combined)
log(f"  Combined     : {n_combined} rows, {len(combined.columns)} cols")

# ---------------------------------------------------------------------------
# QC
# ---------------------------------------------------------------------------
log()
log("=" * 60)
log("QC CHECKS")
log("=" * 60)

# 1. Row count
qc("Row count = TCGA + MIMIC",
   n_combined == n_tcga + n_mimic,
   f"{n_tcga} + {n_mimic} = {n_tcga+n_mimic}, combined={n_combined}")

# 2. STUDYID uniform within each study
tcga_ids  = set(combined.loc[:n_tcga-1, "STUDYID"].unique())
mimic_ids = set(combined.loc[n_tcga:,   "STUDYID"].unique())
qc("TCGA partition has one STUDYID",
   len(tcga_ids) == 1,
   f"found: {tcga_ids}")
qc("MIMIC partition has one STUDYID",
   len(mimic_ids) == 1,
   f"found: {mimic_ids}")

# 3. No unexpected STUDYID values
all_ids = set(combined["STUDYID"].unique())
expected_ids = {"TCGA-BRCA", "MIMICIVBC"}
qc("No unexpected STUDYID values",
   all_ids == expected_ids,
   f"found: {all_ids}")

# 4. USUBJID unique within TCGA (one MH record per TCGA subject)
dup_tcga = combined.loc[:n_tcga-1, "USUBJID"].duplicated().sum()
qc("USUBJID unique within TCGA rows",
   dup_tcga == 0,
   f"{dup_tcga} duplicates" if dup_tcga else "")

# 5. (STUDYID, USUBJID, MHSEQ) natural key unique
dup_key = combined.duplicated(subset=["STUDYID", "USUBJID", "MHSEQ"]).sum()
qc("(STUDYID, USUBJID, MHSEQ) natural key unique",
   dup_key == 0,
   f"{dup_key} duplicates" if dup_key else "")

# 6. All expected columns present in correct order
qc("All expected columns present in COMBINED_COLS order",
   list(combined.columns) == COMBINED_COLS,
   f"got {list(combined.columns)}" if list(combined.columns) != COMBINED_COLS else
   f"{len(COMBINED_COLS)} columns in order")

# 7. TCGA-only columns blank for MIMIC rows
for col in TCGA_ONLY_COLS:
    n_nonblank = (combined.loc[n_tcga:, col] != "").sum()
    qc(f"TCGA-only column '{col}' blank for all MIMIC rows",
       n_nonblank == 0,
       f"{n_nonblank} non-blank MIMIC rows" if n_nonblank else "")

# 8. MIMIC-only columns blank for TCGA rows
for col in MIMIC_ONLY_COLS:
    n_nonblank = (combined.loc[:n_tcga-1, col] != "").sum()
    qc(f"MIMIC-only column '{col}' blank for all TCGA rows",
       n_nonblank == 0,
       f"{n_nonblank} non-blank TCGA rows" if n_nonblank else "")

# 9. Missingness per column per study (informational)
log()
log("  Missingness per column (blank or null) -- informational:")
log(f"  {'Column':<12} {'TCGA blank/'+str(n_tcga):<22} {'MIMIC blank/'+str(n_mimic):<22} Notes")
log(f"  {'-'*12} {'-'*22} {'-'*22} {'-'*30}")
for col in COMBINED_COLS:
    t_blank = (combined.loc[:n_tcga-1, col] == "").sum()
    m_blank = (combined.loc[n_tcga:,   col] == "").sum()
    note = ""
    if col in TCGA_ONLY_COLS:  note = "TCGA only"
    if col in MIMIC_ONLY_COLS: note = "MIMIC only"
    if col in ("MHSTDTC","MHDTC"): note = "Mixed precision across studies"
    log(f"  {col:<12} {str(t_blank)+'/'+str(n_tcga):<22} {str(m_blank)+'/'+str(n_mimic):<22} {note}")

# 10. No tab characters in any cell
tab_hits = 0
for col in COMBINED_COLS:
    tab_hits += combined[col].astype(str).str.contains("\t", regex=False).sum()
qc("No tab characters in any value cell (tab-delimiter safety)",
   tab_hits == 0,
   f"{tab_hits} cells contain tabs" if tab_hits else "")

# 11. Sentinel scan on TCGA rows
log()
log("  Sentinel string scan on TCGA rows:")
sentinel_total = 0
for col in COMBINED_COLS:
    hits = combined.loc[:n_tcga-1, col].isin(SENTINELS).sum()
    if hits:
        log(f"    {col}: {hits} sentinel values  <-- preserved verbatim in output")
        sentinel_total += hits
if sentinel_total == 0:
    log("    (none found)")

log()
n_pass = sum(1 for _, p, _ in _qc if p)
n_fail = sum(1 for _, p, _ in _qc if not p)
log(f"QC summary: {n_pass} PASS, {n_fail} FAIL out of {len(_qc)} checks")

# ---------------------------------------------------------------------------
# Write combined file
# ---------------------------------------------------------------------------
combined.to_csv(OUT_FILE, sep="\t", index=False)
log(f"\nWrote {OUT_FILE}  ({OUT_FILE.stat().st_size:,} bytes)")

# ---------------------------------------------------------------------------
# Write report
# ---------------------------------------------------------------------------
REPORT_LINES = []
def r(s=""): REPORT_LINES.append(s)

r("TCGA-BRCA + MIMIC-IV COMBINED MH DOMAIN — BUILD REPORT")
r("=" * 60)
r()
r("Inputs")
r("------")
r(f"  TCGA  : {TCGA_FILE.name}  ({n_tcga} rows, {len(tcga.columns)} cols)")
r(f"  MIMIC : {MIMIC_FILE.name}      ({n_mimic} rows, {len(mimic.columns)} cols)")
r()
r("Output")
r("------")
r(f"  {OUT_FILE.name}  ({n_combined} rows, {len(COMBINED_COLS)} cols)")
r()
r("Column union")
r("------------")
r(f"  Shared columns ({len(set(tcga.columns) & set(mimic.columns))}): "
  f"{sorted(set(tcga.columns) & set(mimic.columns))}")
r(f"  TCGA-only ({len(TCGA_ONLY_COLS)}): {TCGA_ONLY_COLS} -> blank for MIMIC rows")
r(f"  MIMIC-only ({len(MIMIC_ONLY_COLS)}): {MIMIC_ONLY_COLS} -> blank for TCGA rows")
r()
r("Column-level notes")
r("------------------")
r("  MHSTDY  : TCGA only. Study Day of Start of Event = days + 1. All = 1.")
r("  MHSTRTPT: TCGA only. 'BEFORE' for 2 subjects where year = [Not Available].")
r("  MHSTTPT : TCGA only. 'SCREENING' for same 2 subjects.")
r("  MHSTAT  : MIMIC only. All null in MIMIC source. Always blank.")
r("  MHDY    : MIMIC only. All null in MIMIC source. Always blank.")
r("  MHSTDTC : Mixed precision -- TCGA=year-only (e.g.'2009'), "
  "MIMIC=full datetime (e.g.'2149-01-29T22:09:00').")
r("  MHDTC   : Mixed precision -- TCGA=date-only (e.g.'2011-05-27'), "
  "MIMIC=full datetime.")
r("  MHTERM  : TCGA=histological type text; MIMIC=ICD code string (e.g.'C50919').")
r("  MHCAT   : TCGA='TCGA-PATIENT'; MIMIC='MALIGNANCY HISTORY'.")
r("  MHEVDTYP: TCGA=all populated; MIMIC=1 of 9 populated, 8 blank.")
r("  MHPRESP : TCGA=all 'Y'; MIMIC=all blank (not recorded).")
r()
r("=" * 60)
r("QC RESULTS")
r("=" * 60)
for label, passed, detail in _qc:
    status = "PASS" if passed else "FAIL"
    r(f"  [{status}] {label}" + (f" -- {detail}" if detail else ""))
r()
r(f"Total: {n_pass} PASS, {n_fail} FAIL out of {len(_qc)} checks")

REPORT_FILE.write_text("\n".join(REPORT_LINES) + "\n", encoding="utf-8")
log(f"Wrote {REPORT_FILE}")
