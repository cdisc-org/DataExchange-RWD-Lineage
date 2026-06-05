# RWD-Lineage Data Standard Specification — DRAFT

## Introduction

RWD Lineage is a machine-readable CDISC data exchange standard for lineage metadata supplied along with RWD-derived SDTM. It provides the data reliability required by FDA to use RWE as primary evidence.

## Document Structure

An RWD Lineage document has a single root element, `rwdl:lineage`, with exactly two kinds of top-level child:

- **`rwdl:sourceMetadata`** — the *source metadata layer*. A single OPTIONAL element describing the source systems the lineage draws from: their names, the data models or standards they conform to, and the controlled terminologies in which their coded values are encoded. This layer carries *assertions* about the sources.
- **`rwdl:lineageTrail`** — the *lineage trail*. A single element containing an array of `rwdl:MapID` elements, each a Source–Target pair recording that a value at one physical coordinate became a value at another. This layer carries *forensic facts* about data movement.

The root element `rwdl:lineage` is the document as a whole; `rwdl:lineageTrail` is the one part of it that holds the trail. The two top-level layers are each a named element, so the parallel between them is structural, not merely conventional.

```xml
<rwdl:lineage xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">

    <rwdl:sourceMetadata>      <!-- source metadata layer: assertions about the sources -->
        <rwdl:source> ... </rwdl:source>
    </rwdl:sourceMetadata>

    <rwdl:lineageTrail>        <!-- lineage trail: an array of Source -> Target pairs -->
        <rwdl:MapID> ... </rwdl:MapID>
        <rwdl:MapID> ... </rwdl:MapID>
    </rwdl:lineageTrail>

</rwdl:lineage>
```

**The two layers are parallel and independent.** The lineage trail does not reference the source metadata layer, and the source metadata layer does not depend on the trail. Removing `rwdl:sourceMetadata` does not invalidate the lineage — the bytes still flowed from source coordinate to target coordinate. This separation is deliberate: it keeps the trail a record of *what physically happened* and confines *interpretive claims about what the data means* (for example, the controlled terminology a source column is encoded in) to the source metadata layer. A reviewer can always distinguish what the lineage observed from what it asserted about its sources.

The remainder of this specification describes the two layers in turn — first the **Lineage Trail** (the `rwdl:MapID` array and the Coordinate model that addresses values within sources), then the **Source Metadata** layer — followed by the **Controlled Terminology** that governs the enumerated attributes used by both, worked **Examples**, and the mechanism for attaching an RWD Lineage document to **Define-XML**.

RWD Lineage is an XML-formatted extension to Define-XML, implemented as a Namespace Extension. The `rwdl:lineage` document may be embedded directly within Define-XML or supplied as a separate referenced file; see "Attaching RWD Lineage to Define-XML" below.

## Lineage Trail

The lineage trail is carried in a single `rwdl:lineageTrail` element containing a collection (array) of `rwdl:MapID` elements. Each `rwdl:MapID` contains exactly one Source Coordinate and one Target Coordinate, establishing a direct link between a raw real-world data value and the standardized clinical data value derived from it. The trail is forensic: it records where a value came from, where it went, and — by reference — the transformation applied, without making semantic claims about what the value means.

### MapID Attributes

The following table defines the attributes for a single `rwdl:MapID` element (a Source–Target pair).

| Order | Attribute / Element | XML Node Type | XML Data Type | Usage | Description |
|-------|---------------------|---------------|---------------|-------|-------------|
| 1 | `uuid` | XML Attribute | string (UUIDv5) | Required | A deterministic UUID generated from a hash of the Source+Target coordinates. Ensures ID constancy across regenerations. |
| 2 | `MethodDefOID` | XML Attribute | string | Optional | An OID reference to a Define-XML `MethodDef` element describing the transformation logic applied from Source to Target. Omitted for direct (1:1) maps with no transformation. RWD Lineage reuses the existing Define-XML `MethodDef` mechanism rather than defining a transformation taxonomy of its own. |
| 3 | `rwdl:Source` | Child Element | Coordinate Object | Required | The Data Point representing the origin (RWD). |
| 4 | `rwdl:Target` | Child Element | Coordinate Object | Required | The Data Point representing the destination (SDTM). |

A **Data Point** is a specific value at a specific, uniquely identifiable location. The `rwdl:Source` and `rwdl:Target` are both Data Points, each expressed as a Coordinate Object that locates the value within its source or target system. The transformation between them, when one applies, is referenced via `MethodDefOID` rather than described inline.

### Coordinate Model

A Coordinate Object locates a single value within a source or target system. Both the `rwdl:Source` and `rwdl:Target` of a `rwdl:MapID` are expressed as Coordinates. A Coordinate combines a *storage* type (the kind of container) with a *structure* type (how a value is addressed within it), plus the addressing fields appropriate to each.

#### Coordinate Attributes and Elements

The following table defines the attributes and child elements available within a `<rwdl:Coordinate>` element. Usage depends on the storage and structure types selected.

