"""
build_combined_mh_xmls.py
==========================
Builds the following outputs for the combined TCGA-BRCA + MIMIC-IV MH domain:

  define_combined_mh.xml              -- CDISC Define-XML 2.1
  define_combined_mh.csv              -- CSV rendering of the Define-XML
  rwd_lineage_combined_mh_celllevel.xml -- RWDL v1 cell-level lineage
  rwd_lineage_combined_mh_celllevel.csv -- CSV rendering of the lineage
  build_xml_report_combined.txt       -- Step-by-step documentation + QC

Source data required (all in OUTPUTS or UPLOADS):
  MH.txt          -- combined target SDTM MH file (394 rows)
  tcga_brca_cohort_inclusion.xlsx     -- TCGA source patient file (385 rows)
  MH.xlsx                             -- MIMIC pre-mapped MH source (9 rows)
  tcga_brca_mh_v3_discrepancies.txt   -- 4 TCGA MHTERM/MHDECOD mismatches

Spec references
---------------
  Define-XML 2.1 : CDISC Define-XML Specification Version 2.1 (Final), 2019-05-15
  RWDL v1        : RWD-Lineage Data Standard Specification (Draft)

Design decisions
----------------
  1. MethodDefs: 7 total. Combined-dataset methods (MHTERM, MHDECOD, MHSTDTC,
     MHDTC) carry study-conditional branching logic. MT.MIMIC.DIRECT covers all
     MIMIC direct-copy variables. MT.MHSTDY.DAYSPLUS1 and MT.MHSTRTPT.CONDITIONAL
     are TCGA-only.

  2. MHSTDTC and MHDTC: DataType=incompleteDatetime to accommodate both
     year-only (TCGA) and full datetime (MIMIC) values in the same column.

  3. Lineage: cell-level (one MapID per target cell per subject).
     TCGA: 3,101 MapIDs (8 columns × 385 subjects + 21 extra for MHTERM concat).
     MIMIC: 117 MapIDs (13 columns × 9 subjects).
     Total: 3,218 MapIDs, all UUIDs deterministic UUIDv5.

  4. Omitted columns: hardcoded/assigned/derived-only columns are excluded from
     the lineage and documented in OmittedColumns. See rwdl_spec_gaps_combined.txt.

  5. MIMIC source: MH.xlsx is itself pre-mapped SDTM — not raw RWD. This is a
     known spec gap (Gap C1 in rwdl_spec_gaps_combined.txt).
"""

import uuid, datetime, xml.etree.ElementTree as ET, pandas as pd
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
OUTPUTS   = Path("/mnt/user-data/outputs")
UPLOADS   = Path("/mnt/user-data/uploads")

COMBINED_FILE = OUTPUTS / "MH.txt"
TCGA_SRC_FILE = OUTPUTS / "tcga_brca_cohort_inclusion.xlsx"
MIMIC_SRC_FILE= UPLOADS / "MH.xlsx"
DISC_FILE     = OUTPUTS / "tcga_brca_mh_v3_discrepancies.txt"

DEFINE_OUT    = OUTPUTS / "define_combined_mh.xml"
DEFINE_CSV    = OUTPUTS / "define_combined_mh.csv"
LINEAGE_OUT   = OUTPUTS / "rwd_lineage_combined_mh_celllevel.xml"
LINEAGE_CSV   = OUTPUTS / "rwd_lineage_combined_mh_celllevel.csv"
REPORT_OUT    = OUTPUTS / "build_xml_report_combined.txt"

# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------
ODM_NS   = "http://www.cdisc.org/ns/odm/v1.3"
DEF_NS   = "http://www.cdisc.org/ns/def/v2.1"
XLINK_NS = "http://www.w3.org/1999/xlink"
RWDL_NS  = "http://www.cdisc.org/ns/rwdl/v1.0"
RWDL_UUID_NS = uuid.uuid5(uuid.NAMESPACE_URL, RWDL_NS)

ET.register_namespace("",      ODM_NS)
ET.register_namespace("def",   DEF_NS)
ET.register_namespace("xlink", XLINK_NS)
ET.register_namespace("rwdl",  RWDL_NS)

def ot(n):   return f"{{{ODM_NS}}}{n}"
def dt(n):   return f"{{{DEF_NS}}}{n}"
def xl(n):   return f"{{{XLINK_NS}}}{n}"
def rt(n):   return f"{{{RWDL_NS}}}{n}"
def ioid(c): return f"IT.MH.COMBINED.{c}"
def make_uuid(s): return str(uuid.uuid5(RWDL_UUID_NS, s))

NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

def sub(parent, name, ns=ODM_NS, **attrs):
    el = ET.SubElement(parent, f"{{{ns}}}{name}")
    for k, v in attrs.items(): el.set(k, str(v))
    return el
def dsub(parent, name, **attrs): return sub(parent, name, ns=DEF_NS, **attrs)
def rsub(parent, name, **attrs): return sub(parent, name, ns=RWDL_NS, **attrs)
def rsub_d(parent, name, d):
    el = ET.SubElement(parent, rt(name))
    for k, v in d.items(): el.set(k, str(v))
    return el
def tt_el(parent, text):
    d = sub(parent, "Description")
    tt = sub(d, "TranslatedText"); tt.set("xml:lang","en"); tt.text=text

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log: list[str] = []
def log(msg: str = "") -> None:
    print(msg); _log.append(msg)

