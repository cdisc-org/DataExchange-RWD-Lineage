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
| 1 | `storage` | string (Enum) | Required | The container type. Values from the **RWDL Storage Type** codelist (see Controlled Terminology): `DATABASE`, `FILESYSTEM`, `API`, `MESSAGE`. |
| 2 | `structure` | string (Enum) | Required | The addressing mechanism for locating a value within the source. Values from the **RWDL Structure Type** codelist (see Controlled Terminology): `TABULAR`, `PATH`, `OBJECT`. |
| 3 | `URI` | string | Conditional | The full connection string, file path, or API endpoint. |
| 4 | `Database` | string | Conditional | The specific database name (Required for `storage="Database"`). |
| 5 | `Schema` | string | Conditional | The schema name (Required for `storage="Database"`). |
| 6 | `Table` | string | Conditional | The table name (Required for `storage="Database"`). |
| 7 | `RowIndex` | integer | Conditional | The row number (One of `RowIndex` or `RowKey` required for `structure="TABULAR"`). |
| 8 | `RowKey` | string/integer | Conditional | The Primary Key field (One of `RowIndex` or `RowKey` required for `structure="TABULAR"`). |
| 9 | `RowKeyValue` | string/integer | Conditional | The Primary Key value (Required if `RowKey` is used). |
| 10 | `ColumnName` | string | Conditional | The header/variable name (Optional for `structure="TABULAR"` — omitted for key-value-shaped data with row identifiers but no distinct column dimension). |
| 11 | `Path` | string | Conditional | The navigation string used to address a value (e.g., XPath, JSONPath, FHIRPath, Cypher, SPARQL) (Required for `structure="PATH"`). The syntax is declared on the `Path` element via the `syntax` attribute. |
| 12 | `Format` | string (Enum) | Optional | The serialization format of the source. Values from the **RWDL Data Format** codelist (see Controlled Terminology), e.g., `JSON`, `XML`, `CSV`, `PARQUET`, `XLSX`, `PDF`. |

### Coordinates

The `structure` and `storage` attributes are governed by controlled terminology. See the Controlled Terminology section for the full codelists, definitions, and submission values.

#### Structural Formats

The `structure` attribute classifies how a value within a source is addressed, not the data model of the source itself.

- **TABULAR** — Value addressed by row identifier (index or key) and column name (e.g., SQL tables, SAS XPT, CSV files, key-value stores).
- **PATH** — Value addressed by a path or query expression that locates the value within a structured source (e.g., JSON, XML, FHIR resources, property graphs, RDF triplestores). The syntax of the path expression is declared on the `Path` element.
- **OBJECT** — Value addressed as a whole object with no sub-addressing; the URI is the location (e.g., PDF reports, medical images, binary blobs).

**Scope:**
- *In Scope (Current):* Deterministic, static structures where a value's location can be explicitly defined by an index, key, path expression, or URI alone.
- *Out of Scope:* Non-deterministic or unstructured data requiring semantic interpretation (e.g., free-text clinical notes requiring NLP, video/audio streams).

#### Storage Formats

- **DATABASE** — Structured data engines accessed via connection protocol (e.g., SQL, NoSQL).
- **FILESYSTEM** — Flat files on local disk, network share, or object storage (e.g., POSIX, S3, Azure Blob, GCS).
- **API** — Data accessed via request/response web service endpoint (e.g., REST, SOAP, GraphQL, FHIR API).
- **MESSAGE** — Data delivered as discrete units over a message transport or event stream (e.g., HL7 v2 over MLLP, FHIR Messaging, Kafka, Kinesis, AMQP, MQTT, webhooks).

**Scope:**
- *In Scope (Current):* Standard digital repositories accessible via common, widely supported protocols (JDBC/ODBC, POSIX/S3, HTTP/REST, message broker protocols).
- *Out of Scope:* Physical media (paper records requiring OCR), proprietary legacy systems without standard connectivity, and Distributed Ledger Technology (blockchain).

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

**Database (`storage="DATABASE"`):**
- `URI` — The connection string (e.g., `jdbc:postgresql://host:port/db`).
- `Database` — The specific database name context.
- `Schema` — The schema name (e.g., `public`, `dbo`, `clinical_data`).
- `Table` — The table name.

