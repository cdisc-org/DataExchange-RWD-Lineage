# RWD-Lineage Data Standard Specification — DRAFT



## Introduction

RWD Lineage is a machine-readable CDISC data exchange standard for lineage metadata supplied along with RWD-derived SDTM. It provides the data reliability required by FDA to use RWE as primary evidence.

RWD Lineage is an XML-formatted addition/extension to Define-XML. It should be implemented as a Namespace Extension to Define-XML. It can be embedded directly using a custom tag (e.g., `rwdl:Lineage`) or referenced as a separate XML file.



## Top-level Metadata Attributes

### Lineage Trail Attributes

The following table defines the attributes for a single Lineage Map element (Source–Target Pair).

| Order | Attribute | XML Data Type | Usage | Description |
|-------|-----------|---------------|-------|-------------|
| 1 | `uuid` | string (UUIDv5) | Required | A deterministic UUID generated from a hash of the Source+Target coordinates. Ensures ID constancy across regenerations. |
| 2 | `MethodDefOID` | string | Optional | A reference to MethodDefOID. |
| 3 | `Source` | Coordinate Object | Required | The Data Point representing the origin (RWD). |
| 4 | `Target` | Coordinate Object | Required | The Data Point representing the destination (SDTM). |



### Coordinates Attributes

The following table defines the attributes available within a Coordinate Object. Usage depends on the storage and structure types selected.

| Order | Attribute | XML Data Type | Usage | Description |
|-------|-----------|---------------|-------|-------------|
| 1 | `storage` | string (Enum) | Required | The container type. Allowed values: `Database`, `Filesystem`, `API`, `Messages`. |
| 2 | `structure` | string (Enum) | Required | The internal organization. Allowed values: `Tabular`, `Tree`, `Files`. |
| 3 | `URI` | string | Conditional | The full connection string, file path, or API endpoint. |
| 4 | `Database` | string | Conditional | The specific database name (Required for `storage="Database"`). |
| 5 | `Schema` | string | Conditional | The schema name (Required for `storage="Database"`). |
| 6 | `Table` | string | Conditional | The table name (Required for `storage="Database"`). |
| 7 | `RowIndex` | integer | Conditional | The row number (One of `RowIndex` or `RowKey` required for `structure="Tabular"`). |
| 8 | `RowKey` | string/integer | Conditional | The Primary Key field (One of `RowIndex` or `RowKey` required for `structure="Tabular"`). |
| 9 | `RowKeyValue` | string/integer | Conditional | The Primary Key value (Required if `RowKey` is used). |
| 10 | `ColumnName` | string | Conditional | The header/variable name (Required for `structure="Tabular"`). |
| 11 | `Path` | string | Conditional | The navigation string (XPath/JSONPath) (Required for `structure="Tree"`). |
| 12 | `Format` | string | Optional | The specific format of the file or response (e.g., "JSON", "XML", "CSV"). |

### Coordinates

List of supported coordinates — designed to be extensible by defining the `structure` attribute in the XML schema (e.g., `type="Graph"` or `type="Stream"`).

#### Structural Formats

- **Tabular** — Data organized in a row-and-column format (e.g., CSV, SQL Tables, SAS Datasets).
- **Tree** — Data organized in a hierarchical, nested format (e.g., JSON, XML, FHIR resources).
- **Files** — Data treated as a singular object or blob within a directory structure (e.g., PDF reports, images).

**Scope:**
- *In Scope (Current):* Deterministic, static structures where a value's location can be explicitly defined by a rigid index, key, or path (e.g., "Row 5, Col A" or `$.patient.id`).
- *Out of Scope (Extensible):* Non-deterministic or unstructured data requiring semantic interpretation (e.g., free-text clinical notes requiring NLP, video/audio streams, graph databases relying on complex pattern matching).

#### Storage Formats

- **Database** — Structured data engines requiring connection protocols (e.g., SQL, NoSQL).
- **Filesystem** — Flat files stored on a local disk, network drive, or object storage (e.g., S3).
- **API** — Data accessible via web service endpoints (e.g., REST, SOAP).

**Scope:**
- *In Scope (Current):* Standard digital repositories accessible via common, widely supported protocols (JDBC/ODBC, POSIX/S3, HTTP/REST).
- *Out of Scope (Extensible):* Physical media (paper records requiring OCR), proprietary legacy systems without standard connectivity, and Distributed Ledger Technology (blockchain).

### Lineage Trail Attributes

**Data Point** — An object representing a specific value at a specific, uniquely identifiable location.

- **Unique ID** — A UUID (v5) generated deterministically from the Source+Target coordinates. Ensures the ID remains constant if lineage is regenerated for the same data points.
- **Transformation** *(Optional)* — A description or code representing the logic applied to the Source to achieve the Target (e.g., "Unit Conversion", "Hardcoding", "Mapping Logic").
- **Coordinates** — A composite object containing the location details:
  - **Storage** — The container holding the data (`Database`/`Filesystem`/`API`).
  - **Structure** — The internal organization of that container (`Tabular`/`Tree`).
- **Source** — The Data Point representing the origin (RWD).
- **Target** — The Data Point representing the destination (SDTM).
- **Index/Linkers** — Keys or paths used to deterministically locate the record within the structure (e.g., Primary Keys, Row Numbers).



## Coordinates Metadata

#### Storage Coordinates

**Database:**
- `URI` — The connection string (e.g., `jdbc:postgresql://host:port/db`).
- `Database` — The specific database name context.
- `Schema` — The schema name (e.g., `public`, `dbo`, `clinical_data`).

**Filesystem:**
- `URI` — The full file path or object storage URI (e.g., `file://server/share/data.csv` or `s3://bucket/key`).