_qc: list[tuple[str,bool,str]] = []
def qc(label: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    line = f"  [{status}] {label}" + (f" -- {detail}" if detail else "")
    log(line); _qc.append((label, passed, detail))

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
combined    = pd.read_csv(COMBINED_FILE, sep="\t", dtype=str,
                          keep_default_na=False).reset_index(drop=True)
tcga_src    = pd.read_excel(TCGA_SRC_FILE, dtype=str)
tcga_keyed  = tcga_src.set_index("bcr_patient_barcode")
mimic_src   = pd.read_excel(MIMIC_SRC_FILE, dtype=str).fillna("")
disc        = pd.read_csv(DISC_FILE, sep="\t", dtype=str, keep_default_na=False)
disc_set    = set(disc["bcr_patient_barcode"])

# MIMIC lookup by (USUBJID, MHSEQ)
mimic_lookup = {}
for _, row in mimic_src.iterrows():
    mimic_lookup[(row["USUBJID"], row["MHSEQ"])] = row.to_dict()

n_tcga   = int((combined["STUDYID"] == "TCGA-BRCA").sum())
n_mimic  = int((combined["STUDYID"] == "MIMICIVBC").sum())
n_total  = len(combined)
n_cols   = len(combined.columns)

log(f"Loaded combined file: {n_total} rows ({n_tcga} TCGA, {n_mimic} MIMIC), {n_cols} cols")

TGT_FILE      = "./MH.txt"
TCGA_URI      = "./nationwidechildrens_org_clinical_patient_brca.txt"
MIMIC_URI     = "MH.xlsx"

# ---------------------------------------------------------------------------
# Column specs
# ---------------------------------------------------------------------------
# MethodDef OIDs
MT = {
    "MHTERM"  : "MT.COMBINED.MHTERM",
    "MHDECOD" : "MT.COMBINED.MHDECOD",
    "MHSTDTC" : "MT.COMBINED.MHSTDTC",
    "MHDTC"   : "MT.COMBINED.MHDTC",
    "MHSTDY"  : "MT.MHSTDY.DAYSPLUS1",
    "MHSTRTPT": "MT.MHSTRTPT.CONDITIONAL",
    "MHSTTPT" : "MT.MHSTRTPT.CONDITIONAL",
    "MHSEQ"   : "MT.MIMIC.DIRECT",
    "MHCAT"   : "MT.MIMIC.DIRECT",
    "MHEVDTYP": "MT.MIMIC.DIRECT",
    "MHOCCUR" : "MT.MIMIC.DIRECT",
    "MHSTAT"  : "MT.MIMIC.DIRECT",
    "MHDY"    : "MT.MIMIC.DIRECT",
    "VISITNUM": "MT.MIMIC.DIRECT",
    "VISIT"   : "MT.MIMIC.DIRECT",
}

# TCGA column spec: (src_col_or_list, tr_type, tr_desc, include_in_lineage)
TCGA_COL = {
    "STUDYID" :(None,                                    "Assigned","Hardcoded 'TCGA-BRCA'. SPEC GAP: no source cell.",False),
    "DOMAIN"  :(None,                                    "Assigned","Hardcoded 'MH'. SPEC GAP: no source cell.",False),
    "USUBJID" :("bcr_patient_barcode",                   "Direct Map","Direct copy of bcr_patient_barcode.",True),
    "MHSEQ"   :(None,                                    "Derived","Computed cumcount within USUBJID. SPEC GAP: no source cell.",False),
    "MHTERM"  :(["histological_type","histologic_diagnosis_other"],
                "Conditional Concat","Conditional concat. See MT.COMBINED.MHTERM.",True),
    "MHDECOD" :("icd_o_3_histology",                     "Lookup","ICD-O-3 code to text via lookup. See MT.COMBINED.MHDECOD.",True),
    "MHCAT"   :(None,                                    "Assigned","Hardcoded 'TCGA-PATIENT'. SPEC GAP: no source cell.",False),
    "MHEVDTYP":(None,                                    "Assigned","Hardcoded 'INITIAL PATHOLOGICAL DIAGNOSIS'. SPEC GAP.",False),
    "MHPRESP" :(None,                                    "Assigned","Hardcoded 'Y'. SPEC GAP: no source cell.",False),
    "MHOCCUR" :(None,                                    "Assigned","Hardcoded 'Y'. SPEC GAP: no source cell.",False),
    "MHSTAT"  :(None,                                    "Not Collected","Always blank for TCGA.",False),
    "MHSTDTC" :("initial_pathologic_dx_year",            "ISO8601 Year or Blank","Year-only ISO8601; blank if '[Not Available]'.",True),
    "MHDTC"   :("form_completion_date",                  "ISO8601 Conversion","YYYY-M-D to zero-padded YYYY-MM-DD.",True),
    "MHSTDY"  :("days_to_initial_pathologic_diagnosis",  "Derivation","MHSTDY = source + 1.",True),
    "MHDY"    :(None,                                    "Not Collected","Always blank for TCGA.",False),
    "MHSTRTPT":("initial_pathologic_dx_year",            "Conditional Assign","'BEFORE' iff source == '[Not Available]'.",True),
    "MHSTTPT" :("initial_pathologic_dx_year",            "Conditional Assign","'SCREENING' iff source == '[Not Available]'.",True),
    "VISITNUM":(None,                                    "Assigned","Hardcoded 1. SPEC GAP: no source cell.",False),
    "VISIT"   :(None,                                    "Assigned","Hardcoded 'VISIT 1'. SPEC GAP: no source cell.",False),
}

# MIMIC column spec
MIMIC_COL = {
    "STUDYID" :(None,        "Assigned","Hardcoded 'MIMICIVBC'. SPEC GAP: no source cell.",False),
    "DOMAIN"  :(None,        "Assigned","Hardcoded 'MH'. SPEC GAP: no source cell.",False),
    "USUBJID" :("USUBJID",   "Direct Map","Direct copy from MIMIC MH source.",True),
    "MHSEQ"   :("MHSEQ",     "Direct Map","Direct copy from MIMIC MH source.",True),
    "MHTERM"  :("MHTERM",    "Direct Map","ICD code string from MIMIC source.",True),
    "MHDECOD" :("MHDECOD",   "Direct Map","ICD description from MIMIC source.",True),
    "MHCAT"   :("MHCAT",     "Direct Map","Direct copy 'MALIGNANCY HISTORY'.",True),
    "MHEVDTYP":("MHEVDTYP",  "Direct Map","Direct copy (blank for 8 of 9 rows).",True),
    "MHPRESP" :(None,        "Not Collected","Blank for MIMIC — not in source.",False),
    "MHOCCUR" :("MHOCCUR",   "Direct Map","Direct copy from MIMIC source.",True),
    "MHSTAT"  :("MHSTAT",    "Direct Map","Direct copy (all null in source).",True),
    "MHSTDTC" :("MHSTDTC",   "Direct Map","Full ISO8601 datetime from MIMIC.",True),
    "MHDTC"   :("MHDTC",     "Direct Map","Full ISO8601 datetime from MIMIC.",True),
    "MHSTDY"  :(None,        "Not Collected","Blank for MIMIC.",False),
    "MHDY"    :("MHDY",      "Direct Map","Direct copy (all null in source).",True),
    "MHSTRTPT":(None,        "Not Collected","Blank for MIMIC — not applicable.",False),
    "MHSTTPT" :(None,        "Not Collected","Blank for MIMIC — not applicable.",False),
    "VISITNUM":("VISITNUM",  "Direct Map","Direct copy from MIMIC source.",True),
    "VISIT"   :("VISIT",     "Direct Map","Direct copy from MIMIC source.",True),
}

# Variable definitions for Define-XML
MH_VARS = [
    # col, label, dtype, len, origin_type, origin_src, method_oid, mandatory
    ("STUDYID",  "Study Identifier",                       "text",             9,  "Protocol",  "Sponsor",       None,                      "Yes"),
    ("DOMAIN",   "Domain Abbreviation",                    "text",             2,  "Protocol",  "Sponsor",       None,                      "Yes"),
    ("USUBJID",  "Unique Subject Identifier",              "text",            18,  "Assigned",  "Sponsor",       "MT.MIMIC.DIRECT",         "Yes"),
    ("MHSEQ",    "Sequence Number",                        "integer",          2,  "Derived",   "Sponsor",       "MT.MIMIC.DIRECT",         "Yes"),
    ("MHTERM",   "Verbatim History Term",                  "text",           200,  "Collected", "Investigator",  "MT.COMBINED.MHTERM",      "Yes"),
    ("MHDECOD",  "Dictionary-Derived Term",                "text",           200,  "Derived",   "Sponsor",       "MT.COMBINED.MHDECOD",     "No"),
    ("MHCAT",    "Category for History",                   "text",            20,  "Assigned",  "Sponsor",       "MT.MIMIC.DIRECT",         "No"),
    ("MHEVDTYP", "Medical History Event Evidence Type",    "text",            30,  "Assigned",  "Sponsor",       "MT.MIMIC.DIRECT",         "No"),
    ("MHPRESP",  "Medical History Event Pre-Specified",    "text",             1,  "Protocol",  "Sponsor",       None,                      "No"),
    ("MHOCCUR",  "Medical History Event Occurrence",       "text",             1,  "Collected", "Investigator",  "MT.MIMIC.DIRECT",         "No"),
    ("MHSTAT",   "Completion Status",                      "text",            20,  "Collected", "Investigator",  "MT.MIMIC.DIRECT",         "No"),
    ("MHSTDTC",  "Start Date/Time of Medical History",     "incompleteDatetime",19,"Collected", "Investigator",  "MT.COMBINED.MHSTDTC",    "No"),
    ("MHDTC",    "Date/Time of Medical History",           "incompleteDatetime",19,"Collected", "Investigator",  "MT.COMBINED.MHDTC",       "No"),
    ("MHSTDY",   "Study Day of Start of Medical History",  "integer",          1,  "Derived",   "Sponsor",       "MT.MHSTDY.DAYSPLUS1",     "No"),
    ("MHDY",     "Study Day of Medical History Collection","integer",          1,  "Collected", "Investigator",  "MT.MIMIC.DIRECT",         "No"),
    ("MHSTRTPT", "Start Relative to Reference Time Point", "text",            10,  "Derived",   "Sponsor",       "MT.MHSTRTPT.CONDITIONAL", "No"),
    ("MHSTTPT",  "Start Reference Time Point",             "text",            20,  "Derived",   "Sponsor",       "MT.MHSTRTPT.CONDITIONAL", "No"),
    ("VISITNUM", "Visit Number",                           "integer",          2,  "Protocol",  "Sponsor",       "MT.MIMIC.DIRECT",         "No"),
    ("VISIT",    "Visit Name",                             "text",            25,  "Protocol",  "Sponsor",       "MT.MIMIC.DIRECT",         "No"),
]

KEY_SEQ     = {"STUDYID":1,"USUBJID":2,"MHSEQ":3}
VAR_CODELIST= {"MHPRESP":"CL.NY","MHOCCUR":"CL.NY","MHSTRTPT":"CL.STENRF"}

METHODDEFS = [
    {"OID":"MT.COMBINED.MHTERM","Name":"Algorithm to derive MHTERM (combined TCGA+MIMIC)","Type":"Computation",
     "Desc":("SOURCE DEPENDENT BY STUDYID. TCGA-BRCA: if histological_type=='Other  specify', "
             "MHTERM='Other specify - '||histologic_diagnosis_other. "
             "If histological_type=='Mixed Histology (please specify)', "
             "MHTERM='Mixed Histology (please specify) - '||histologic_diagnosis_other. "
             "Otherwise MHTERM=histological_type verbatim. 21 subjects trigger concat. "
             "MIMICIVBC: direct copy of MHTERM from MH.xlsx (ICD code string, e.g. 'C50919')."),
     "FExpr":("if STUDYID=='TCGA-BRCA':\n"
              "    if histological_type=='Other  specify':\n"
              "        MHTERM='Other specify - '+histologic_diagnosis_other\n"
              "    elif histological_type=='Mixed Histology (please specify)':\n"
              "        MHTERM='Mixed Histology (please specify) - '+histologic_diagnosis_other\n"
              "    else: MHTERM=histological_type\n"
              "elif STUDYID=='MIMICIVBC': MHTERM=MH_xlsx.MHTERM"),
     "FCtx":"Python 3.x pandas"},
    {"OID":"MT.COMBINED.MHDECOD","Name":"Algorithm to derive MHDECOD (combined TCGA+MIMIC)","Type":"Computation",
     "Desc":("SOURCE DEPENDENT BY STUDYID. TCGA-BRCA: map icd_o_3_histology code to text via "
             "icd-o-3_code_to_text.xlsx (13 codes, full coverage). 4 subjects have MHTERM/MHDECOD "
             "mismatch (TCGA-BH-A0HL, TCGA-EW-A1OW, TCGA-EW-A1OX, TCGA-EW-A1PE). "
             "MIMICIVBC: direct copy of MHDECOD from MH.xlsx (ICD description text)."),
     "FExpr":("if STUDYID=='TCGA-BRCA':\n"
              "    lookup=pd.read_excel('icd-o-3_code_to_text.xlsx').set_index('icd_o_3_code')['icd_o_3_text']\n"
              "    MHDECOD=icd_o_3_histology.map(lookup)\n"
              "elif STUDYID=='MIMICIVBC': MHDECOD=MH_xlsx.MHDECOD"),
     "FCtx":"Python 3.x pandas"},
    {"OID":"MT.COMBINED.MHSTDTC","Name":"Algorithm to derive MHSTDTC (combined TCGA+MIMIC)","Type":"Computation",
     "Desc":("SOURCE DEPENDENT BY STUDYID. TCGA-BRCA: source=initial_pathologic_dx_year. "
             "If matches ^\\d{4}$, assign as-is (year-only ISO8601). "
             "If sentinel '[Not Available]', MHSTDTC is blank (2 subjects). "
             "MIMICIVBC: direct copy MHSTDTC from MH.xlsx (full ISO8601 datetime). "
             "CONFORMANCE NOTE: mixed precision (year-only vs datetime) — DataType=incompleteDatetime."),
     "FExpr":("if STUDYID=='TCGA-BRCA':\n"
              "    MHSTDTC=initial_pathologic_dx_year.where(year.str.match(r'^\\d{4}$'),'')\n"
              "elif STUDYID=='MIMICIVBC': MHSTDTC=MH_xlsx.MHSTDTC"),
     "FCtx":"Python 3.x pandas"},
    {"OID":"MT.COMBINED.MHDTC","Name":"Algorithm to derive MHDTC (combined TCGA+MIMIC)","Type":"Computation",
     "Desc":("SOURCE DEPENDENT BY STUDYID. TCGA-BRCA: source=form_completion_date (YYYY-M-D). "
             "Reformatted to zero-padded YYYY-MM-DD via pd.to_datetime. All 385 populated. "
             "MIMICIVBC: direct copy MHDTC from MH.xlsx (full ISO8601 datetime). "
             "CONFORMANCE NOTE: mixed precision — DataType=incompleteDatetime."),
     "FExpr":("if STUDYID=='TCGA-BRCA':\n"
              "    MHDTC=pd.to_datetime(form_completion_date,errors='coerce').dt.strftime('%Y-%m-%d').fillna('')\n"
              "elif STUDYID=='MIMICIVBC': MHDTC=MH_xlsx.MHDTC"),
     "FCtx":"Python 3.x pandas"},
    {"OID":"MT.MHSTDY.DAYSPLUS1","Name":"Algorithm to derive MHSTDY (TCGA-BRCA only)","Type":"Computation",
     "Desc":("TCGA-BRCA ONLY. Blank for MIMICIVBC rows. "
             "MHSTDY=days_to_initial_pathologic_diagnosis+1. "
             "Source=0 for all 385 cohort subjects; MHSTDY=1 for all."),
     "FExpr":("if STUDYID=='TCGA-BRCA':\n"
              "    MHSTDY=pd.to_numeric(days_to_initial_pathologic_diagnosis,errors='coerce')+1\n"
              "elif STUDYID=='MIMICIVBC': MHSTDY=''"),
     "FCtx":"Python 3.x pandas"},
    {"OID":"MT.MHSTRTPT.CONDITIONAL","Name":"Algorithm to derive MHSTRTPT and MHSTTPT (TCGA-BRCA only)","Type":"Computation",
     "Desc":("TCGA-BRCA ONLY. Both blank for MIMICIVBC rows. "
             "Populated iff initial_pathologic_dx_year=='[Not Available]' (exact match). "
             "MHSTRTPT='BEFORE', MHSTTPT='SCREENING'. "
             "2 subjects triggered: TCGA-HN-A2NL, TCGA-HN-A2OB."),
     "FExpr":("if STUDYID=='TCGA-BRCA':\n"
              "    trigger=(initial_pathologic_dx_year=='[Not Available]')\n"
              "    MHSTRTPT=trigger.map({True:'BEFORE',False:''})\n"
              "    MHSTTPT=trigger.map({True:'SCREENING',False:''})\n"
              "elif STUDYID=='MIMICIVBC': MHSTRTPT=MHSTTPT=''"),
     "FCtx":"Python 3.x pandas"},
    {"OID":"MT.MIMIC.DIRECT","Name":"Algorithm for MIMIC-IV direct-copy variables","Type":"Computation",
     "Desc":("MIMICIVBC ONLY. Variables copied directly from MH.xlsx with no transformation: "
             "USUBJID, MHSEQ, MHCAT, MHOCCUR, MHSTAT, MHDY, VISITNUM, VISIT, MHEVDTYP. "
             "SPEC GAP: MH.xlsx is itself a pre-mapped SDTM output, not raw RWD. "
             "True lineage requires tracing back to MIMIC-IV PostgreSQL "
             "(tables: hosp.diagnoses_icd, hosp.admissions, hosp.patients)."),
     "FExpr":"if STUDYID=='MIMICIVBC': <variable>=MH_xlsx.<variable>  # direct copy",
     "FCtx":"Python 3.x pandas concat"},
]

CODELISTS = [
    ("CL.MHCAT.COMBINED","Medical History Category (Combined)","text",None,"Yes",
     [("TCGA-PATIENT",None),("MALIGNANCY HISTORY",None)]),
    ("CL.NY","No Yes Response","text","STD.CT.SDTM.2023",None,
     [("Y","C66742"),("N","C49487")]),
    ("CL.STENRF","Start/End Relative to Reference Time Point","text","STD.CT.SDTM.2023",None,
     [("BEFORE","C25629"),("AFTER","C25630"),("COINCIDENT","C25551"),
      ("ONGOING","C25669"),("UNKNOWN","C17998")]),
]

# ===========================================================================
# STEP 1: Define-XML 2.1
# ===========================================================================
log(); log("STEP 1: Building define_combined_mh.xml"); log("-"*50)

odm = ET.Element(ot("ODM"))
odm.set("ODMVersion","1.3.2"); odm.set("FileType","Snapshot")
odm.set("FileOID","RWDL.COMBINED.MH.DEFINE.001")
odm.set("CreationDateTime",NOW)
odm.set("Originator","TCGA-BRCA + MIMIC-IV MH Pipeline")
odm.set(dt("Context"),"Submission")

study = sub(odm,"Study",OID="STUDY.COMBINED.BRCA.MH")
gv = sub(study,"GlobalVariables")
sub(gv,"StudyName").text = "Combined TCGA-BRCA + MIMIC-IV Breast Cancer MH Domain"
sub(gv,"StudyDescription").text = (
    "Medical History (MH) domain — combined 394 subjects "
    "(385 TCGA-BRCA + 9 MIMIC-IV). "
    "Lineage: rwd_lineage_combined_mh_celllevel.xml.")
sub(gv,"ProtocolName").text = "RWDL-COMBINED-BRCA-001"

mdv = sub(study,"MetaDataVersion",OID="MDV.COMBINED.MH.001",
          Name="Combined TCGA+MIMIC MH Domain Data Definitions v1")
mdv.set(dt("DefineVersion"),"2.1")
mdv.set("Description",
        "MH domain — 394 subjects (385 TCGA-BRCA, 9 MIMIC-IV), 19 variables. "
        "MHSTDTC/MHDTC use DataType=incompleteDatetime due to mixed precision.")
mdv.set(dt("CommentOID"),"COM.MDV.MIXEDPRECISION")

stds = dsub(mdv,"Standards")
for oid_,name,stype,ver,status,pset in [
    ("STD.SDTMIG-3.3",  "SDTMIG",  "IG","3.3",      "Final",None),
    ("STD.CT.SDTM.2023","CDISC/NCI","CT","2023-06-30","Final","SDTM"),
    ("STD.RWDL-1.0",    "RWDL",    "IG","1.0",       "Draft",None),
]:
    s=dsub(stds,"Standard",OID=oid_,Name=name,Type=stype,Version=ver,Status=status)
    if pset: s.set("PublishingSet",pset)

# CommentDefs
for com_oid, com_text in [
    ("COM.MDV.MIXEDPRECISION",
     "MHSTDTC and MHDTC contain values of mixed ISO 8601 precision: "
     "TCGA-BRCA=year-only for MHSTDTC, date-only for MHDTC; "
     "MIMIC-IV=full datetime for both. DataType=incompleteDatetime used for both."),
    ("COM.MHCAT.COMBINED",
     "MHCAT values differ by study: TCGA-BRCA='TCGA-PATIENT'; "
     "MIMICIVBC='MALIGNANCY HISTORY'. Both are sponsor-defined non-CT values."),
]:
    com = dsub(mdv,"CommentDef",OID=com_oid); tt_el(com,com_text)

supdoc = dsub(mdv,"SupplementalDoc")
dsub(supdoc,"DocumentRef",leafID="LF.RWDLINEAGE.COMBINED")
dsub(supdoc,"DocumentRef",leafID="LF.SPECGAPS")

igd = sub(mdv,"ItemGroupDef",
          OID="IG.MH.COMBINED",Domain="MH",Name="MH",
          Repeating="Yes",IsReferenceData="No",
          SASDatasetName="MH",Purpose="Tabulation")
igd.set(dt("Structure"),"One record per medical history event per subject")
igd.set(dt("ArchiveLocationID"),"LF.MH.COMBINED")
igd.set(dt("StandardOID"),"STD.SDTMIG-3.3")
igd.set(dt("CommentOID"),"COM.MDV.MIXEDPRECISION")
tt_el(igd,"Medical History — Combined TCGA-BRCA and MIMIC-IV")

for col,label,dtype,length,orig_type,orig_src,moid,mandatory in MH_VARS:
    ir=sub(igd,"ItemRef",
           ItemOID=ioid(col),
           OrderNumber=str([v[0] for v in MH_VARS].index(col)+1),
           Mandatory=mandatory)
    if col in KEY_SEQ: ir.set("KeySequence",str(KEY_SEQ[col]))
    if moid: ir.set("MethodOID",moid)

cls=dsub(igd,"Class"); cls.set("Name","EVENTS")
lf=dsub(igd,"leaf")
lf.set("ID","LF.MH.COMBINED"); lf.set(xl("href"),"MH.txt")
dsub(lf,"title").text="MH.txt"

for col,label,dtype,length,orig_type,orig_src,moid,_ in MH_VARS:
    idef=sub(mdv,"ItemDef",OID=ioid(col),Name=col,DataType=dtype,SASFieldName=col)
    if dtype in ("text","integer","float"): idef.set("Length",str(length))
    if col=="MHCAT": idef.set(dt("CommentOID"),"COM.MHCAT.COMBINED")
    tt_el(idef,label)
    if col in VAR_CODELIST: sub(idef,"CodeListRef",CodeListOID=VAR_CODELIST[col])
    orig=dsub(idef,"Origin"); orig.set("Type",orig_type); orig.set("Source",orig_src)
    if moid:
        od=sub(orig,"Description"); ott=sub(od,"TranslatedText")
        ott.set("xml:lang","en"); ott.text=f"See MethodDef {moid}."

for md in METHODDEFS:
    mdef=sub(mdv,"MethodDef",OID=md["OID"],Name=md["Name"],Type=md["Type"])
    tt_el(mdef,md["Desc"])
    fe=sub(mdef,"FormalExpression"); fe.set("Context",md["FCtx"]); fe.text=md["FExpr"]

for cl_oid,cl_name,cl_dt,std_oid,is_nonstd,items in CODELISTS:
    cl=sub(mdv,"CodeList",OID=cl_oid,Name=cl_name,DataType=cl_dt)
    if std_oid: cl.set(dt("StandardOID"),std_oid)
    if is_nonstd: cl.set(dt("IsNonStandard"),is_nonstd)
    for cv,nci in items:
        ei=sub(cl,"EnumeratedItem",CodedValue=cv)
        if nci: sub(ei,"Alias",Context="nci:ExtCodeID",Name=nci)

for lid,href,title in [
    ("LF.MH.COMBINED",       "MH.txt",             "Combined TCGA+MIMIC MH Dataset"),
    ("LF.RWDLINEAGE.COMBINED","rwd_lineage_combined_mh_celllevel.xml",  "RWD Lineage — Combined (cell-level)"),
    ("LF.SPECGAPS",           "rwdl_spec_gaps_combined.txt",            "RWDL Specification Gaps — Combined"),
]:
    lf=dsub(mdv,"leaf"); lf.set("ID",lid); lf.set(xl("href"),href)
    dsub(lf,"title").text=title

ET.indent(odm,space="  ")
out_str=('<?xml version="1.0" encoding="UTF-8"?>\n'
         '<?xml-stylesheet type="text/xsl" href="define2-1.xsl"?>\n'
         +ET.tostring(odm,encoding="unicode",xml_declaration=False))
DEFINE_OUT.write_text(out_str,encoding="utf-8")
log(f"  Written: {DEFINE_OUT}  ({DEFINE_OUT.stat().st_size:,} bytes)")

# ===========================================================================
# STEP 2: RWD-Lineage XML (cell-level)
# ===========================================================================
log(); log("STEP 2: Building rwd_lineage_combined_mh_celllevel.xml"); log("-"*50)

root_rl = ET.Element(rt("lineage"))
root_rl.set("CreationDateTime",NOW)
root_rl.set("FileOID","RWDL.COMBINED.MH.CELLLEVEL.v2")

sm=rsub(root_rl,"sourceMetadata")
rsub_d(sm,"source",{"OID":"SRC.TCGA.1","name":"TCGA-BRCA BCR Biotab Legacy Portal",
    "description":"nationwidechildrens_org_clinical_patient_brca.txt — 385 patients."})
rsub_d(sm,"source",{"OID":"SRC.MIMIC.1","name":"MIMIC-IV Breast Cancer MH Pre-Mapped Output",
    "description":"MH.xlsx — 9 MIMIC-IV subjects. SPEC GAP: source is pre-mapped SDTM, not raw RWD."})

all_omit=sorted(set(
    [c for c,(*_,inc) in TCGA_COL.items() if not inc]+
    [c for c,(*_,inc) in MIMIC_COL.items() if not inc]))
omit_el=rsub(root_rl,"OmittedColumns",
             reason="Hardcoded/derived-only/not-applicable columns have no RWD source cell. "
                    "See rwdl_spec_gaps_combined.txt.")
for col in all_omit:
    t=TCGA_COL.get(col,(None,"","",False)); m=MIMIC_COL.get(col,(None,"","",False))
    rsub(omit_el,"Column",name=col,note=f"TCGA: {t[2]}  |  MIMIC: {m[2]}")

n_mapids=0
for row_idx,row in combined.iterrows():
    studyid=row["STUDYID"]; usubjid=row["USUBJID"]; mhseq=row["MHSEQ"]
    tgt_row=row_idx+2; is_tcga=(studyid=="TCGA-BRCA")
    col_spec=TCGA_COL if is_tcga else MIMIC_COL; barcode=usubjid

    for col,(src_cols,tr_type,tr_desc,included) in col_spec.items():
        if not included: continue
        tgt_val=row.get(col,"")
        is_disc=is_tcga and (barcode in disc_set) and col in ("MHTERM","MHDECOD")

        if isinstance(src_cols,list):
            hist=tcga_keyed.loc[barcode,"histological_type"] if barcode in tcga_keyed.index else ""
            contributing=(src_cols if hist in
                          ("Other  specify","Mixed Histology (please specify)") else [src_cols[0]])
        else:
            contributing=[src_cols]

        for src_col in contributing:
            if is_tcga:
                src_val=(str(tcga_keyed.loc[barcode,src_col])
                         if barcode in tcga_keyed.index and src_col in tcga_keyed.columns else "")
                uri=TCGA_URI; rk_col="bcr_patient_barcode"; rk_val=barcode; fmt="TSV"
            else:
                mr=mimic_lookup.get((usubjid,mhseq),{})
                raw=mr.get(src_col,"")
                src_val="" if str(raw) in ("nan","NaN","<NA>","None") else str(raw)
                uri=MIMIC_URI; rk_col="USUBJID"; rk_val=usubjid; fmt="XLSX"

            note=tr_desc
            if is_disc: note+=f" [DATA QUALITY FLAG: MHTERM/MHDECOD mismatch for {barcode}.]"
            if col=="MHSTDTC" and is_tcga and src_val=="[Not Available]":
                note+=" [Source sentinel — target blank.]"
            if col in ("MHSTRTPT","MHSTTPT") and is_tcga:
                note+=(" [Conditional triggered.]" if src_val=="[Not Available]"
                       else f" [Source '{src_val}' — not triggered, target blank.]")
            if not is_tcga and src_val=="": note+=" [Source null in MIMIC pre-mapped file.]"

            uid=make_uuid(f"{studyid}::{uri}::{src_col}::{barcode}::{mhseq}"
                          f"|{TGT_FILE}::{col}::{tgt_row}")
            mapid=rsub(root_rl,"MapID",uuid=uid)
            moid=MT.get(col)
            if moid and (not is_tcga or col in
                         ("MHTERM","MHDECOD","MHSTDTC","MHDTC","MHSTDY","MHSTRTPT","MHSTTPT")):
                mapid.set("MethodDefOID",moid)

            xf=rsub(mapid,"Transformation",type=tr_type); xf.text=note
            se=rsub(mapid,"Source"); sc_el=rsub(se,"Coordinate",storage="FILESYSTEM",structure="TABULAR")
            rsub(sc_el,"URI").text=uri
            rk=rsub(sc_el,"RowKey",column=rk_col); rk.text=rk_val
            rsub(sc_el,"ColumnName").text=src_col
            rsub(sc_el,"SourceValue").text=src_val
            rsub(sc_el,"Format").text=fmt
            te=rsub(mapid,"Target"); tc_el=rsub(te,"Coordinate",storage="FILESYSTEM",structure="TABULAR")
            rsub(tc_el,"URI").text=TGT_FILE
            rsub(tc_el,"RowIndex").text=str(tgt_row)
            rsub(tc_el,"ColumnName").text=col
            rsub(tc_el,"TargetValue").text=tgt_val
            rsub(tc_el,"Format").text="TSV"
            n_mapids+=1

log(f"  Generated {n_mapids:,} MapIDs")
all_uuids=[m.get("uuid") for m in root_rl.findall(rt("MapID"))]
assert len(set(all_uuids))==len(all_uuids),"UUID collision!"
log(f"  All {len(all_uuids):,} UUIDs unique")

ET.indent(root_rl,space="  ")
LINEAGE_OUT.write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(root_rl,encoding="unicode"),
    encoding="utf-8")
