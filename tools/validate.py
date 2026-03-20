#!/usr/bin/env python3
"""
validate.py — RWD-Lineage XML Validation Tools
===============================================
Provides two validation functions:

  validate_rwd_lineage(xml_path)
      Validates an rwd-lineage.xml file against the rules defined in
      RWD-Lineage_Data_Standard_Specification.md.

  validate_define_xml(xml_path, xsd_path=None)
      Validates a define.xml file against the CDISC Define-XML 2.1 XSD
      schema using lxml, plus checks the required rwdl namespace extension.

Both return a ValidationResult(valid: bool, errors: list[str]).

CLI usage:
    python3 tools/validate.py rwd-lineage path/to/rwd-lineage.xml
    python3 tools/validate.py define-xml  path/to/define.xml [path/to/define2-1-0.xsd]
"""

from __future__ import annotations

import os
import sys
import re
import urllib.request
from collections import namedtuple
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Public return type
# ---------------------------------------------------------------------------

ValidationResult = namedtuple("ValidationResult", ["valid", "errors"])

# ---------------------------------------------------------------------------
# Namespace constants
# ---------------------------------------------------------------------------

RWDL_NS = "http://www.cdisc.org/ns/rwd-lineage/v1"
ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
DEF_NS = "http://www.cdisc.org/ns/def/v2.1"

VALID_STORAGE = {"Database", "Filesystem", "API"}
VALID_STRUCTURE = {"Tabular", "Tree", "Files"}