| Order | Name | XML Node Type | XML Data Type | Usage | Description |
|-------|------|---------------|---------------|-------|-------------|
| 1 | `storage` | XML Attribute | string (Enum) | Required | The container type. Values from the **RWDL Storage Type** codelist (see Controlled Terminology): `DATABASE`, `FILESYSTEM`, `API`, `MESSAGE`. |
| 2 | `structure` | XML Attribute | string (Enum) | Required | The addressing mechanism for locating a value within the source. Values from the **RWDL Structure Type** codelist (see Controlled Terminology): `TABULAR`, `PATH`, `OBJECT`. |
| 3 | `Format` | XML Attribute | string (Enum) | Optional | The serialization format of the source. Values from the **RWDL Data Format** codelist (see Controlled Terminology), e.g., `JSON`, `XML`, `CSV`, `PARQUET`, `XLSX`, `PDF`. |
| 4 | `rwdl:URI` | Child Element | string | Conditional | The full connection string, file path, or API endpoint. |
| 5 | `rwdl:Database` | Child Element | string | Conditional | The specific database name (Required for `storage="DATABASE"`). |
| 6 | `rwdl:Schema` | Child Element | string | Conditional | The schema name (Required for `storage="DATABASE"`). |
| 7 | `rwdl:Table` | Child Element | string | Conditional | The table name (Required for `storage="DATABASE"`). |
| 8 | `rwdl:RowIndex` | Child Element | integer | Conditional | The row number (One of `RowIndex` or `RowKey` required for `structure="TABULAR"`). |
| 9 | `rwdl:RowKey` | Child Element | string | Conditional | The Primary Key field name (One of `RowIndex` or `RowKey` required for `structure="TABULAR"`). |
| 10 | `rwdl:RowKeyValue` | Child Element | string/integer | Conditional | The Primary Key value (Required if `RowKey` is used). |
| 11 | `rwdl:ColumnName` | Child Element | string | Conditional | The header/variable name (Optional for `structure="TABULAR"` — omitted for key-value-shaped data with row identifiers but no distinct column dimension). |
| 12 | `rwdl:Path` | Child Element | string | Conditional | The navigation string used to address a value (e.g., XPath, JSONPath, FHIRPath, Cypher, SPARQL) (Required for `structure="PATH"`). The syntax is declared on the `rwdl:Path` element via the `syntax` attribute. |

*(Note: In the Coordinate representation, `storage`, `structure`, and `Format` are XML attributes on the `<rwdl:Coordinate>` element itself, while others are nested XML child elements prefixed with `rwdl:`).*

#### Storage and Structure Types

The `structure` and `storage` attributes are governed by controlled terminology. See the Controlled Terminology section for the full codelists, definitions, and submission values.

##### Structure Types

The `structure` attribute classifies how a value within a source is addressed, not the data model of the source itself.

- **TABULAR** — Value addressed by row identifier (index or key) and column name (e.g., SQL tables, SAS XPT, CSV files, key-value stores).
- **PATH** — Value addressed by a path or query expression that locates the value within a structured source (e.g., JSON, XML, FHIR resources, property graphs, RDF triplestores). The syntax of the path expression is declared on the `rwdl:Path` element.
- **OBJECT** — Value addressed as a whole object with no sub-addressing; the URI is the location (e.g., PDF reports, medical images, binary blobs).

**Scope:**
- *In Scope (Current):* Deterministic, static structures where a value's location can be explicitly defined by an index, key, path expression, or URI alone.
- *Out of Scope:* Non-deterministic or unstructured data requiring semantic interpretation (e.g., free-text clinical notes requiring NLP, video/audio streams).

##### Storage Types

- **DATABASE** — Structured data engines accessed via connection protocol (e.g., SQL, NoSQL).
- **FILESYSTEM** — Flat files on local disk, network share, or object storage (e.g., POSIX, S3, Azure Blob, GCS).
- **API** — Data accessed via request/response web service endpoint (e.g., REST, SOAP, GraphQL, FHIR API).
- **MESSAGE** — Data delivered as discrete units over a message transport or event stream (e.g., HL7 v2 over MLLP, FHIR Messaging, Kafka, Kinesis, AMQP, MQTT, webhooks).

**Scope:**
- *In Scope (Current):* Standard digital repositories accessible via common, widely supported protocols (JDBC/ODBC, POSIX/S3, HTTP/REST, message broker protocols).
- *Out of Scope:* Physical media (paper records requiring OCR), proprietary legacy systems without standard connectivity, and Distributed Ledger Technology (blockchain).

#### Coordinate Field Reference

##### Storage Field Reference

**Database (`storage="DATABASE"`):**
- `rwdl:URI` — The connection string (e.g., `jdbc:postgresql://host:port/db`).
- `rwdl:Database` — The specific database name context.
- `rwdl:Schema` — The schema name (e.g., `public`, `dbo`, `clinical_data`).
- `rwdl:Table` — The table name.

**Filesystem (`storage="FILESYSTEM"`):**
- `rwdl:URI` — The full file path or object storage URI (e.g., `file://server/share/data.csv` or `s3://bucket/key`).

**API (`storage="API"`):**
- `rwdl:URI` — The full endpoint URL including query parameters (e.g., `https://api.hospital.org/fhir/Patient/123`).

**Message (`storage="MESSAGE"`):**
- `rwdl:URI` — The transport endpoint or topic identifier (e.g., `kafka://broker:9092/topic-adt`, `mllp://hospital-feed:2575`).

##### Structure Field Reference

**Tabular (`structure="TABULAR"`):**
- `rwdl:RowIndex` — The specific row number, OR
- `rwdl:RowKey` + `rwdl:RowKeyValue` — The primary key field name and its value.
- `rwdl:ColumnName` — The header or variable name (omitted for key-value-shaped data).

**Path-Addressable (`structure="PATH"`):**
- `rwdl:Path` — The navigation or query expression used to address the value, with `syntax` attribute declaring the expression language (e.g., XPath for XML, JSONPath for JSON, FHIRPath for FHIR resources, Cypher for property graphs, SPARQL for RDF triplestores).

**Object (`structure="OBJECT"`):**
- `rwdl:URI` — The identifier of the object as a whole. No sub-addressing.