**API:**
- `URI` — The full endpoint URL including query parameters (e.g., `https://api.hospital.org/fhir/Patient/123`).

#### Structural Coordinates

**Tabular Data:**
- `RowIndex` — The specific row number or Primary Key value identifying the record.
- `ColumnName` — The header name or variable name of the specific cell.

**Tree:**
- `Path` — The navigation string used to traverse the hierarchy (e.g., XPath for XML, JSONPath for JSON).

**Files:**
- `URI` — The identifier of the specific file if the lineage points to the file as a whole object.



## Lineage trail metadata

### Array of Source–Target Pairs

The core of the RWD-Lineage file is a collection (array) of `<MapID>` elements. Each element contains exactly one Source Coordinate and one Target Coordinate, establishing a direct link between the raw real-world data and the standardized clinical data.



## Examples

### Example 1 — Tabular data in a database

```xml
<!-- UUID v5 generated from namespace + "jdbc...ehr_prod...vitals...10055...sys_bp" -->
<MapID uuid="a3bb189e-8bf9-5888-996e-1d54230623a1">
    <Transformation type="Direct Map">None</Transformation>
    <!-- Source: Hospital SQL DB -->
    <Source>
        <Coordinate storage="Database" structure="Tabular">
            <URI>jdbc:postgresql://hospital-db:5432/ehr</URI>
            <Database>ehr_prod</Database>
            <Schema>cardiology</Schema>
            <Table>vitals</Table>
            <RowKey column="visit_id">10055</RowKey>
            <ColumnName>sys_bp</ColumnName>
        </Coordinate>
    </Source>
    <!-- Target: SDTM VS Domain -->
    <Target>
        <Coordinate storage="Filesystem" structure="Tabular">
            <URI>./sdtm/vs.xpt</URI>
            <RowIndex>42</RowIndex>
            <ColumnName>VSORRES</ColumnName>
        </Coordinate>
    </Target>
</MapID>
```

### Example 2 — Tabular data in filesystem

```xml
<!-- UUID v5 generated from namespace + Source Coordinate Hash -->
<MapID uuid="c4d0290f-9cf0-5111-807f-2e65341734b2">
    <Transformation type="Unit Conversion">lb to kg</Transformation>
    <!-- Source: CSV Lab Report -->
    <Source>
        <Coordinate storage="Filesystem" structure="Tabular">
            <URI>file://server/raw_data/labs_2023.csv</URI>
            <RowIndex>501</RowIndex>
            <ColumnName>RESULT_VAL</ColumnName>
        </Coordinate>
    </Source>
    <!-- Target: SDTM LB Domain -->
    <Target>
        <Coordinate storage="Filesystem" structure="Tabular">
            <URI>./sdtm/lb.xpt</URI>
            <RowIndex>15</RowIndex>
            <ColumnName>LBORRES</ColumnName>
        </Coordinate>
    </Target>
</MapID>
```

### Example 3 — FHIR data via API

```xml
<MapID uuid="e5e13010-0dg1-5222-9180-3f76452845c3">
    <Transformation type="Extraction">JSON Path Extraction</Transformation>
    <!-- Source: FHIR API Endpoint -->
    <Source>
        <Coordinate storage="API" structure="Tree">
            <URI>https://api.hospital.org/fhir/R4/MedicationRequest/med-abc-123</URI>
            <Path syntax="JSONPath">$.medicationCodeableConcept.coding[0].code</Path>
        </Coordinate>
    </Source>
    <!-- Target: SDTM CM Domain -->
    <Target>
        <Coordinate storage="Filesystem" structure="Tabular">
            <URI>./sdtm/cm.xpt</URI>
            <RowIndex>8</RowIndex>
            <ColumnName>CMDECOD</ColumnName>
        </Coordinate>
    </Target>
</MapID>
```

### Example 4 — XML data in filesystem

```xml
<MapID uuid="f6f24121-1eh2-5333-0291-4087563956d4">
    <Transformation type="Date Format">ISO8601 to SAS Date</Transformation>
    <!-- Source: HL7 CDA XML File -->
    <Source>
        <Coordinate storage="Filesystem" structure="Tree">
            <URI>file://server/records/patient_001.xml</URI>
            <Path syntax="XPath">/ClinicalDocument/recordTarget/patientRole/patient/birthTime/@value</Path>
        </Coordinate>
    </Source>
    <!-- Target: SDTM DM Domain -->
    <Target>
        <Coordinate storage="Filesystem" structure="Tabular">
            <URI>./sdtm/dm.xpt</URI>
            <RowIndex>1</RowIndex>
            <ColumnName>BRTHDTC</ColumnName>
        </Coordinate>
    </Target>
</MapID>
```



## Reference to RWD-Lineage File in Define-XML

```xml
<define xmlns="http://www.cdisc.org/ns/def/v2.1"
        xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">

    <!-- Standard Define-XML content -->

    <rwdl:lineage>
        <rwdl:ref leafID="LF.RWDLINEAGE">rwd-lineage-traceability.xml</rwdl:ref>
    </rwdl:lineage>

</define>
```



## Glossary and Abbreviations

| Term | Definition |
|------|-----------|
| API | Application Programming Interface |
| CDISC | Clinical Data Interchange Standards Consortium |
| FHIR | Fast Healthcare Interoperability Resources |
| JSONPath | A query language for selecting nodes in a JSON document |
| RWD | Real-World Data |
| RWE | Real-World Evidence |
| SDTM | Study Data Tabulation Model |
| Transformation | The logic or algorithmic rule applied to source data to produce the target value |
| URI | Uniform Resource Identifier |
| UUID | Universally Unique Identifier |
| XPath | XML Path Language |
