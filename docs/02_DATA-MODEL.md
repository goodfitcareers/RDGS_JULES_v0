# M0: Data Model (PostgreSQL) - Dataset Distiller

This document outlines the proposed database schema for the Dataset Distiller project, targeting PostgreSQL 15. The schema is designed to support the M1 and M2 milestones, focusing on metadata storage, job tracking, content management, and PII annotation.

## 1. Schema Philosophy

*   **Normalization:** Strive for a reasonable level of normalization to reduce redundancy and improve data integrity, but not at the expense of query performance for common use cases.
*   **Extensibility:** Design tables with future needs in mind (e.g., `jsonb` fields for flexible metadata).
*   **Clear Naming:** Use consistent and descriptive names for tables and columns.
*   **Timestamps:** Include `created_at` and `updated_at` timestamps for most tables to track changes.
*   **Foreign Keys:** Enforce relationships using foreign keys to maintain referential integrity.
*   **Indexing:** Define indexes on frequently queried columns, especially foreign keys and columns used in WHERE clauses.

## 2. Enumerated Types (Enums)

These enums will be used in various tables to ensure consistency for status fields.

```sql
CREATE TYPE job_status AS ENUM (
    'PENDING',
    'RUNNING',
    'COMPLETED',
    'FAILED',
    'CANCELLED'
);

CREATE TYPE source_node_status AS ENUM (
    'PENDING',
    'PROCESSING',
    'COMPLETED',
    'ERROR_PARSING',
    'ERROR_CHUNKING',
    'ERROR_PII_DETECTION',
    'SKIPPED'
);

CREATE TYPE content_item_status AS ENUM (
    'RAW',          -- Freshly chunked
    'PII_DETECTED', -- PII detection complete
    'REDACTED',     -- PII redaction complete (if applied)
    'VALIDATED',    -- Passed validation rules
    'EXPORTED'      -- Included in a JSONL export
);

CREATE TYPE pii_type AS ENUM (
    -- Common Presidio types, extend as needed
    'PERSON',
    'PHONE_NUMBER',
    'EMAIL_ADDRESS',
    'LOCATION',
    'DATE_TIME',
    'US_SSN',
    'CREDIT_CARD',
    'ORGANIZATION',
    -- Add more specific types if necessary
    'CUSTOM_REGEX_1' -- Example for custom patterns
);

CREATE TYPE data_source_type AS ENUM (
    'LOCAL_ZIP',
    'LOCAL_FOLDER',
    'NOTION',
    'GOOGLE_DRIVE', -- M2
    'CONFLUENCE'    -- Future
);
```

## 3. Core Tables

### `data_sources` (M2 primarily, basic for M1)

Stores information about configured data sources. For M1, this might be minimal if sources are passed ad-hoc via CLI.

```sql
CREATE TABLE data_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    type data_source_type NOT NULL,
    config JSONB NOT NULL, -- Connection details, API keys (encrypted or references to secrets manager)
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- Index on type for filtering
CREATE INDEX idx_data_sources_type ON data_sources(type);
```

### `pipeline_runs` (Formerly Jobs)

Tracks each execution of the Dataset Distiller pipeline.

```sql
CREATE TABLE pipeline_runs (
    id SERIAL PRIMARY KEY,
    data_source_id INTEGER REFERENCES data_sources(id) NULL, -- Can be NULL if source is ad-hoc (e.g. local path via CLI for M1)
    source_identifier TEXT NOT NULL, -- e.g., path to local ZIP, Notion workspace ID, GDrive folder ID
    pipeline_config_name VARCHAR(255), -- Name of the configuration used (e.g., "default_pii_redaction")
    status job_status NOT NULL DEFAULT 'PENDING',
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    report JSONB, -- Summary statistics, errors, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- Index on status and start_time for monitoring
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX idx_pipeline_runs_start_time ON pipeline_runs(start_time DESC);
```

### `source_nodes`

Represents an individual file or item within an archive/data source (e.g., a DOCX file in a ZIP, a Notion page).