log(f"  Written: {LINEAGE_OUT}  ({LINEAGE_OUT.stat().st_size/1024:,.0f} KB)")

# ===========================================================================
# STEP 3: QC Checks
# ===========================================================================
log(); log("="*60); log("STEP 3: QC CHECKS"); log("="*60)

dr2=ET.parse(str(DEFINE_OUT)).getroot()
mdv2=dr2.find(f".//{ot('MetaDataVersion')}")
igd2=dr2.find(f".//{ot('ItemGroupDef')}")
irefs2=igd2.findall(ot("ItemRef")) if igd2 is not None else []
idefs2=dr2.findall(f".//{ot('ItemDef')}")
mdefs2=dr2.findall(f".//{ot('MethodDef')}")
mdef_oids2={m.get("OID") for m in mdefs2}
cls2=dr2.findall(f".//{ot('CodeList')}")
com2=dr2.findall(f".//{dt('CommentDef')}")
leaves2={l.get("ID") for l in dr2.findall(f".//{dt('leaf')}")}
stds2={s.get("OID") for s in dr2.findall(f".//{dt('Standard')}")}

qc("Define-XML well-formed (no parse error)",True)
qc("ODM root",dr2.tag==ot("ODM"))
qc("def:Context=Submission",dr2.get(dt("Context"))=="Submission")
qc("def:DefineVersion=2.1",mdv2 is not None and mdv2.get(dt("DefineVersion"))=="2.1")
qc("MDV def:CommentOID set",mdv2 is not None and mdv2.get(dt("CommentOID"))=="COM.MDV.MIXEDPRECISION")
qc("3 def:Standards",len(stds2)==3,f"found {len(stds2)}")
qc("SDTMIG-3.3 present","STD.SDTMIG-3.3" in stds2)
qc("CT standard present","STD.CT.SDTM.2023" in stds2)
qc("RWDL-1.0 present","STD.RWDL-1.0" in stds2)
qc("ItemGroupDef OID=IG.MH.COMBINED",igd2 is not None and igd2.get("OID")=="IG.MH.COMBINED")
qc("def:Class=EVENTS",igd2 is not None and igd2.find(dt("Class")) is not None
   and igd2.find(dt("Class")).get("Name")=="EVENTS")