## Source Metadata

The source metadata layer is the second of the two top-level layers introduced in Document Structure. It is carried in a single OPTIONAL `rwdl:sourceMetadata` element and is populated once per source system rather than per data point. It holds *assertions* about the sources — their data models and the controlled terminologies their values are encoded in — kept separate from the forensic lineage trail.

Source data characterization is authoritatively documented in the sponsor's Study Data Reviewer's Guide (SDRG) and, for RWE submissions, in the RWD Reliability Assessment. The `rwdl:sourceMetadata` element provides a structured, machine-readable pointer to the same information for reviewers and tooling working directly within the RWD Lineage file, but is not intended to replace the narrative documents that authoritatively characterize source data.

### Structure

`rwdl:sourceMetadata` contains one or more `rwdl:source` child elements. Each `rwdl:source` describes one source system (the physical or logical origin). It MAY contain a nested `rwdl:standard` child element describing the data model or standard to which the source conforms, and one or more `rwdl:externalCodeList` child elements declaring the controlled terminologies in which the source's coded values are encoded.

#### `rwdl:source` Attributes

| Attribute | XML Data Type | Usage | Description |
|-----------|---------------|-------|-------------|
| `OID` | string | Optional | A unique identifier for the source system, used if any MapID or Coordinate needs to reference this source explicitly. By convention, OIDs identify distinct source systems (e.g., `SRC.EHR.1`, `SRC.EDW.1`, `SRC.CLAIMS.1`, `SRC.EDC.1`). |
| `name` | string | Optional | The physical or logical name of the origin system (e.g., `University Hospital Epic Interconnect`, `Memorial Healthcare Enterprise Data Warehouse`, `Optum Claims Repository`, `Site 042 Medidata Rave EDC`). |
| `description` | string | Optional | Free-text description of the source. Use when the source is bespoke or when additional context is helpful beyond the structured attributes. |

#### `rwdl:standard` Child Element

The `rwdl:standard` element is OPTIONAL and is used to declare that the parent `rwdl:source` conforms to a named data model or interoperability standard. A sponsor populates this element when the source system implements a recognizable standard; sources without a named standard omit the element and rely on the parent `description` attribute.

| Attribute | XML Data Type | Usage | Description |
|-----------|---------------|-------|-------------|
| `name` | string | Optional | The specific data model or standard utilized by the source (e.g., `FHIR`, `OMOP-CDM`, `PCORNET-CDM`, `SENTINEL-CDM`, `CDA`). Free-text; not constrained by an RWDL codelist in V1. |
| `version` | string | Optional | The version of the standard (e.g., `5.4`, `R4`, `1.0`). |
| `status` | string | Optional | Publication status of the standard. Allowed values mirror Define-XML `def:Standard/@Status`: `Draft`, `Provisional`, `Final`. |

A sponsor populates whichever attributes meaningfully apply to their source. The `rwdl:standard` element is appropriate for sources that conform to a named, versioned standard. The `description` attribute on `rwdl:source` is appropriate for bespoke sources, or as a supplement to the structured attributes.

#### `rwdl:externalCodeList` Child Element

The `rwdl:externalCodeList` element declares the controlled terminology (e.g., ICD-10-CM, LOINC, RxNorm, NDC, SNOMED CT) in which coded values in the source are encoded. It is OPTIONAL and a single `rwdl:source` MAY carry multiple `rwdl:externalCodeList` elements — one per coded element in the source.

`rwdl:externalCodeList` is modeled on the Define-XML `ExternalCodeList` element, which declares external controlled terminology dictionaries on the target side. The `Dictionary`, `Version`, and `href` attributes are carried over directly, so Define-XML readers recognize the pattern. RWD Lineage adds an `appliesTo` attribute, identifying which element or column within the source the declaration governs, and an optional `rwdl:Scope` child element for declarations that apply only to part of a source (for example, a column whose encoding changed over time).

**Why source terminology is an assertion, not an observable fact.** As Document Structure notes, interpretive claims about what the data means are kept out of the lineage trail. Source terminology is exactly such a claim. A row identifier or column name is an observable property of the source; the claim that a given column is encoded in "ICD-10-CM 2024" is different in kind, because in many EHR and claims sources the encoding vocabulary is not explicit in the data and the claim is an inference made by a person or process applying judgment to sample data. Recording it on the Coordinate or MapID would make interpretive content indistinguishable from forensic fact to a downstream reviewer. Keeping it in the source metadata layer, declared on the source, keeps that boundary clean.

This source-side layer gives the controlled-terminology documentation called for in FDA's 2024 EHR/medical claims guidance §VI.A (accuracy of mappings across coding systems, semantics of local codes to a target terminology, and coding-practice/version changes across the study period) a structured, machine-readable home. It complements, and does not replace, the narrative characterization in the SDRG / Data Characterization Report and the coding-system declarations in the Protocol.

##### Attributes

