# M0: Functional Spec & UI - Dataset Distiller

## 1. Functional Specification

This section details the functional requirements for Dataset Distiller, broken down by Milestones (M1, M2).

### M1: Core Pipeline & CLI (MVP)

**1.1. Data Ingestion (CLI-driven)**

*   **FS-1.1.1:** The system MUST allow ingestion of local ZIP archives specified via a CLI argument.
    *   The ZIP archive may contain various file types (TXT, MD, PDF, DOCX, HTML).
    *   The system should iterate through all files within the ZIP.
*   **FS-1.1.2:** The system MUST allow ingestion of local file folders specified via a CLI argument.
    *   The folder may contain various file types.
    *   The system should recursively scan subfolders.
*   **FS-1.1.3:** The system MUST allow ingestion from a Notion workspace via API.
    *   Requires Notion API Key and Database/Page IDs provided via configuration (e.g., `.env` file or CLI args).
    *   The system should traverse specified Notion pages and their children.
*   **FS-1.1.4:** For each ingested source node (file/Notion page), basic metadata (filename, path, source type) MUST be recorded in the StateDB.

**1.2. Data Processing (Core Pipeline)**

*   **FS-1.2.1:** The system MUST detect the file type of each ingested file (e.g., PDF, DOCX, TXT, MD, HTML) using libraries like `python-magic` or `filetype.py` and fall back to extensions if needed.
*   **FS-1.2.2:** The system MUST use `unstructured.io` (or equivalent) to parse content from supported file types (PDF, DOCX, HTML, TXT, MD).
    *   Raw extracted text should be stored in StateDB or a temporary file system cache linked from StateDB.
    *   Parsing errors MUST be logged per source node in StateDB. The system should "fail-loud" for unparseable files (mark as error, potentially skip).
*   **FS-1.2.3:** The system MUST offer basic text chunking strategies:
    *   By fixed character size (e.g., 1000 characters) with configurable overlap.
    *   By a user-defined separator string.
    *   Chunked content items MUST be stored in StateDB, linked to their parent source node.
*   **FS-1.2.4:** The system MUST extract basic metadata from source nodes (e.g., filename, source URI, creation/modification dates if available from source). This metadata should be associated with content items.
*   **FS-1.2.5:** The system MUST integrate a PII detection tool (e.g., Presidio) to identify common PII types (configurable list, e.g., PERSON, EMAIL, PHONE, CREDIT_CARD, US_SSN) in content items.
    *   Detected PII instances (type, location, original value, confidence) MUST be stored in StateDB, linked to the content item.
    *   For M1, redaction is NOT performed; the system only detects and logs.
*   **FS-1.2.6:** The system MUST output processed data as JSONL files.
    *   Each line in the JSONL file represents a "golden row" (a processed content item).
    *   The JSONL structure should include:
        *   `id`: Unique ID for the content item.
        *   `source_node_id`: ID of the parent source node.
        *   `text_content`: The text of the content item.
        *   `metadata`: A JSON object containing extracted metadata (source, filename, chunk info, etc.).
        *   `pii_annotations`: A list of detected PII instances (type, start, end, value) for that content item.
            ```json
            // Example Golden Row (Illustrative)
            {"id": "ci_123", "source_node_id": "sn_abc", "text_content": "This is a sample text chunk with an email address test@example.com.", "metadata": {"source": "local/my_document.docx", "chunk_num": 1}, "pii_annotations": [{"type": "EMAIL_ADDRESS", "start": 37, "end": 53, "value": "test@example.com"}]}
            ```

**1.3. CLI Operations**

*   **FS-1.3.1:** The CLI MUST provide a command to initiate a new pipeline run:
    *   `distiller run --source-type <local_zip|local_folder|notion> --source-path <path_or_id> [--config <pipeline_config_name>] [--output-dir <path>]`
*   **FS-1.3.2:** The CLI MUST allow users to specify essential configuration parameters (e.g., chunk size, PII types to detect) either via a configuration file (e.g., TOML or YAML) or individual CLI arguments.
*   **FS-1.3.3:** The CLI MUST provide basic status updates during a pipeline run (e.g., files processed, errors encountered).
*   **FS-1.3.4:** The CLI MUST generate a summary report after a pipeline run (total files, successful, failed, PII detected counts) and save it to the output directory.

**1.4. Database & State Management**

*   **FS-1.4.1:** The system MUST use a PostgreSQL database (StateDB) to store all metadata, job status, content references, and PII annotations as defined in `02_DATA-MODEL.md`.
*   **FS-1.4.2:** Pipeline runs MUST be resumable to some extent (e.g., if a run fails processing file 50 of 100, it should be possible to restart and ideally skip already processed files, based on checksums or StateDB records). Idempotency is key.

**1.5. Code Quality & DevOps**

*   **FS-1.5.1:** Code MUST be formatted using Black and linted using Ruff.
*   **FS-1.5.2:** Type checking MUST be enforced using MyPy.
*   **FS-1.5.3:** Unit and integration tests MUST be written using Pytest. Target minimum 70% test coverage.
*   **FS-1.5.4:** Pre-commit hooks MUST be configured to run Black, Ruff, and MyPy.
*   **FS-1.5.5:** A basic CI/CD pipeline MUST be set up using GitHub Actions to run linters, type checkers, and tests on pushes and PRs.