```sql
CREATE TABLE source_nodes (
    id SERIAL PRIMARY KEY,
    pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    source_uri VARCHAR(2048) NOT NULL, -- Path within archive, URL to Notion page, etc.
    internal_path VARCHAR(2048) NULL, -- Path where the raw file is stored locally by the system during processing
    file_type_detected VARCHAR(50), -- e.g., 'pdf', 'docx', 'txt'
    file_type_provided VARCHAR(50), -- Extension from filename
    content_hash VARCHAR(64),       -- SHA256 hash of the raw file content for deduplication/change detection
    metadata JSONB,                  -- Original metadata from source (e.g., Notion page properties, file system dates)
    status source_node_status NOT NULL DEFAULT 'PENDING',
    processing_log TEXT,             -- Log of processing steps and errors for this node
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (pipeline_run_id, source_uri) -- Ensure a file is processed once per run
);
-- Indexes for querying by status, type, and hash
CREATE INDEX idx_source_nodes_status ON source_nodes(status);
CREATE INDEX idx_source_nodes_pipeline_run_id ON source_nodes(pipeline_run_id);
CREATE INDEX idx_source_nodes_file_type_detected ON source_nodes(file_type_detected);
CREATE INDEX idx_source_nodes_content_hash ON source_nodes(content_hash);
```

### `raw_content_store`

Stores the extracted raw text from source nodes. Could be a pointer to a file if content is very large.
For M1, we might store directly in DB and evaluate performance.

```sql
CREATE TABLE raw_content_store (
    id SERIAL PRIMARY KEY,
    source_node_id INTEGER NOT NULL REFERENCES source_nodes(id) ON DELETE CASCADE UNIQUE,
    extracted_text TEXT,             -- Full extracted text
    -- storage_pointer VARCHAR(2048), -- Alternative: path to file on disk if text is too large for DB
    extraction_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    parser_module VARCHAR(100)       -- Which parser was used (e.g., 'unstructured_pdf', 'custom_txt')
);
CREATE INDEX idx_raw_content_store_source_node_id ON raw_content_store(source_node_id);
```

### `content_items` (Chunks)

Represents a processed chunk of text derived from a `source_node`. This is the level at which PII detection and transformation occur.

```sql
CREATE TABLE content_items (
    id BIGSERIAL PRIMARY KEY, -- Use BIGSERIAL if expecting a very large number of chunks
    source_node_id INTEGER NOT NULL REFERENCES source_nodes(id) ON DELETE CASCADE,
    raw_content_id INTEGER NOT NULL REFERENCES raw_content_store(id) ON DELETE CASCADE,
    chunk_sequence_number INTEGER NOT NULL, -- Order of this chunk within its source node
    text_content TEXT NOT NULL,             -- The actual text of the chunk
    text_content_redacted TEXT,             -- Text content after PII redaction (if applied)
    chunking_strategy VARCHAR(100),         -- e.g., 'fixed_size_1000', 'sentence_boundary'
    metadata JSONB,                         -- Metadata specific to this chunk (e.g., page number, section headers)
    status content_item_status NOT NULL DEFAULT 'RAW',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_node_id, chunk_sequence_number) -- Ensure chunk order is unique per source
);
-- Indexes for querying by status and source node
CREATE INDEX idx_content_items_status ON content_items(status);
CREATE INDEX idx_content_items_source_node_id ON content_items(source_node_id);
CREATE INDEX idx_content_items_raw_content_id ON content_items(raw_content_id);
```

### `pii_annotations`

Stores information about detected PII within `content_items`.

```sql
CREATE TABLE pii_annotations (
    id BIGSERIAL PRIMARY KEY,
    content_item_id BIGINT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    pii_type pii_type NOT NULL,
    start_offset INTEGER NOT NULL,        -- Start character offset within the original (non-redacted) content_item text
    end_offset INTEGER NOT NULL,          -- End character offset
    detected_value TEXT NOT NULL,         -- The actual detected PII string
    confidence_score FLOAT,               -- Confidence score from the PII detection tool (e.g., Presidio)
    detection_module VARCHAR(100),        -- e.g., 'PresidioAnalyzerWrapper'
    is_redacted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- Indexes for querying by content_item_id and pii_type
CREATE INDEX idx_pii_annotations_content_item_id ON pii_annotations(content_item_id);
CREATE INDEX idx_pii_annotations_pii_type ON pii_annotations(pii_type);
```