| Attribute | XML Data Type | Usage | Description |
|-----------|---------------|-------|-------------|
| `Dictionary` | string | Required | The name of the external controlled terminology (e.g., `ICD-10-CM`, `LOINC`, `RxNorm`, `NDC`, `SNOMED CT`). Mirrors Define-XML `ExternalCodeList/@Dictionary`. Free-text and not governed by a CDISC Controlled Terminology codelist; published terminology lists such as the NCI Metathesaurus may be consulted as a reference for dictionary names, but values are not constrained to a CDISC-controlled set. |
| `Version` | string | Conditional | The version or release of the dictionary (e.g., `2024`, `2024-09-03`). Required where the dictionary is versioned; the literal `continuous` MAY be used for dictionaries that are continuously updated without discrete versions (e.g., NDC). Mirrors Define-XML `ExternalCodeList/@Version`. |
| `href` | string (URI) | Optional | A resolvable reference to the dictionary or its publisher. Mirrors Define-XML `ExternalCodeList/@href`. |
| `appliesTo` | string | Optional | Identifies the element, field, or column within the source the declaration applies to. The expression follows the source's own conventions (e.g., FHIRPath for FHIR sources such as `Condition.code`; dot notation for CDM tables such as `DIAGNOSIS.DX`), or uses the Coordinate addressing the specification already defines for finer-grained scoping. When omitted, the declaration applies to the source as a whole. |

##### Child Elements

The `rwdl:externalCodeList` element MAY carry one or more `rwdl:Scope` child elements. A declaration that applies to the whole of the element named in `appliesTo` carries no `rwdl:Scope`.