### M2: Web UI & Enhanced Features

**2.1. Web UI (FastAPI + Simple Frontend)**

*   **FS-2.1.1:** The system MUST provide a web UI for managing data sources.
    *   Users can add, view, edit, and delete configured data sources (Notion, Google Drive connections).
    *   Sensitive information (API keys) should be handled securely (e.g., input only, stored encrypted or in a secrets manager, not displayed).
*   **FS-2.1.2:** The system MUST provide a web UI for managing pipeline configurations.
    *   Users can create, view, edit, and clone pipeline configurations (e.g., chunking strategy, PII detection/redaction settings).
*   **FS-2.1.3:** The system MUST allow users to initiate pipeline runs from the web UI, selecting a data source and a pipeline configuration.
*   **FS-2.1.4:** The web UI MUST display the status of ongoing and completed pipeline runs, including progress, logs, and error summaries.
*   **FS-2.1.5:** Users MUST be able to view and download generated JSONL datasets and reports from the web UI.
*   **FS-2.1.6:** The web UI MUST have user authentication (e.g., username/password, OAuth with a provider like GitHub/Google).

**2.2. Enhanced Data Processing**

*   **FS-2.2.1:** The system MUST support ingestion from Google Drive (reading files from specified folders).
*   **FS-2.2.2:** The system MUST provide PII redaction options (beyond just detection in M1).
    *   Replace PII with placeholders (e.g., `[EMAIL]`, `[PERSON]`).
    *   Replace PII with synthetic data (future, complex).
    *   Configurable per PII type.
*   **FS-2.2.3:** The system MAY explore more sophisticated chunking strategies (e.g., semantic chunking using LLM embeddings if feasible within performance constraints).
*   **FS-2.2.4:** The system MUST use Alembic for managing database schema migrations.

**2.3. Reporting & Analytics (Enhanced)**

*   **FS-2.3.1:** The web UI MUST provide more detailed reports and visualizations (e.g., distribution of file types, PII types found, processing times).

**2.4. Data Versioning (Basic)**

*   **FS-2.4.1:** The system MAY offer basic data versioning, allowing users to track changes to source data or pipeline configurations and associate them with specific output datasets. (Details to be refined).

## 2. UI/UX Mockups (Conceptual for M2)

As M1 is CLI-focused, these are very high-level concepts for the M2 Web UI.

**Page 1: Dashboard / Pipeline Runs**

*   **Layout:** Table view of recent and ongoing pipeline runs.
*   **Columns:** Run ID, Data Source, Pipeline Config, Start Time, End Time, Status (Pending, Running, Completed, Failed), Progress Bar, Actions (View Details, Download Output, Re-run).
*   **Controls:** "New Pipeline Run" button. Filters for status, data source.

**Page 2: New Pipeline Run / Configure Pipeline Run**

*   **Layout:** Form-based.
*   **Fields:**
    *   Dropdown: Select Data Source (from pre-configured sources).
    *   Dropdown: Select Pipeline Configuration (from saved configs, or "Create New").
    *   Input: Output Directory/Name for this run.
    *   (If "Create New" Pipeline Config): Sections for Chunking (Strategy, Size), PII (Detection toggle, Redaction toggle, Types to handle), etc.
*   **Actions:** "Start Run" button, "Save Configuration" button.

**Page 3: Data Sources Management**

*   **Layout:** Table view of configured data sources.
*   **Columns:** Name, Type (Notion, GDrive), Connection Status, Actions (Edit, Delete, Test Connection).
*   **Controls:** "Add New Data Source" button.
    *   **Modal/Form for Add/Edit Data Source:** Fields for Name, Type, API Key/Credentials (secure input), relevant IDs (e.g., Notion Workspace ID, GDrive Folder ID).

**Page 4: Pipeline Configurations Management**

*   **Layout:** Table view of saved pipeline configurations.
*   **Columns:** Name, Description, Last Modified, Actions (Edit, Clone, Delete).
*   **Controls:** "Create New Configuration" button.

**Page 5: Pipeline Run Details**

*   **Layout:** Summary section, then tabbed interface or expandable sections.
*   **Summary:** Run ID, Status, Timings, Overall Stats (Files Processed, Errors, Golden Rows produced).
*   **Tabs/Sections:**
    *   **Processed Files:** Table of individual source nodes, their status, errors (if any), link to logs/details.
    *   **Logs:** Real-time logs for the run.
    *   **Output:** Link to download JSONL and reports.
    *   **PII Report:** Summary of PII detected/redacted.

The UI should be clean, intuitive, and prioritize clarity of information, especially regarding errors and pipeline progress. For M2, a simple, functional UI using FastAPI's Jinja2 templating or a lightweight frontend framework (like HTMX or petite-vue) would be sufficient. A full SPA with React/Angular is likely overkill unless requirements significantly expand.