qc("19 ItemRefs",len(irefs2)==19,f"found {len(irefs2)}")
key2={ir.get("ItemOID"):ir.get("KeySequence") for ir in irefs2 if ir.get("KeySequence")}
qc("KeySequence STUDYID=1",key2.get(ioid("STUDYID"))=="1")
qc("KeySequence USUBJID=2",key2.get(ioid("USUBJID"))=="2")
qc("KeySequence MHSEQ=3",  key2.get(ioid("MHSEQ"))  =="3")
qc("19 ItemDefs",len(idefs2)==19,f"found {len(idefs2)}")
missing_oids={ioid(c) for c,*_ in MH_VARS}-{d.get("OID") for d in idefs2}
qc("All ItemDef OIDs present",len(missing_oids)==0,
   f"missing:{missing_oids}" if missing_oids else "")
bad_orig=[d.get("Name") for d in idefs2 if d.find(dt("Origin")) is None]
qc("All ItemDefs have def:Origin",len(bad_orig)==0)
bad_src=[d.get("Name") for d in idefs2
         if d.find(dt("Origin")) is not None and not d.find(dt("Origin")).get("Source")]
qc("All def:Origin have Type+Source",len(bad_src)==0)
qc("7 MethodDefs",len(mdefs2)==7,f"found {len(mdefs2)}")
exp_moids={md["OID"] for md in METHODDEFS}
qc("All MethodDef OIDs present",exp_moids==mdef_oids2)
bad_fe=[m.get("OID") for m in mdefs2 if m.find(ot("FormalExpression")) is None]
qc("All MethodDefs have FormalExpression",len(bad_fe)==0)
ref_moids={ir.get("MethodOID") for ir in irefs2 if ir.get("MethodOID")}
bad_moids=ref_moids-mdef_oids2
qc("All ItemRef MethodOIDs resolve",len(bad_moids)==0,
   f"unresolved:{bad_moids}" if bad_moids else f"{len(ref_moids)} refs resolve")