| Element | Cardinality | Description |
|---------|-------------|-------------|
| `rwdl:Scope` | 0..n | Qualifies when or to which subset of records the assertion applies. Carries an optional `condition` attribute (a predicate in the source's own expression conventions, e.g., `encounter_date >= 2015-10-01`) and an optional `description` attribute (free-text explanation). When no `rwdl:Scope` is present, the assertion applies unconditionally ("Always"). Multiple `rwdl:Scope` elements partition a column whose encoding changed over time or across subsets (e.g., an ICD-9-CM → ICD-10-CM transition). |

### Source Metadata Examples

A sponsor with a single OMOP CDM source:

```xml
<rwdl:sourceMetadata xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">
    <rwdl:source OID="SRC.EDW.1"
                 name="Hospital X Enterprise Data Warehouse"
                 description="Hospital X OMOP warehouse, refreshed quarterly">
        <rwdl:standard name="OMOP-CDM" version="5.4" status="Final"/>
    </rwdl:source>
</rwdl:sourceMetadata>
```

A sponsor with multiple source systems (an EHR exposed via FHIR and a research data warehouse on OMOP CDM):

```xml
<rwdl:sourceMetadata xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">
    <rwdl:source OID="SRC.EHR.1"
                 name="University Hospital Epic Interconnect"
                 description="EHR FHIR API at api.hospital.org">
        <rwdl:standard name="FHIR" version="R4" status="Final"/>
    </rwdl:source>
    <rwdl:source OID="SRC.EDW.1"
                 name="Memorial Healthcare Enterprise Data Warehouse"
                 description="Research data warehouse">
        <rwdl:standard name="OMOP-CDM" version="5.4" status="Final"/>
    </rwdl:source>
</rwdl:sourceMetadata>
```

A sponsor combining claims data and EDC data alongside an EHR feed:

```xml
<rwdl:sourceMetadata xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">
    <rwdl:source OID="SRC.EHR.1"
                 name="University Hospital Epic Interconnect"
                 description="EHR FHIR API at api.hospital.org">
        <rwdl:standard name="FHIR" version="R4" status="Final"/>
    </rwdl:source>
    <rwdl:source OID="SRC.CLAIMS.1"
                 name="Optum Claims Repository"
                 description="Adjudicated medical and pharmacy claims feed">
        <rwdl:standard name="PCORNET-CDM" version="6.1" status="Final"/>
    </rwdl:source>
    <rwdl:source OID="SRC.EDC.1"
                 name="Site 042 Medidata Rave EDC"
                 description="Clinical trial EDC export, Q2 2025">
        <rwdl:standard name="CDISC ODM" version="1.3.2" status="Final"/>
    </rwdl:source>
</rwdl:sourceMetadata>
```

A sponsor declaring the controlled terminologies in which source values are encoded. The EHR source carries an ICD-10-CM declaration scoped across the ICD-9/ICD-10 transition date (two `rwdl:Scope` elements partition the column) plus an RxNorm declaration; the claims source declares ICD-10-CM and NDC for its respective columns:

```xml
<rwdl:sourceMetadata xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">
    <rwdl:source OID="SRC.EHR.1"
                 name="University Hospital Epic Interconnect"
                 description="EHR FHIR API at api.hospital.org">
        <rwdl:standard name="FHIR" version="R4" status="Final"/>
        <!-- ICD-10-CM coding, date-scoped across the ICD-9 to ICD-10 transition -->
        <rwdl:externalCodeList Dictionary="ICD-10-CM" Version="2024"
                               href="https://www.cms.gov/medicare/icd-10/2024-icd-10-cm"
                               appliesTo="Condition.code">
            <rwdl:Scope condition="encounter_date &gt;= 2015-10-01"
                        description="Codes on or after 2015-10-01 are ICD-10-CM; transition date approximate"/>
            <rwdl:Scope condition="encounter_date &lt; 2015-10-01"
                        description="Codes prior to 2015-10-01 are ICD-9-CM"/>
        </rwdl:externalCodeList>
        <rwdl:externalCodeList Dictionary="RxNorm" Version="2024-09-03"
                               href="https://www.nlm.nih.gov/research/umls/rxnorm/"
                               appliesTo="MedicationRequest.medicationCodeableConcept"/>
    </rwdl:source>
    <rwdl:source OID="SRC.CLAIMS.1"
                 name="Optum Claims Repository"
                 description="Adjudicated medical and pharmacy claims feed">
        <rwdl:standard name="PCORNET-CDM" version="6.1" status="Final"/>
        <rwdl:externalCodeList Dictionary="ICD-10-CM" Version="2024"
                               appliesTo="DIAGNOSIS.DX"/>
        <rwdl:externalCodeList Dictionary="NDC" Version="continuous"
                               appliesTo="DISPENSING.NDC"/>
    </rwdl:source>
</rwdl:sourceMetadata>
```

A sponsor with a bespoke source that does not conform to a named standard (the `rwdl:standard` child element is simply omitted):

```xml
<rwdl:sourceMetadata xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">
    <rwdl:source OID="SRC.EDC.1"
                 name="Site 17 CSV Export"
                 description="CSV exports from clinical trial site EDC system, Q2 2025; bespoke schema documented in SDRG Section 3.2"/>
</rwdl:sourceMetadata>
```

### Notes

- The `name` attribute on `rwdl:source` identifies the physical or logical origin system; the `name` attribute on the nested `rwdl:standard` element identifies the data model the system implements. Two distinct source systems implementing the same standard (e.g., two hospitals both exposing FHIR R4) are represented as two separate `rwdl:source` elements.
- The `name` attribute on `rwdl:standard` is free-text in V1. If RWDL submissions accumulate enough usage of common standardized names (OMOP-CDM, FHIR, etc.) to warrant a controlled vocabulary, a Data Model codelist may be submitted to CDISC CT in a future RWDL revision, informed by actual usage patterns.
- OID conventions: recommended forms use a source-class prefix and a system index, e.g., `SRC.EHR.1`, `SRC.EHR.2`, `SRC.EDW.1`, `SRC.CLAIMS.1`, `SRC.EDC.1`. This keeps OIDs stable when a source system's underlying standard or version changes, and lets multiple sources implementing the same standard be distinguished.
- Coordinates within `rwdl:MapID` elements do not declare source data model on a per-data-point basis. The data model of a source is implicit from the source URI and the submission-level `rwdl:sourceMetadata` declaration, with authoritative characterization in the SDRG and RWD Reliability Assessment.
- Sponsors who want to bind a specific `rwdl:MapID` or Coordinate to a specific declared source MAY do so via implementer-defined conventions referencing the `rwdl:source/@OID`, but no formal mechanism is specified in V1.
- `rwdl:externalCodeList` declarations live inside the `rwdl:source` they describe, alongside `rwdl:standard`. The lineage trail does not reference them and does not depend on them: a Coordinate addresses a physical location; the vocabulary in which the value at that location is encoded is a separate, interpretive claim recorded on the source. This separation is deliberate and preserves the forensic integrity of the trail.
- The `Dictionary` attribute is free-text and is deliberately not governed by a CDISC Controlled Terminology codelist. Published terminology lists such as the NCI Metathesaurus may be consulted as a reference for naming source dictionaries, but RWDL does not constrain `Dictionary` to a CDISC-controlled set: the universe of source vocabularies a sponsor may encounter is open-ended, and forcing it through a controlled list would create friction without improving comparability.


## Controlled Terminology

This section defines the controlled terminology (codelists) governing enumerated attributes in RWD Lineage. Codelists are submitted to the CDISC Controlled Terminology team under the `RWDL` prefix and are intended to be published through CDISC and NCI Enterprise Vocabulary Services (NCI-EVS) on the standard CDISC release cadence.

The codelists in this section are finalized for V1. Source data model conformance (e.g., FHIR R4, OMOP CDM 5.4, PCORnet CDM) and source controlled terminology (e.g., ICD-10-CM, LOINC, RxNorm) are not governed by RWDL codelists; both are declared at the document level via the `rwdl:sourceMetadata` element (on `rwdl:standard` and `rwdl:externalCodeList` respectively). See the Source Metadata section.

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
| `TABULAR` | Tabular | Value addressed by row identifier and column name. | `rwdl:RowIndex` or (`rwdl:RowKey` + `rwdl:RowKeyValue`); plus `rwdl:ColumnName` (optional for key-value-shaped data). |
| `PATH` | Path-Addressable | Value addressed by a path or query expression that locates the value within a structured source. | `rwdl:Path` element with `syntax` attribute. |
| `OBJECT` | Object | Value is addressed as a whole object with no sub-addressing; the URI is the location. | `rwdl:URI` only. No `rwdl:RowIndex`, `rwdl:ColumnName`, or `rwdl:Path`. |

**Coverage notes:**
- Tree-structured sources (JSON, XML, FHIR resources) are addressed as `structure="PATH"` with `syntax="JSONPATH"`, `"XPATH"`, or `"FHIRPATH"`.
- Graph sources (property graphs, RDF triplestores) are addressed as `structure="PATH"` with `syntax="CYPHER"`, `"GREMLIN"`, or `"SPARQL"`.
- Key-value stores (Redis, DynamoDB) are addressed as `structure="TABULAR"` with `rwdl:RowKey`/`rwdl:RowKeyValue` populated and `rwdl:ColumnName` omitted.
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
| `TTL` | Turtle | Terse RDF Triple Language per W3C Turtle specification; text serialization of RDF graph data. |
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
| `X12` | ASC X12 EDI | ASC X12 Electronic Data Interchange transaction sets used in healthcare claims and eligibility (e.g., 837 claims, 835 remittance, 270/271 eligibility). |
| `TXT` | Plain Text | Unstructured or semi-structured plain text. |

### RWDL Path Syntax

Governs the `syntax` attribute on the `rwdl:Path` element. Required when `structure="PATH"`.

**Extensibility:** Extensible. Sponsors populating a value not present in the published codelist flag the value as an extension using the Define-XML convention (`def:ExtendedValue="Yes"`).

| Submission Value | Preferred Term | Definition |
|------------------|----------------|------------|
| `XPATH` | XPath | XML Path Language expression per W3C XPath specification. |
| `JSONPATH` | JSONPath | JSON path expression per RFC 9535. |
| `JSONPOINTER` | JSON Pointer | JSON Pointer syntax per RFC 6901, used to address values within JSON documents (distinct from JSONPath). |
| `FHIRPATH` | FHIRPath | FHIRPath expression per HL7 FHIRPath specification. |
| `JMESPATH` | JMESPath | JMESPath query expression. |
| `GRAPHQL` | GraphQL | GraphQL query expression used to extract values from a GraphQL API response. |
| `SQL` | Structured Query Language | SQL `SELECT` statement used to address values that are not naturally captured by the decomposed `rwdl:Database`/`rwdl:Schema`/`rwdl:Table`/`rwdl:RowKey`/`rwdl:ColumnName` fields, e.g., values produced by joins, computed expressions, views, or materialized views. |
| `CYPHER` | Cypher | Cypher query language for property graphs (Neo4j and openCypher-compatible databases, ISO/IEC 39075 GQL). |
| `GREMLIN` | Gremlin | Apache TinkerPop Gremlin graph traversal language for property graphs (JanusGraph, Amazon Neptune, Azure Cosmos DB Gremlin API). |
| `SPARQL` | SPARQL | SPARQL query language for RDF triplestores per W3C SPARQL specification. |
| `HL7V2` | HL7 v2 Segment Notation | Segment-field-component-subcomponent addressing used to locate values within HL7 v2 pipe-delimited messages (e.g., `PID-5.1.1`). |
| `DICOMTAG` | DICOM Tag Reference | DICOM data element tag in `(group,element)` notation used to locate metadata within DICOM files (e.g., `(0010,0010)` for Patient Name). |
| `REGEX` | Regular Expression | Regular expression with capture group locating the target value within a text source. |

**Note:** Several values appear in both this codelist and the Data Format codelist (`HL7V2`, `DICOM`/`DICOMTAG`). They are governing different attributes and are not redundant: the Data Format value declares what kind of bytes the source contains; the Path Syntax value declares what addressing language locates a value within those bytes. They commonly co-occur for the same data point.


## Examples

### Example 1 — A complete document (source metadata + lineage trail)

This example shows both top-level layers of an `rwdl:lineage` document together. The `rwdl:sourceMetadata` block declares one source — a hospital EHR exposed via FHIR — and records that its condition codes are encoded in ICD-10-CM. The `rwdl:MapID` that follows is the forensic trail: it addresses a value in that same source and maps it to an SDTM target. The trail does not reference the source metadata; the two layers stand side by side.

```xml
<rwdl:lineage xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">

    <!-- LAYER 1: Source metadata - assertions about the source -->
    <rwdl:sourceMetadata>
        <rwdl:source OID="SRC.EHR.1"
                     name="University Hospital Epic Interconnect"
                     description="EHR FHIR API at api.hospital.org">
            <rwdl:standard name="FHIR" version="R4" status="Final"/>
            <rwdl:externalCodeList Dictionary="ICD-10-CM" Version="2024"
                                   href="https://www.cms.gov/medicare/icd-10/2024-icd-10-cm"
                                   appliesTo="Condition.code"/>
        </rwdl:source>
    </rwdl:sourceMetadata>

    <!-- LAYER 2: Lineage trail - a forensic Source -> Target pair -->
    <rwdl:lineageTrail>
        <rwdl:MapID uuid="b7c0290f-1cf0-5222-907f-3e75341845c3">
            <!-- Source: a condition code in the EHR FHIR API -->
            <rwdl:Source>
                <rwdl:Coordinate storage="API" structure="PATH">
                    <rwdl:URI>https://api.hospital.org/fhir/R4/Condition/cond-456</rwdl:URI>
                    <rwdl:Path syntax="JSONPATH">$.code.coding[0].code</rwdl:Path>
                </rwdl:Coordinate>
            </rwdl:Source>
            <!-- Target: SDTM MH Domain -->
            <rwdl:Target>
                <rwdl:Coordinate storage="FILESYSTEM" structure="TABULAR">
                    <rwdl:URI>./sdtm/mh.xpt</rwdl:URI>
                    <rwdl:RowIndex>12</rwdl:RowIndex>
                    <rwdl:ColumnName>MHDECOD</rwdl:ColumnName>
                </rwdl:Coordinate>
            </rwdl:Target>
        </rwdl:MapID>
    </rwdl:lineageTrail>

</rwdl:lineage>
```

The examples that follow focus on individual storage and structure patterns. Each is shown wrapped in its `rwdl:lineage` root and `rwdl:lineageTrail` element; in a real document, all `rwdl:MapID` elements share one `rwdl:lineageTrail` and a single `rwdl:sourceMetadata` block sits alongside it, as above.

### Example 2 — Tabular data in a database

```xml
<rwdl:lineage xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">

    <rwdl:lineageTrail>
        <!-- UUID v5 generated from namespace + "jdbc...ehr_prod...vitals...10055...sys_bp" -->
        <!-- Direct (1:1) map: no transformation, so no MethodDefOID -->
        <rwdl:MapID uuid="a3bb189e-8bf9-5888-996e-1d54230623a1">
            <!-- Source: Hospital SQL DB -->
            <rwdl:Source>
                <rwdl:Coordinate storage="DATABASE" structure="TABULAR">
                    <rwdl:URI>jdbc:postgresql://hospital-db:5432/ehr</rwdl:URI>
                    <rwdl:Database>ehr_prod</rwdl:Database>
                    <rwdl:Schema>cardiology</rwdl:Schema>
                    <rwdl:Table>vitals</rwdl:Table>
                    <rwdl:RowKey>visit_id</rwdl:RowKey>
                    <rwdl:RowKeyValue>10055</rwdl:RowKeyValue>
                    <rwdl:ColumnName>sys_bp</rwdl:ColumnName>
                </rwdl:Coordinate>
            </rwdl:Source>
            <!-- Target: SDTM VS Domain -->
            <rwdl:Target>
                <rwdl:Coordinate storage="FILESYSTEM" structure="TABULAR">
                    <rwdl:URI>./sdtm/vs.xpt</rwdl:URI>
                    <rwdl:RowIndex>42</rwdl:RowIndex>
                    <rwdl:ColumnName>VSORRES</rwdl:ColumnName>
                </rwdl:Coordinate>
            </rwdl:Target>
        </rwdl:MapID>
    </rwdl:lineageTrail>

</rwdl:lineage>
```

### Example 3 — Tabular data in filesystem

This example shows a transformation (pounds to kilograms). The transformation is declared once as a standard Define-XML `MethodDef` in the Define-XML document metadata block, and is referenced from the lineage `rwdl:MapID` via the `MethodDefOID` attribute.

**Define-XML Metadata Definition (inside `define.xml`):**
```xml
<MethodDef OID="MT.LB2KG" Name="Pounds to kilograms" Type="Computation"
           xmlns="http://www.cdisc.org/ns/def/v2.1">
    <Description>
        <TranslatedText xml:lang="en">Multiply source value (lb) by 0.45359237 to yield kg.</TranslatedText>
    </Description>
</MethodDef>
```

**RWD Lineage Traceability Document:**
```xml
<rwdl:lineage xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">

    <rwdl:lineageTrail>
        <!-- UUID v5 generated from namespace + Source Coordinate Hash -->
        <rwdl:MapID uuid="c4d0290f-9cf0-5111-807f-2e65341734b2" MethodDefOID="MT.LB2KG">
            <!-- Source: CSV Lab Report -->
            <rwdl:Source>
                <rwdl:Coordinate storage="FILESYSTEM" structure="TABULAR">
                    <rwdl:URI>file://server/raw_data/labs_2023.csv</rwdl:URI>
                    <rwdl:RowIndex>501</rwdl:RowIndex>
                    <rwdl:ColumnName>RESULT_VAL</rwdl:ColumnName>
                </rwdl:Coordinate>
            </rwdl:Source>
            <!-- Target: SDTM LB Domain -->
            <rwdl:Target>
                <rwdl:Coordinate storage="FILESYSTEM" structure="TABULAR">
                    <rwdl:URI>./sdtm/lb.xpt</rwdl:URI>
                    <rwdl:RowIndex>15</rwdl:RowIndex>
                    <rwdl:ColumnName>LBORRES</rwdl:ColumnName>
                </rwdl:Coordinate>
            </rwdl:Target>
        </rwdl:MapID>
    </rwdl:lineageTrail>

</rwdl:lineage>
```

### Example 4 — FHIR data via API

This example illustrates how `rwdl:sourceMetadata` is declared once at the document root using the nested `rwdl:source`/`rwdl:standard` architecture, and how the per-coordinate `rwdl:MapID` then carries only the addressing information. The FHIR R4 conformance of the source is captured on the nested `rwdl:standard` element; the parent `rwdl:source` names the origin system.

**Define-XML Metadata Definition (inside `define.xml`):**
```xml
<MethodDef OID="MT.FHIR.MEDCODE" Name="FHIR medication code extraction" Type="Computation"
           xmlns="http://www.cdisc.org/ns/def/v2.1">
    <Description>
        <TranslatedText xml:lang="en">Extract the primary medication code from the FHIR MedicationRequest resource via JSONPath.</TranslatedText>
    </Description>
</MethodDef>
```

**RWD Lineage Traceability Document:**
```xml
<rwdl:lineage xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">

    <!-- Document-level source declaration: declared once for the file -->
    <rwdl:sourceMetadata>
        <rwdl:source OID="SRC.EHR.1"
                     name="University Hospital Epic Interconnect"
                     description="Hospital FHIR API at api.hospital.org">
            <rwdl:standard name="FHIR" version="R4" status="Final"/>
        </rwdl:source>
    </rwdl:sourceMetadata>

    <rwdl:lineageTrail>
        <rwdl:MapID uuid="e5e13010-0dg1-5222-9180-3f76452845c3" MethodDefOID="MT.FHIR.MEDCODE">
            <!-- Source: FHIR API Endpoint -->
            <rwdl:Source>
                <rwdl:Coordinate storage="API" structure="PATH">
                    <rwdl:URI>https://api.hospital.org/fhir/R4/MedicationRequest/med-abc-123</rwdl:URI>
                    <rwdl:Path syntax="JSONPATH">$.medicationCodeableConcept.coding[0].code</rwdl:Path>
                </rwdl:Coordinate>
            </rwdl:Source>
            <!-- Target: SDTM CM Domain -->
            <rwdl:Target>
                <rwdl:Coordinate storage="FILESYSTEM" structure="TABULAR">
                    <rwdl:URI>./sdtm/cm.xpt</rwdl:URI>
                    <rwdl:RowIndex>8</rwdl:RowIndex>
                    <rwdl:ColumnName>CMDECOD</rwdl:ColumnName>
                </rwdl:Coordinate>
            </rwdl:Target>
        </rwdl:MapID>

        <!-- Additional MapID elements pulling from the same FHIR source follow;
             each carries only addressing information, not source metadata -->

    </rwdl:lineageTrail>

</rwdl:lineage>
```

### Example 5 — XML data in filesystem

This example sources from an HL7 CDA document and demonstrates `rwdl:sourceMetadata` declaring a CDA-conformant source alongside a date-format transformation.

**Define-XML Metadata Definition (inside `define.xml`):**
```xml
<MethodDef OID="MT.ISO2SASDATE" Name="ISO 8601 to SAS date" Type="Computation"
           xmlns="http://www.cdisc.org/ns/def/v2.1">
    <Description>
        <TranslatedText xml:lang="en">Convert ISO 8601 birthTime value to SAS date representation.</TranslatedText>
    </Description>
</MethodDef>
```

**RWD Lineage Traceability Document:**
```xml
<rwdl:lineage xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0">

    <!-- Document-level source declaration -->
    <rwdl:sourceMetadata>
        <rwdl:source OID="SRC.CDA.1"
                     name="Regional HIE CDA Repository"
                     description="Continuity of Care Documents retrieved from the regional health information exchange">
            <rwdl:standard name="CDA" version="R2" status="Final"/>
        </rwdl:source>
    </rwdl:sourceMetadata>

    <rwdl:lineageTrail>
        <rwdl:MapID uuid="f6f24121-1eh2-5333-0291-4087563956d4" MethodDefOID="MT.ISO2SASDATE">
            <!-- Source: HL7 CDA XML File -->
            <rwdl:Source>
                <rwdl:Coordinate storage="FILESYSTEM" structure="PATH">
                    <rwdl:URI>file://server/records/patient_001.xml</rwdl:URI>
                    <rwdl:Path syntax="XPATH">/ClinicalDocument/recordTarget/patientRole/patient/birthTime/@value</rwdl:Path>
                </rwdl:Coordinate>
            </rwdl:Source>
            <!-- Target: SDTM DM Domain -->
            <rwdl:Target>
                <rwdl:Coordinate storage="FILESYSTEM" structure="TABULAR">
                    <rwdl:URI>./sdtm/dm.xpt</rwdl:URI>
                    <rwdl:RowIndex>1</rwdl:RowIndex>
                    <rwdl:ColumnName>BRTHDTC</rwdl:ColumnName>
                </rwdl:Coordinate>
            </rwdl:Target>
        </rwdl:MapID>
    </rwdl:lineageTrail>

</rwdl:lineage>
```


## Attaching RWD Lineage to Define-XML

RWD Lineage may be supplied in either of two mutually exclusive ways:

- **Embedded** — the `rwdl:lineage` root element (containing `rwdl:sourceMetadata` and the `rwdl:lineageTrail` array of `rwdl:MapID` elements) appears directly inside the Define-XML document.
- **Referenced** — the `rwdl:lineage` content lives in a separate XML file, and the Define-XML document points at it. The external file uses `rwdl:lineage` as its root element.

For the referenced case, the pointer reuses the standard Define-XML external-document mechanism: a `<def:leaf>` declares the physical file (carrying the filename in `xlink:href`), and `<rwdl:lineageRef>` references it by `leafID` under the standard metadata block.

```xml
<ODM xmlns="http://www.cdisc.org/ns/odm/v1.3"
     xmlns:def="http://www.cdisc.org/ns/def/v2.1"
     xmlns:rwdl="http://www.cdisc.org/ns/rwdl/v1.0"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     ODMVersion="1.3.2"
     FileType="Transactional"
     FileOID="Define-XML_RWD-Lineage_Example"
     CreationDateTime="2026-06-05T13:00:00">

    <Study OID="STUDY.EXAMPLE">
        <GlobalVariables>
            <StudyName>Example RWD-Lineage Study</StudyName>
            <StudyDescription>Example study integrating RWD Lineage</StudyDescription>
            <ProtocolName>Example Protocol</ProtocolName>
        </GlobalVariables>
        <MetaDataVersion OID="MDV.EXAMPLE" Name="Metadata Version" Description="Metadata Version Description">

            <!-- Standard Define-XML metadata content here -->

            <!-- def:leaf declares the physical lineage file, per Define-XML convention -->
            <def:leaf ID="LF.RWDLINEAGE" xlink:href="rwd-lineage-traceability.xml">
                <def:title>RWD Lineage Traceability</def:title>
            </def:leaf>

            <!-- rwdl:lineageRef points at the external file by leafID -->
            <rwdl:lineageRef leafID="LF.RWDLINEAGE"/>

        </MetaDataVersion>
    </Study>
</ODM>
```


## Glossary and Abbreviations

| Term | Definition |
|------|-----------|
| API | Application Programming Interface |
| CDISC | Clinical Data Interchange Standards Consortium |
| ExternalCodeList | A Define-XML element declaring an external controlled terminology dictionary. RWD Lineage adapts it as `rwdl:externalCodeList` to declare the source-side vocabulary in which coded values are encoded. |
| FHIR | Fast Healthcare Interoperability Resources |
| JSONPath | A query language for selecting nodes in a JSON document |
| RWD | Real-World Data |
| RWE | Real-World Evidence |
| MethodDef | A Define-XML element defining a computation or derivation. RWD Lineage references it via `MethodDefOID` to describe the transformation applied from source to target value. |
| rwdl:lineageTrail | The `rwdl:lineageTrail` element: one of the two top-level layers of an RWD Lineage document, containing the array of `rwdl:MapID` Source–Target pairs that form the forensic trail. |
| SDTM | Study Data Tabulation Model |
| URI | Uniform Resource Identifier |
| UUID | Universally Unique Identifier |
| XPath | XML Path Language |