**Filesystem (`storage="FILESYSTEM"`):**
- `URI` — The full file path or object storage URI (e.g., `file://server/share/data.csv` or `s3://bucket/key`).

**API (`storage="API"`):**
- `URI` — The full endpoint URL including query parameters (e.g., `https://api.hospital.org/fhir/Patient/123`).

**Message (`storage="MESSAGE"`):**
- `URI` — The transport endpoint or topic identifier (e.g., `kafka://broker:9092/topic-adt`, `mllp://hospital-feed:2575`).

#### Structural Coordinates

**Tabular (`structure="TABULAR"`):**
- `RowIndex` — The specific row number, OR
- `RowKey` + `RowKeyValue` — The primary key field name and its value.
- `ColumnName` — The header or variable name (omitted for key-value-shaped data).

**Path-Addressable (`structure="PATH"`):**
- `Path` — The navigation or query expression used to address the value, with `syntax` attribute declaring the expression language (e.g., XPath for XML, JSONPath for JSON, FHIRPath for FHIR resources, Cypher for property graphs, SPARQL for RDF triplestores).

**Object (`structure="OBJECT"`):**
- `URI` — The identifier of the object as a whole. No sub-addressing.



## Controlled Terminology

This section defines the controlled terminology (codelists) governing enumerated attributes in RWD Lineage. Codelists are submitted to the CDISC Controlled Terminology team under the `RWDL` prefix and are intended to be published through CDISC and NCI Enterprise Vocabulary Services (NCI-EVS) on the standard CDISC release cadence.

The codelists in this section are finalized for V1. Additional codelists (Path Syntax, Data Model) are under discussion and will be added in a future revision once decisions are settled.

### RWDL Storage Type

Governs the `storage` attribute on the Coordinate element.

**Extensibility:** Non-extensible. The four values comprehensively cover the architectural categories of data access (query-connection, file-path, request/response, message transport).

| Submission Value | Preferred Term | Definition |
|------------------|----------------|------------|
| `DATABASE` | Database | Structured data engine accessed via connection protocol (SQL, NoSQL). |
| `FILESYSTEM` | Filesystem | Flat files on local disk, network share, or object storage (POSIX, S3, Azure Blob, GCS). |
| `API` | Application Programming Interface | Data accessed via request/response web service endpoint (REST, SOAP, GraphQL, FHIR API). |
| `MESSAGE` | Messages | Data delivered as discrete units over a message transport or event stream (HL7 v2, FHIR Messaging, Kafka, Kinesis, AMQP, MQTT, webhooks). |

### RWDL Structure Type

Governs the `structure` attribute on the Coordinate element. Each value corresponds to a distinct addressing mechanism rather than to the data model of the source.

**Extensibility:** Non-extensible. The three values correspond directly to the addressing mechanisms the specification itself defines (row-and-column, path expression, whole-object).

| Submission Value | Preferred Term | Definition | Required Addressing |
|------------------|----------------|------------|---------------------|
| `TABULAR` | Tabular | Value addressed by row identifier and column name. | `RowIndex` or (`RowKey` + `RowKeyValue`); plus `ColumnName` (optional for key-value-shaped data). |
| `PATH` | Path-Addressable | Value addressed by a path or query expression that locates the value within a structured source. | `Path` element with `syntax` attribute. |
| `OBJECT` | Object | Value is addressed as a whole object with no sub-addressing; the URI is the location. | `URI` only. No `RowIndex`, `ColumnName`, or `Path`. |

**Coverage notes:**
- Tree-structured sources (JSON, XML, FHIR resources) are addressed as `structure="PATH"` with `syntax="JSONPath"`, `"XPath"`, or `"FHIRPath"`.
- Graph sources (property graphs, RDF triplestores) are addressed as `structure="PATH"` with `syntax="Cypher"` or `"SPARQL"`.
- Key-value stores (Redis, DynamoDB) are addressed as `structure="TABULAR"` with `RowKey`/`RowKeyValue` populated and `ColumnName` omitted.
- Whole-object sources (PDF reports, medical images, opaque blobs) are addressed as `structure="OBJECT"`.

### RWDL Data Format

Governs the `Format` attribute on the Coordinate element. Scoped strictly to serialization layer: how bytes are arranged.