qc("3 CodeLists",len(cls2)==3)
qc("2 CommentDefs",len(com2)==2)
qc("LF.MH.COMBINED leaf present",       "LF.MH.COMBINED"        in leaves2)
qc("LF.RWDLINEAGE.COMBINED leaf present","LF.RWDLINEAGE.COMBINED" in leaves2)
qc("LF.SPECGAPS leaf present",           "LF.SPECGAPS"            in leaves2)
qc("MHSTDTC DataType=incompleteDatetime",
   dr2.find(f".//{ot('ItemDef')}[@OID='{ioid('MHSTDTC')}']") is not None and
   dr2.find(f".//{ot('ItemDef')}[@OID='{ioid('MHSTDTC')}']").get("DataType")=="incompleteDatetime")
qc("MHDTC DataType=incompleteDatetime",
   dr2.find(f".//{ot('ItemDef')}[@OID='{ioid('MHDTC')}']") is not None and
   dr2.find(f".//{ot('ItemDef')}[@OID='{ioid('MHDTC')}']").get("DataType")=="incompleteDatetime")

lr2=ET.parse(str(LINEAGE_OUT)).getroot()
mapids2=lr2.findall(rt("MapID"))
all_uuids2=[m.get("uuid") for m in mapids2]
qc("Lineage well-formed XML",True)
qc("rwdl:lineage root",lr2.tag==rt("lineage"))
qc("sourceMetadata present",lr2.find(rt("sourceMetadata")) is not None)
qc("2 source elements",len(lr2.findall(f".//{rt('source')}"))==2)
qc(f"3,218 MapIDs",len(mapids2)==3218,f"found {len(mapids2)}")
qc("All MapID UUIDs unique",len(set(all_uuids2))==len(all_uuids2))
lin_moids={m.get("MethodDefOID") for m in mapids2 if m.get("MethodDefOID")}
bad_lin_moids=lin_moids-mdef_oids2
qc("All lineage MethodDefOIDs resolve to Define-XML MethodDef",len(bad_lin_moids)==0,
   f"unresolved:{bad_lin_moids}" if bad_lin_moids else f"{len(lin_moids)} resolve")