# Canonical URL for the Define-XML 2.1 XSD (with ODM 1.3.2 base)
# Falls back to bundled copy if download fails.
DEFINE_XSD_URL = (
    "https://raw.githubusercontent.com/cdisc-org/DataExchange-Define-XML"
    "/main/cdisc-define-2.1/define2-1-0.xsd"
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _q(ns: str, tag: str) -> str:
    """Return a Clark-notation qualified name: {ns}tag."""
    return f"{{{ns}}}{tag}"


def _attr(elem, name: str, default: str = "") -> str:
    return elem.get(name, default)


# ---------------------------------------------------------------------------
# validate_rwd_lineage
# ---------------------------------------------------------------------------

def validate_rwd_lineage(xml_path: str) -> ValidationResult:
    """Validate an rwd-lineage.xml file against the RWD-Lineage specification.

    Checks performed
    ----------------
    - Root element is <RWDLineage> in the correct namespace
    - Required root-level attributes are present
    - Every <MapID> has a uuid attribute
    - All uuid values are unique
    - Every <MapID> contains exactly one <Source> and one <Target>
    - Every <Source> and <Target> contains exactly one <Coordinate>
    - <Coordinate> storage attribute is a valid enum value
    - <Coordinate> structure attribute is a valid enum value
    - Every <Coordinate> has a <URI> child element
    - Tabular coordinates have <RowIndex> or <RowKey>, and <ColumnName>
    - Tree coordinates have a <Path> child element
    - Database coordinates have <Database> and <Schema> child elements

    Parameters
    ----------
    xml_path : str
        Path to the rwd-lineage.xml file to validate.

    Returns
    -------
    ValidationResult
        Named tuple with (valid: bool, errors: list[str]).
    """
    errors: list[str] = []

    # -- Parse --
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        return ValidationResult(False, [f"XML parse error: {exc}"])
    except FileNotFoundError:
        return ValidationResult(False, [f"File not found: {xml_path}"])

    root = tree.getroot()

    # -- Root element --
    expected_root = _q(RWDL_NS, "RWDLineage")
    if root.tag != expected_root:
        errors.append(
            f"Root element must be <RWDLineage> in namespace '{RWDL_NS}', "
            f"got '{root.tag}'"
        )

    # -- Required root attributes --
    required_root_attrs = [
        "FileType", "FileOID", "CreationDateTime", "AsOfDateTime", "Originator"
    ]
    for attr in required_root_attrs:
        if not _attr(root, attr):
            errors.append(f"Root <RWDLineage> is missing required attribute '{attr}'")

    # -- MapID elements --
    map_id_tag = _q(RWDL_NS, "MapID")
    source_tag = _q(RWDL_NS, "Source")
    target_tag = _q(RWDL_NS, "Target")
    coord_tag = _q(RWDL_NS, "Coordinate")
    uri_tag = _q(RWDL_NS, "URI")
    row_index_tag = _q(RWDL_NS, "RowIndex")
    row_key_tag = _q(RWDL_NS, "RowKey")
    col_name_tag = _q(RWDL_NS, "ColumnName")
    path_tag = _q(RWDL_NS, "Path")
    db_tag = _q(RWDL_NS, "Database")
    schema_tag = _q(RWDL_NS, "Schema")

    seen_uuids: dict[str, int] = {}

    for idx, map_id in enumerate(root.findall(map_id_tag), start=1):
        prefix = f"MapID[{idx}]"

        # uuid attribute
        uuid = _attr(map_id, "uuid")
        if not uuid:
            errors.append(f"{prefix}: missing required 'uuid' attribute")
        else:
            if uuid in seen_uuids:
                errors.append(
                    f"{prefix}: duplicate uuid '{uuid}' "
                    f"(first seen at MapID[{seen_uuids[uuid]}])"
                )
            else:
                seen_uuids[uuid] = idx

        # Source
        sources = map_id.findall(source_tag)
        if len(sources) != 1:
            errors.append(
                f"{prefix}: expected exactly 1 <Source>, found {len(sources)}"
            )

        # Target
        targets = map_id.findall(target_tag)
        if len(targets) != 1:
            errors.append(
                f"{prefix}: expected exactly 1 <Target>, found {len(targets)}"
            )

        # Validate each Source/Target coordinate
        for role, container_list in [("Source", sources), ("Target", targets)]:
            for container in container_list:
                coords = container.findall(coord_tag)
                if len(coords) != 1:
                    errors.append(
                        f"{prefix} <{role}>: expected exactly 1 <Coordinate>, "
                        f"found {len(coords)}"
                    )
                for coord in coords:
                    _validate_coordinate(
                        coord,
                        f"{prefix} <{role}><Coordinate>",
                        errors,
                        uri_tag, row_index_tag, row_key_tag,
                        col_name_tag, path_tag, db_tag, schema_tag,
                    )

    if not seen_uuids:
        errors.append("Document contains no <MapID> elements")

    return ValidationResult(len(errors) == 0, errors)


def _validate_coordinate(
    coord: ET.Element,
    path: str,
    errors: list[str],
    uri_tag, row_index_tag, row_key_tag, col_name_tag,
    path_tag, db_tag, schema_tag,
) -> None:
    """Validate a single <Coordinate> element and append errors in-place."""
    storage = _attr(coord, "storage")
    structure = _attr(coord, "structure")

    # Enum checks
    if not storage:
        errors.append(f"{path}: missing required 'storage' attribute")
    elif storage not in VALID_STORAGE:
        errors.append(
            f"{path}: invalid storage='{storage}'. "
            f"Allowed values: {sorted(VALID_STORAGE)}"
        )

    if not structure:
        errors.append(f"{path}: missing required 'structure' attribute")
    elif structure not in VALID_STRUCTURE:
        errors.append(
            f"{path}: invalid structure='{structure}'. "
            f"Allowed values: {sorted(VALID_STRUCTURE)}"
        )

    # URI is always required
    if coord.find(uri_tag) is None:
        errors.append(f"{path}: missing required <URI> child element")

    # Tabular: RowIndex or RowKey + ColumnName required
    if structure == "Tabular":
        has_row = (
            coord.find(row_index_tag) is not None
            or coord.find(row_key_tag) is not None
        )
        if not has_row:
            errors.append(
                f"{path}: structure='Tabular' requires a <RowIndex> or <RowKey> child"
            )
        if coord.find(col_name_tag) is None:
            errors.append(
                f"{path}: structure='Tabular' requires a <ColumnName> child"
            )

    # Tree: Path required
    if structure == "Tree":
        if coord.find(path_tag) is None:
            errors.append(
                f"{path}: structure='Tree' requires a <Path> child element"
            )

    # Database: Database + Schema required
    if storage == "Database":
        if coord.find(db_tag) is None:
            errors.append(
                f"{path}: storage='Database' requires a <Database> child element"
            )
        if coord.find(schema_tag) is None:
            errors.append(
                f"{path}: storage='Database' requires a <Schema> child element"
            )


# ---------------------------------------------------------------------------
# validate_define_xml
# ---------------------------------------------------------------------------

def validate_define_xml(
    xml_path: str,
    xsd_path: str | None = None,
) -> ValidationResult:
    """Validate a define.xml file against the CDISC Define-XML 2.1 XSD schema.

    Uses lxml for XSD validation. If lxml is not installed, XSD validation is
    skipped and a warning is included in the errors list. In either case, the
    function performs structural checks on the rwdl namespace extension block.

    Parameters
    ----------
    xml_path : str
        Path to the define.xml file to validate.
    xsd_path : str, optional
        Path to the Define-XML 2.1 XSD file. If None, the function will attempt
        to locate a cached copy in the same directory as this script, or download
        it from the CDISC GitHub repository.

    Returns
    -------
    ValidationResult
        Named tuple with (valid: bool, errors: list[str]).
    """
    errors: list[str] = []
    warnings: list[str] = []

    # -- Parse with stdlib first (fast, gives friendly error messages) --
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        return ValidationResult(False, [f"XML parse error: {exc}"])
    except FileNotFoundError:
        return ValidationResult(False, [f"File not found: {xml_path}"])

    root = tree.getroot()

    # -- Basic structural checks regardless of XSD --
    _validate_define_xml_structure(root, xml_path, errors, warnings)

    # -- XSD validation via lxml --
    try:
        from lxml import etree as lxml_etree
        xsd_errors = _xsd_validate(xml_path, xsd_path, lxml_etree)
        errors.extend(xsd_errors)
    except ImportError:
        warnings.append(
            "WARNING: lxml is not installed — XSD validation skipped. "
            "Install with: pip install lxml"
        )

    # Warnings are informational; only real errors affect validity
    all_messages = warnings + errors
    return ValidationResult(len(errors) == 0, all_messages)


def _validate_define_xml_structure(
    root: ET.Element,
    xml_path: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Structural checks on the define.xml that don't require XSD."""
    odm_tag = _q(ODM_NS, "ODM")

    # Root must be <ODM> in ODM namespace
    if root.tag != odm_tag:
        errors.append(
            f"Root element must be <ODM> in namespace '{ODM_NS}', got '{root.tag}'"
        )

    # Required ODM root attributes
    for attr in ("FileType", "FileOID", "CreationDateTime", "AsOfDateTime", "Originator"):
        if not _attr(root, attr):
            errors.append(f"<ODM>: missing required attribute '{attr}'")

    # Check rwdl namespace is declared
    # ElementTree strips namespace declarations so we check the raw text
    rwdl_ns_decl = f'xmlns:rwdl="{RWDL_NS}"'
    try:
        with open(xml_path, "r", encoding="utf-8") as fh:
            raw = fh.read(4096)  # namespace declarations are always near the top
        if rwdl_ns_decl not in raw:
            errors.append(
                f"Missing rwdl namespace declaration. "
                f"Expected: {rwdl_ns_decl}"
            )
    except OSError:
        pass  # already failed to parse above, skip raw check

    # Walk to MetaDataVersion > rwdl:lineage > rwdl:ref
    study_tag = _q(ODM_NS, "Study")
    mdv_tag = _q(ODM_NS, "MetaDataVersion")
    lineage_tag = _q(RWDL_NS, "lineage")
    ref_tag = _q(RWDL_NS, "ref")

    found_lineage = False
    found_ref = False

    for study in root.findall(study_tag):
        for mdv in study.findall(mdv_tag):
            lineage = mdv.find(lineage_tag)
            if lineage is not None:
                found_lineage = True
                ref = lineage.find(ref_tag)
                if ref is not None:
                    found_ref = True
                    leaf_id = _attr(ref, "leafID")
                    ref_text = (ref.text or "").strip()
                    if not leaf_id:
                        errors.append(
                            "<rwdl:ref> is missing the required 'leafID' attribute"
                        )
                    if not ref_text:
                        errors.append(
                            "<rwdl:ref> must contain the filename of the "
                            "rwd-lineage XML file as its text content"
                        )

    if not found_lineage:
        errors.append(
            "No <rwdl:lineage> element found inside <MetaDataVersion>. "
            "A Define-XML with RWD Lineage must include this extension block."
        )
    elif not found_ref:
        errors.append(
            "Found <rwdl:lineage> but it is missing a <rwdl:ref> child element."
        )

    # Check that the referenced leaf ID exists as a <def:leaf>
    if found_ref:
        def_leaf_tag = _q(DEF_NS, "leaf")
        leaf_ids = set()
        for elem in root.iter(def_leaf_tag):
            lid = _attr(elem, "ID")
            if lid:
                leaf_ids.add(lid)

        # Find all rwdl:ref leafIDs and verify each has a matching def:leaf
        for ref in root.iter(ref_tag):
            leaf_id = _attr(ref, "leafID")
            if leaf_id and leaf_id not in leaf_ids:
                errors.append(
                    f"<rwdl:ref leafID='{leaf_id}'> does not have a matching "
                    f"<def:leaf ID='{leaf_id}'> in the document"
                )


def _xsd_validate(
    xml_path: str,
    xsd_path: str | None,
    lxml_etree,
) -> list[str]:
    """Run lxml XSD validation and return a list of error strings."""
    errors: list[str] = []

    if xsd_path is None:
        xsd_path = _get_xsd_path(lxml_etree)

    if xsd_path is None:
        return [
            "Could not locate or download Define-XML XSD. "
            "Provide a path via xsd_path= or place define2-1-0.xsd in tools/schema/."
        ]

    try:
        with open(xsd_path, "rb") as fh:
            xsd_doc = lxml_etree.parse(fh)
        schema = lxml_etree.XMLSchema(xsd_doc)
    except Exception as exc:
        return [f"Failed to load XSD '{xsd_path}': {exc}"]

    try:
        xml_doc = lxml_etree.parse(xml_path)
    except Exception as exc:
        return [f"Failed to parse XML for XSD validation: {exc}"]

    if not schema.validate(xml_doc):
        for err in schema.error_log:
            errors.append(f"XSD error (line {err.line}): {err.message}")

    return errors


def _get_xsd_path(lxml_etree) -> str | None:
    """Return path to the Define-XML 2.1 XSD, downloading if necessary."""
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    schema_dir = os.path.join(tools_dir, "schema")
    cached_xsd = os.path.join(schema_dir, "define2-1-0.xsd")

    if os.path.isfile(cached_xsd):
        return cached_xsd

    # Attempt download
    os.makedirs(schema_dir, exist_ok=True)
    try:
        print(f"Downloading Define-XML XSD from {DEFINE_XSD_URL} ...", file=sys.stderr)
        urllib.request.urlretrieve(DEFINE_XSD_URL, cached_xsd)
        print(f"Saved to {cached_xsd}", file=sys.stderr)
        return cached_xsd
    except Exception as exc:
        print(f"Warning: could not download XSD: {exc}", file=sys.stderr)
        # Clean up partial download
        if os.path.exists(cached_xsd):
            os.remove(cached_xsd)
        return None


# ---------------------------------------------------------------------------
# validate_lineage_coverage
# ---------------------------------------------------------------------------

import csv as _csv  # noqa: E402  (imported here to keep top-level imports minimal)


def validate_lineage_coverage(
    sdtm_dir: str,
    lineage_xml_path: str,
) -> ValidationResult:
    """Check that every data cell in the SDTM CSV files has a lineage entry.

    For each CSV file in *sdtm_dir*, every combination of (row_index,
    column_name) for every data row is compared against the Target
    ``<Coordinate>`` elements in *lineage_xml_path*.  A match requires that the
    Target Coordinate's ``<URI>`` ends with the CSV filename (case-insensitive),
    its ``<RowIndex>`` equals the 1-based data-row number, and its
    ``<ColumnName>`` equals the column header.

    Two categories of issue are reported:

    * **Missing coverage** — a (file, row, column) combination exists in the
      SDTM data but has no corresponding Target Coordinate in the lineage.
    * **Phantom entries** — a Target Coordinate in the lineage refers to a
      (file, row, column) that does not exist in any SDTM CSV.

    Parameters
    ----------
    sdtm_dir : str
        Path to the directory containing SDTM CSV files.
    lineage_xml_path : str
        Path to the rwd-lineage.xml to check coverage against.

    Returns
    -------
    ValidationResult
        Named tuple with (valid: bool, errors: list[str]).
        ``valid`` is True only when there are no missing-coverage issues.
        Phantom entries are reported as warnings (prefixed ``WARNING:``) and
        do not affect the ``valid`` flag.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ------------------------------------------------------------------ #
    # 1. Build the full set of (filename_stem, row_index, column_name)    #
    #    from all CSV files in sdtm_dir.                                  #
    # ------------------------------------------------------------------ #

    if not os.path.isdir(sdtm_dir):
        return ValidationResult(False, [f"SDTM directory not found: {sdtm_dir}"])

    # sdtm_cells: maps (filename, row_idx, col) -> True
    sdtm_cells: set[tuple[str, int, str]] = set()
    # Also track which filenames exist (lowercased basename for fuzzy URI matching)
    sdtm_files: dict[str, str] = {}  # lower_basename -> actual_basename

    csv_files = sorted(
        f for f in os.listdir(sdtm_dir)
        if f.lower().endswith(".csv")
    )
    if not csv_files:
        return ValidationResult(False, [f"No CSV files found in {sdtm_dir}"])

    for csv_filename in csv_files:
        csv_path = os.path.join(sdtm_dir, csv_filename)
        sdtm_files[csv_filename.lower()] = csv_filename
        try:
            with open(csv_path, newline="", encoding="utf-8-sig") as fh:
                reader = _csv.DictReader(fh, skipinitialspace=True)
                for row_idx, row in enumerate(reader, start=1):
                    for col in row:
                        col = col.strip()
                        if col:
                            sdtm_cells.add((csv_filename.lower(), row_idx, col))
        except OSError as exc:
            errors.append(f"Could not read {csv_path}: {exc}")

    if errors:
        return ValidationResult(False, errors)

    # ------------------------------------------------------------------ #
    # 2. Parse the lineage XML and collect all Target coordinate tuples.  #
    # ------------------------------------------------------------------ #

    try:
        tree = ET.parse(lineage_xml_path)
    except ET.ParseError as exc:
        return ValidationResult(False, [f"XML parse error: {exc}"])
    except FileNotFoundError:
        return ValidationResult(False, [f"File not found: {lineage_xml_path}"])

    root = tree.getroot()

    map_id_tag = _q(RWDL_NS, "MapID")
    target_tag = _q(RWDL_NS, "Target")
    coord_tag = _q(RWDL_NS, "Coordinate")
    uri_tag = _q(RWDL_NS, "URI")
    row_index_tag = _q(RWDL_NS, "RowIndex")
    col_name_tag = _q(RWDL_NS, "ColumnName")

    # lineage_targets: set of (lower_filename, row_idx, col)
    lineage_targets: set[tuple[str, int, str]] = set()

    for map_id in root.findall(map_id_tag):
        target = map_id.find(target_tag)
        if target is None:
            continue
        coord = target.find(coord_tag)
        if coord is None:
            continue

        uri_el = coord.find(uri_tag)
        if uri_el is None:
            continue
        row_el = coord.find(row_index_tag)
        if row_el is None:
            continue
        col_el = coord.find(col_name_tag)
        if col_el is None:
            continue

        uri_text = (uri_el.text or "").strip()
        # Match the URI against known SDTM filenames by suffix
        matched_file: str = ""
        for lower_name in sdtm_files:
            if uri_text.lower().endswith(lower_name):
                matched_file = lower_name
                break

        if not matched_file:
            # Target points to a file outside the SDTM dir — not a phantom,
            # just not relevant to this coverage check.
            continue

        try:
            row_idx = int(row_el.text or "")
        except (ValueError, TypeError):
            continue

        col_name = (col_el.text or "").strip()
        lineage_targets.add((matched_file, row_idx, col_name))

    # ------------------------------------------------------------------ #
    # 3. Compare sets and report.                                         #
    # ------------------------------------------------------------------ #

    missing = sorted(sdtm_cells - lineage_targets)
    phantom = sorted(lineage_targets - sdtm_cells)

    for lower_name, row_idx, col in missing:
        actual_name = sdtm_files.get(lower_name, lower_name)
        errors.append(
            f"Missing lineage: {actual_name} row {row_idx}, column '{col}'"
        )

    for lower_name, row_idx, col in phantom:
        actual_name = sdtm_files.get(lower_name, lower_name)
        warnings.append(
            f"WARNING: Phantom lineage entry: {actual_name} row {row_idx}, "
            f"column '{col}' does not exist in the SDTM data"
        )

    # Summary line
    total_cells = len(sdtm_cells)
    covered = total_cells - len(missing)
    pct = int(100 * covered / total_cells) if total_cells else 0
    summary = (
        f"Coverage: {covered}/{total_cells} cells covered ({pct}%) "
        f"across {len(csv_files)} SDTM file(s)"
    )

    all_messages = [summary] + warnings + errors
    return ValidationResult(len(errors) == 0, all_messages)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _print_result(result: ValidationResult, label: str) -> None:
    status = "✅ VALID" if result.valid else "❌ INVALID"
    print(f"\n{status}  —  {label}")
    if result.errors:
        for msg in result.errors:
            if msg.startswith("WARNING:"):
                print(f"  ⚠️  {msg}")
            elif msg.startswith("Coverage:"):
                print(f"  ℹ️  {msg}")
            else:
                print(f"  ✗  {msg}")
    else:
        print("  No issues found.")


def main() -> int:
    usage = (
        "Usage:\n"
        "  python3 tools/validate.py rwd-lineage <path/to/rwd-lineage.xml>\n"
        "  python3 tools/validate.py define-xml  <path/to/define.xml> [path/to/define2-1-0.xsd]\n"
        "  python3 tools/validate.py coverage    <path/to/sdtm/dir> <path/to/rwd-lineage.xml>\n"
    )

    if len(sys.argv) < 3:
        print(usage)
        return 1

    mode = sys.argv[1].lower()

    if mode in ("rwd-lineage", "rwd_lineage", "rwdlineage"):
        result = validate_rwd_lineage(sys.argv[2])
        _print_result(result, sys.argv[2])
    elif mode in ("define-xml", "define_xml", "definexml"):
        xsd_path = sys.argv[3] if len(sys.argv) > 3 else None
        result = validate_define_xml(sys.argv[2], xsd_path)
        _print_result(result, sys.argv[2])
    elif mode == "coverage":
        if len(sys.argv) < 4:
            print("coverage mode requires two arguments: <sdtm_dir> <rwd-lineage.xml>")
            print(usage)
            return 1
        result = validate_lineage_coverage(sys.argv[2], sys.argv[3])
        _print_result(result, f"{sys.argv[2]} → {sys.argv[3]}")
    else:
        print(f"Unknown mode '{mode}'. {usage}")
        return 1

    return 0 if result.valid else 2


if __name__ == "__main__":
    sys.exit(main())