**Extensibility:** Extensible. Sponsors populating a value not present in the published codelist flag the value as an extension using the Define-XML convention (`def:ExtendedValue="Yes"` on the relevant CodeList element) and are encouraged to contribute commonly-used extensions back to CDISC for consideration in future codelist versions.

| Submission Value | Preferred Term | Definition |
|------------------|----------------|------------|
| `CSV` | Comma-Separated Values | Delimited text, comma-separated. |
| `TSV` | Tab-Separated Values | Delimited text, tab-separated. |
| `JSON` | JavaScript Object Notation | Tree-structured text format per RFC 8259. |
| `XML` | Extensible Markup Language | Tree-structured markup format per W3C XML 1.0. |
| `NDJSON` | Newline-Delimited JSON | One JSON object per line. |
| `YAML` | YAML | Human-readable structured data serialization format. |
| `PARQUET` | Apache Parquet | Columnar binary format common in data science and analytics pipelines. |
| `AVRO` | Apache Avro | Row-based binary format with embedded schema. |
| `ORC` | Apache ORC | Columnar binary format common in Hadoop and Spark ecosystems. |
| `FEATHER` | Apache Arrow Feather | Arrow-based columnar format for fast dataframe interchange between R and Python. |
| `ARROW` | Apache Arrow IPC | Apache Arrow inter-process communication streaming format. |
| `HDF5` | HDF5 | Hierarchical Data Format v5; used for large numerical datasets, scientific arrays, and clinical waveforms. |
| `NPY` | NumPy Array | NumPy single-array binary format. |
| `PKL` | Python Pickle | Python Pickle format. |
| `XPT` | SAS Transport File | SAS XPORT v5 or v8 format. |
| `SAS7BDAT` | SAS Dataset | Native SAS dataset format. |
| `RDS` | R Data Serialization | R single-object serialization format. |
| `RDA` | R Data | R workspace serialization format (multiple objects). |
| `SPSS-SAV` | SPSS Dataset | IBM SPSS Statistics dataset (.sav). |
| `STATA-DTA` | Stata Dataset | Stata dataset (.dta). |
| `XLSX` | Excel Workbook | Microsoft Excel Office Open XML workbook. |
| `XLS` | Excel Legacy Workbook | Microsoft Excel legacy binary workbook (pre-2007). |
| `DOCX` | Word Document | Microsoft Word Office Open XML document. |
| `RTF` | Rich Text Format | Microsoft Rich Text Format document. |
| `PDF` | Portable Document Format | ISO 32000 document format. |
| `DICOM` | DICOM | ISO 12052 medical imaging format. |
| `JPEG` | JPEG | JPEG image format. |
| `HL7V2` | HL7 v2 Message | Pipe-delimited HL7 v2 message syntax. |
| `TXT` | Plain Text | Unstructured or semi-structured plain text. |



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
        <Coordinate storage="DATABASE" structure="TABULAR">
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
        <Coordinate storage="FILESYSTEM" structure="TABULAR">
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
        <Coordinate storage="FILESYSTEM" structure="TABULAR">
            <URI>file://server/raw_data/labs_2023.csv</URI>
            <RowIndex>501</RowIndex>
            <ColumnName>RESULT_VAL</ColumnName>
        </Coordinate>
    </Source>
    <!-- Target: SDTM LB Domain -->
    <Target>
        <Coordinate storage="FILESYSTEM" structure="TABULAR">
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
        <Coordinate storage="API" structure="PATH">
            <URI>https://api.hospital.org/fhir/R4/MedicationRequest/med-abc-123</URI>
            <Path syntax="JSONPath">$.medicationCodeableConcept.coding[0].code</Path>
        </Coordinate>
    </Source>
    <!-- Target: SDTM CM Domain -->
    <Target>
        <Coordinate storage="FILESYSTEM" structure="TABULAR">
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
        <Coordinate storage="FILESYSTEM" structure="PATH">
            <URI>file://server/records/patient_001.xml</URI>
            <Path syntax="XPath">/ClinicalDocument/recordTarget/patientRole/patient/birthTime/@value</Path>
        </Coordinate>
    </Source>
    <!-- Target: SDTM DM Domain -->
    <Target>
        <Coordinate storage="FILESYSTEM" structure="TABULAR">
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