n_pass=sum(1 for _,p,_ in _qc if p)
n_fail=sum(1 for _,p,_ in _qc if not p)
log(); log(f"QC summary: {n_pass} PASS, {n_fail} FAIL out of {len(_qc)} checks")

# ===========================================================================
# STEP 4: CSV renderings
# ===========================================================================
log(); log("STEP 4: Building CSV renderings"); log("-"*50)

def gtext_el(parent, tag, ns=ODM_NS):
    el=parent.find(f"{{{ns}}}{tag}") if parent is not None else None
    return (el.text or "").strip() if el is not None else ""

# Define-XML CSV
rows_def=[]
def blank_d():
    return {k:"" for k in ["section","OID","Name","Type","Version","PublishingSet","Status",
                            "Domain","Repeating","Purpose","SASDatasetName","def_Structure",
                            "def_Class","def_StandardOID","def_ArchiveLocationID","def_CommentOID",
                            "ItemOID","OrderNumber","Mandatory","KeySequence","MethodOID",
                            "DataType","Length","SASFieldName","Label","Origin_Type",
                            "Origin_Source","CodeListOID","Description","FormalExpression_Context",
                            "FormalExpression","def_IsNonStandard","CodedValues_with_NCICodes",
                            "xlink_href","Title","Comment"]}