### `exported_golden_rows` (Linking Table)

Tracks which `content_items` were included in which export (JSONL file).
An export can be considered part of a `pipeline_run` or a separate concept if re-exporting is possible.
For simplicity here, linking to `pipeline_run`.

```sql
CREATE TABLE exported_golden_rows (
    id BIGSERIAL PRIMARY KEY,
    pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    content_item_id BIGINT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    export_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    exported_filename VARCHAR(1024), -- Name of the JSONL file this row went into
    UNIQUE (pipeline_run_id, content_item_id, exported_filename) -- Avoid duplicates in the same export file
);
CREATE INDEX idx_exported_golden_rows_pipeline_run_id ON exported_golden_rows(pipeline_run_id);
CREATE INDEX idx_exported_golden_rows_content_item_id ON exported_golden_rows(content_item_id);
```

## 4. Relationships and Cardinality

*   `pipeline_runs` to `source_nodes`: One-to-Many (one pipeline run processes many source files)
*   `source_nodes` to `raw_content_store`: One-to-One (each source file has one primary extracted text body)
*   `source_nodes` (or `raw_content_store`) to `content_items`: One-to-Many (one source file's text is broken into many chunks)
*   `content_items` to `pii_annotations`: One-to-Many (one chunk can have multiple PII instances)
*   `pipeline_runs` to `exported_golden_rows`: One-to-Many
*   `content_items` to `exported_golden_rows`: One-to-Many (a content item could potentially be part of multiple exports if re-exported with different settings, though the table structure above assumes one export context per golden row for simplicity)

## 5. Future Considerations / Extensions

*   **Users & Permissions (M2+):** `users`, `roles`, `permissions` tables for UI access control.
*   **Pipeline Configurations Table:** A dedicated table to store named pipeline configurations (e.g., chunking strategy, PII rules) instead of just `pipeline_config_name` in `pipeline_runs`.
    ```sql
    -- Example:
    -- CREATE TABLE pipeline_configurations (
    --     id SERIAL PRIMARY KEY,
    --     name VARCHAR(255) NOT NULL UNIQUE,
    --     config_details JSONB NOT NULL, -- Chunking settings, PII settings, etc.
    --     is_default BOOLEAN DEFAULT FALSE,
    --     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    --     updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    -- );
    ```
*   **Vector Embeddings Table:** If semantic search or similarity is needed.
    ```sql
    -- Example:
    -- CREATE TABLE content_item_embeddings (
    --     content_item_id BIGINT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE PRIMARY KEY,
    --     embedding VECTOR(1536), -- Assuming OpenAI ada-002, adjust dimensions as needed
    --     model_name VARCHAR(100),
    --     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    -- );
    -- CREATE INDEX idx_content_item_embeddings_embedding ON content_item_embeddings USING ivfflat (embedding vector_cosine_ops); -- Or HNSW for pgvector
    ```
*   **Tenant Isolation:** Add `tenant_id` to all relevant tables if multi-tenancy becomes a requirement.

## 6. Canonical SQL DDL (PostgreSQL 15)

This section concatenates all `CREATE TYPE` and `CREATE TABLE` statements for easy execution.

```sql
-- Enums
CREATE TYPE job_status AS ENUM (
    'PENDING',
    'RUNNING',
    'COMPLETED',
    'FAILED',
    'CANCELLED'
);

CREATE TYPE source_node_status AS ENUM (
    'PENDING',
    'PROCESSING',
    'COMPLETED',
    'ERROR_PARSING',
    'ERROR_CHUNKING',
    'ERROR_PII_DETECTION',
    'SKIPPED'
);

CREATE TYPE content_item_status AS ENUM (
    'RAW',
    'PII_DETECTED',
    'REDACTED',
    'VALIDATED',
    'EXPORTED'
);

CREATE TYPE pii_type AS ENUM (
    'PERSON',
    'PHONE_NUMBER',
    'EMAIL_ADDRESS',
    'LOCATION',
    'DATE_TIME',
    'US_SSN',
    'CREDIT_CARD',
    'ORGANIZATION',
    'CUSTOM_REGEX_1'
);

CREATE TYPE data_source_type AS ENUM (
    'LOCAL_ZIP',
    'LOCAL_FOLDER',
    'NOTION',
    'GOOGLE_DRIVE',
    'CONFLUENCE'
);

-- Tables
CREATE TABLE data_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    type data_source_type NOT NULL,
    config JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_data_sources_type ON data_sources(type);

CREATE TABLE pipeline_runs (
    id SERIAL PRIMARY KEY,
    data_source_id INTEGER REFERENCES data_sources(id) NULL,
    source_identifier TEXT NOT NULL,
    pipeline_config_name VARCHAR(255),
    status job_status NOT NULL DEFAULT 'PENDING',
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    report JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX idx_pipeline_runs_start_time ON pipeline_runs(start_time DESC);

CREATE TABLE source_nodes (
    id SERIAL PRIMARY KEY,
    pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    source_uri VARCHAR(2048) NOT NULL,
    internal_path VARCHAR(2048) NULL,
    file_type_detected VARCHAR(50),
    file_type_provided VARCHAR(50),
    content_hash VARCHAR(64),
    metadata JSONB,
    status source_node_status NOT NULL DEFAULT 'PENDING',
    processing_log TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (pipeline_run_id, source_uri)
);
CREATE INDEX idx_source_nodes_status ON source_nodes(status);
CREATE INDEX idx_source_nodes_pipeline_run_id ON source_nodes(pipeline_run_id);
CREATE INDEX idx_source_nodes_file_type_detected ON source_nodes(file_type_detected);
CREATE INDEX idx_source_nodes_content_hash ON source_nodes(content_hash);

CREATE TABLE raw_content_store (
    id SERIAL PRIMARY KEY,
    source_node_id INTEGER NOT NULL REFERENCES source_nodes(id) ON DELETE CASCADE UNIQUE,
    extracted_text TEXT,
    extraction_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    parser_module VARCHAR(100)
);
CREATE INDEX idx_raw_content_store_source_node_id ON raw_content_store(source_node_id);

CREATE TABLE content_items (
    id BIGSERIAL PRIMARY KEY,
    source_node_id INTEGER NOT NULL REFERENCES source_nodes(id) ON DELETE CASCADE,
    raw_content_id INTEGER NOT NULL REFERENCES raw_content_store(id) ON DELETE CASCADE,
    chunk_sequence_number INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    text_content_redacted TEXT,
    chunking_strategy VARCHAR(100),
    metadata JSONB,
    status content_item_status NOT NULL DEFAULT 'RAW',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_node_id, chunk_sequence_number)
);
CREATE INDEX idx_content_items_status ON content_items(status);
CREATE INDEX idx_content_items_source_node_id ON content_items(source_node_id);
CREATE INDEX idx_content_items_raw_content_id ON content_items(raw_content_id);

CREATE TABLE pii_annotations (
    id BIGSERIAL PRIMARY KEY,
    content_item_id BIGINT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    pii_type pii_type NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    detected_value TEXT NOT NULL,
    confidence_score FLOAT,
    detection_module VARCHAR(100),
    is_redacted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_pii_annotations_content_item_id ON pii_annotations(content_item_id);
CREATE INDEX idx_pii_annotations_pii_type ON pii_annotations(pii_type);

CREATE TABLE exported_golden_rows (
    id BIGSERIAL PRIMARY KEY,
    pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    content_item_id BIGINT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    export_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    exported_filename VARCHAR(1024),
    UNIQUE (pipeline_run_id, content_item_id, exported_filename)
);
CREATE INDEX idx_exported_golden_rows_pipeline_run_id ON exported_golden_rows(pipeline_run_id);
CREATE INDEX idx_exported_golden_rows_content_item_id ON exported_golden_rows(content_item_id);

```

This data model should provide a solid foundation for the Dataset Distiller's backend. Adjustments can be made as development progresses and new requirements emerge.