for com in dr2.findall(f".//{dt('CommentDef')}"):
    tt=com.find(f".//{ot('TranslatedText')}")
    r=blank_d(); r["section"]="CommentDef"; r["OID"]=com.get("OID","")
    r["Comment"]=(tt.text or "").strip() if tt is not None else ""; rows_def.append(r)

for s in dr2.findall(f".//{dt('Standard')}"):
    r=blank_d(); r["section"]="Standard"
    r["OID"]=s.get("OID",""); r["Name"]=s.get("Name",""); r["Type"]=s.get("Type","")
    r["Version"]=s.get("Version",""); r["PublishingSet"]=s.get("PublishingSet","")
    r["Status"]=s.get("Status",""); rows_def.append(r)

if igd2 is not None:
    cls_el=igd2.find(dt("Class"))
    r=blank_d(); r["section"]="ItemGroupDef"; r["OID"]=igd2.get("OID","")
    r["Name"]=igd2.get("Name",""); r["Domain"]=igd2.get("Domain","")
    r["Repeating"]=igd2.get("Repeating",""); r["Purpose"]=igd2.get("Purpose","")
    r["SASDatasetName"]=igd2.get("SASDatasetName","")
    r["def_Structure"]=igd2.get(dt("Structure"),"")
    r["def_Class"]=cls_el.get("Name","") if cls_el is not None else ""
    r["def_StandardOID"]=igd2.get(dt("StandardOID"),"")
    r["def_ArchiveLocationID"]=igd2.get(dt("ArchiveLocationID"),"")
    r["def_CommentOID"]=igd2.get(dt("CommentOID"),""); rows_def.append(r)

for ir in irefs2:
    r=blank_d(); r["section"]="ItemRef"; r["ItemOID"]=ir.get("ItemOID","")
    r["OrderNumber"]=ir.get("OrderNumber",""); r["Mandatory"]=ir.get("Mandatory","")
    r["KeySequence"]=ir.get("KeySequence",""); r["MethodOID"]=ir.get("MethodOID","")
    rows_def.append(r)

for idef in idefs2:
    tt=idef.find(f".//{ot('TranslatedText')}"); orig=idef.find(dt("Origin"))
    clrf=idef.find(ot("CodeListRef"))
    r=blank_d(); r["section"]="ItemDef"; r["OID"]=idef.get("OID","")
    r["Name"]=idef.get("Name",""); r["DataType"]=idef.get("DataType","")
    r["Length"]=idef.get("Length",""); r["SASFieldName"]=idef.get("SASFieldName","")
    r["Label"]=(tt.text or "").strip() if tt is not None else ""
    r["Origin_Type"]=orig.get("Type","") if orig is not None else ""
    r["Origin_Source"]=orig.get("Source","") if orig is not None else ""
    r["CodeListOID"]=clrf.get("CodeListOID","") if clrf is not None else ""
    rows_def.append(r)

for mdef in mdefs2:
    tt=mdef.find(f".//{ot('TranslatedText')}"); fe=mdef.find(ot("FormalExpression"))
    r=blank_d(); r["section"]="MethodDef"; r["OID"]=mdef.get("OID","")
    r["Name"]=mdef.get("Name",""); r["Type"]=mdef.get("Type","")
    r["Description"]=(tt.text or "").strip() if tt is not None else ""
    r["FormalExpression_Context"]=fe.get("Context","") if fe is not None else ""
    r["FormalExpression"]=(fe.text or "").strip() if fe is not None else ""
    rows_def.append(r)

for cl in cls2:
    items=[]; 
    for ei in cl.findall(ot("EnumeratedItem")):
        al=ei.find(ot("Alias")); nci=f" [{al.get('Name','')}]" if al is not None else ""
        items.append(ei.get("CodedValue","")+nci)
    r=blank_d(); r["section"]="CodeList"; r["OID"]=cl.get("OID","")
    r["Name"]=cl.get("Name",""); r["DataType"]=cl.get("DataType","")
    r["def_StandardOID"]=cl.get(dt("StandardOID"),"")
    r["def_IsNonStandard"]=cl.get(dt("IsNonStandard"),"")
    r["CodedValues_with_NCICodes"]="; ".join(items); rows_def.append(r)

for lid in dr2.findall(f".//{dt('leaf')}"):
    ttl=lid.find(dt("title"))
    r=blank_d(); r["section"]="Leaf"; r["OID"]=lid.get("ID","")
    r["xlink_href"]=lid.get(xl("href"),"")
    r["Title"]=(ttl.text or "").strip() if ttl is not None else ""; rows_def.append(r)

df_def=pd.DataFrame(rows_def); df_def=df_def.loc[:,(df_def!="").any(axis=0)]
df_def.to_csv(DEFINE_CSV,index=False)
log(f"  Written: {DEFINE_CSV}  ({len(df_def)} rows)")

# Lineage CSV
rows_lin=[]
def gtext2(p,tag):
    el=p.find(rt(tag)) if p is not None else None
    return (el.text or "").strip() if el is not None else ""
def gattr2(el,attr,d=""):
    return el.get(attr,d) if el is not None else d

for src in lr2.findall(f".//{rt('source')}"):
    rows_lin.append({"section":"sourceMetadata","uuid":"","MethodDefOID":"",
        "Transformation_type":"","Transformation":"","src_storage":"","src_structure":"",
        "src_URI":"","src_RowKey_column":"","src_RowKey_value":"","src_ColumnName":"",
        "src_SourceValue":"","src_Format":"","tgt_storage":"","tgt_structure":"",
        "tgt_URI":"","tgt_RowIndex":"","tgt_ColumnName":"","tgt_TargetValue":"","tgt_Format":"",
        "src_OID":src.get("OID",""),"src_name":src.get("name",""),
        "src_description":src.get("description",""),"omit_name":"","omit_note":""})

omit2=lr2.find(rt("OmittedColumns"))
if omit2 is not None:
    for c in omit2.findall(rt("Column")):
        rows_lin.append({"section":"OmittedColumn","uuid":"","MethodDefOID":"",
            "Transformation_type":"","Transformation":"","src_storage":"","src_structure":"",
            "src_URI":"","src_RowKey_column":"","src_RowKey_value":"","src_ColumnName":"",
            "src_SourceValue":"","src_Format":"","tgt_storage":"","tgt_structure":"",
            "tgt_URI":"","tgt_RowIndex":"","tgt_ColumnName":"","tgt_TargetValue":"","tgt_Format":"",
            "src_OID":"","src_name":"","src_description":"",
            "omit_name":c.get("name",""),"omit_note":c.get("note","")})

for mapid in mapids2:
    xf=mapid.find(rt("Transformation")); se=mapid.find(rt("Source")); te=mapid.find(rt("Target"))
    sc=se.find(rt("Coordinate")) if se is not None else None
    tc=te.find(rt("Coordinate")) if te is not None else None
    rk=sc.find(rt("RowKey")) if sc is not None else None
    rows_lin.append({"section":"MapID",
        "uuid":mapid.get("uuid",""),"MethodDefOID":mapid.get("MethodDefOID",""),
        "Transformation_type":gattr2(xf,"type"),
        "Transformation":(xf.text or "")[:250] if xf is not None else "",
        "src_storage":gattr2(sc,"storage"),"src_structure":gattr2(sc,"structure"),
        "src_URI":gtext2(sc,"URI"),
        "src_RowKey_column":rk.get("column","") if rk is not None else "",
        "src_RowKey_value":(rk.text or "").strip() if rk is not None else "",
        "src_ColumnName":gtext2(sc,"ColumnName"),"src_SourceValue":gtext2(sc,"SourceValue"),
        "src_Format":gtext2(sc,"Format"),
        "tgt_storage":gattr2(tc,"storage"),"tgt_structure":gattr2(tc,"structure"),
        "tgt_URI":gtext2(tc,"URI"),"tgt_RowIndex":gtext2(tc,"RowIndex"),
        "tgt_ColumnName":gtext2(tc,"ColumnName"),"tgt_TargetValue":gtext2(tc,"TargetValue"),
        "tgt_Format":gtext2(tc,"Format"),
        "src_OID":"","src_name":"","src_description":"","omit_name":"","omit_note":""})

df_lin=pd.DataFrame(rows_lin); df_lin=df_lin.loc[:,(df_lin!="").any(axis=0)]
df_lin.to_csv(LINEAGE_CSV,index=False)
log(f"  Written: {LINEAGE_CSV}  ({len(df_lin)} rows)")

# ===========================================================================
# STEP 5: Build report
# ===========================================================================
REPORT_LINES=[]
def r(s=""): REPORT_LINES.append(s)

r("BUILD REPORT: Combined TCGA-BRCA + MIMIC-IV MH Domain XMLs")
r("="*65)
r()
r("SOURCE DATA")
r("-----------")
r(f"  Combined MH file : {COMBINED_FILE.name}  ({n_total} rows, {n_cols} cols)")
r(f"  TCGA source      : {TCGA_SRC_FILE.name}  ({n_tcga} subjects)")
r(f"  MIMIC source     : {MIMIC_SRC_FILE.name}  ({n_mimic} subjects)")
r(f"  Discrepancies    : {DISC_FILE.name}  (4 MHTERM/MHDECOD mismatches)")
r()
r("OUTPUTS")
r("-------")
for f in [DEFINE_OUT,DEFINE_CSV,LINEAGE_OUT,LINEAGE_CSV,REPORT_OUT]:
    size=f.stat().st_size if f.exists() else 0
    r(f"  {f.name:<55} {size:>10,} bytes")
r()
r("DEFINE-XML 2.1 STRUCTURE")
r("------------------------")
r(f"  StudyOID         : STUDY.COMBINED.BRCA.MH")
r(f"  MetaDataVersion  : MDV.COMBINED.MH.001  (def:DefineVersion=2.1)")
r(f"  def:Context      : Submission")
r(f"  def:Standards    : STD.SDTMIG-3.3 (Final), STD.CT.SDTM.2023 (Final), STD.RWDL-1.0 (Draft)")
r(f"  ItemGroupDef     : IG.MH.COMBINED  (Repeating=Yes, Class=EVENTS)")
r(f"  Key sequence     : STUDYID(1), USUBJID(2), MHSEQ(3)")
r(f"  ItemDefs         : {len(idefs2)} (one per column)")
r(f"  MethodDefs       : {len(mdefs2)} (see table below)")
r(f"  CodeLists        : {len(cls2)}")
r(f"  CommentDefs      : {len(com2)}")
r(f"  def:leaves       : {len(leaves2)}")
r()
r("  MethodDef OIDs and purpose:")
for md in METHODDEFS:
    r(f"    {md['OID']:<35} {md['Name']}")
r()
r("  Notable Design Decisions:")
r("    MHSTDTC DataType=incompleteDatetime (TCGA=year-only, MIMIC=full datetime)")
r("    MHDTC   DataType=incompleteDatetime (TCGA=date-only, MIMIC=full datetime)")
r("    COM.MDV.MIXEDPRECISION attached to both MDV and ItemGroupDef")
r("    COM.MHCAT.COMBINED documents different MHCAT values across studies")
r()
r("RWD-LINEAGE STRUCTURE (cell-level)")
r("-----------------------------------")
r(f"  FileOID          : RWDL.COMBINED.MH.CELLLEVEL.v2")
r(f"  Namespace        : {RWDL_NS}")
r(f"  Source systems   : 2 (SRC.TCGA.1, SRC.MIMIC.1)")
r(f"  Total MapIDs     : {len(mapids2):,}")
r(f"  Omitted columns  : {len(all_omit)} (documented in OmittedColumns block)")
r()
r("  MapID breakdown by study and target column:")
col_study=[]
for m in mapids2:
    tcn=m.find(f".//{rt('Target')}/{rt('Coordinate')}/{rt('ColumnName')}")
    su=m.find(f".//{rt('Source')}/{rt('Coordinate')}/{rt('URI')}")
    study="TCGA" if su is not None and "nationwidechildrens" in (su.text or "") else "MIMIC"
    col_study.append((tcn.text if tcn is not None else "",study))
ct=Counter(col_study)
r(f"  {'Column':<15} {'TCGA':>6} {'MIMIC':>6}")
r(f"  {'-'*15} {'-'*6} {'-'*6}")
all_cols=sorted(set(c for c,_ in col_study))
for col in all_cols:
    t=ct.get((col,"TCGA"),0); m=ct.get((col,"MIMIC"),0)
    r(f"  {col:<15} {t:>6} {m:>6}")
r(f"  {'TOTAL':<15} {sum(ct.get((c,'TCGA'),0) for c in all_cols):>6} "
  f"{sum(ct.get((c,'MIMIC'),0) for c in all_cols):>6}")
r()
r("  Coordinate schema:")
r("    TCGA source  : FILESYSTEM/TABULAR, URI=./nationwidechildrens_org_clinical_patient_brca.txt, Format=TSV")
r("    MIMIC source : FILESYSTEM/TABULAR, URI=MH.xlsx, Format=XLSX")
r("    All targets  : FILESYSTEM/TABULAR, URI=./MH.txt, Format=TSV")
r()
r("  Key spec gaps (see rwdl_spec_gaps_combined.txt for full detail):")
r("    C1: MIMIC source is pre-mapped SDTM, not raw RWD")
r("    C2: Mixed date precision in MHSTDTC and MHDTC")
r("    C3: MHTERM semantics differ (text vs ICD code) across studies")
r("    + all 10 gaps from rwdl_spec_gaps.txt (TCGA-only) also apply")
r()
r("="*65)
r("QC RESULTS")
r("="*65)
for label,passed,detail in _qc:
    status="PASS" if passed else "FAIL"
    r(f"  [{status}] {label}"+(f" -- {detail}" if detail else ""))
r()
r(f"Total: {n_pass} PASS, {n_fail} FAIL out of {len(_qc)} checks")

REPORT_OUT.write_text("\n".join(REPORT_LINES)+"\n",encoding="utf-8")
log(f"\nWrote: {REPORT_OUT}")
log("Done.")
