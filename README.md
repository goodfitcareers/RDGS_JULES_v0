# Dataset Distiller v0.2

A fast, fail-loud pipeline that converts messy client archives into golden JSONL rows for GPT-4 fine-tuning.

## Core Problem

The "Dataset Distiller" project aims to solve the critical challenge of transforming heterogeneous, messy, and often deeply nested client-provided data archives into clean, structured, and fine-tune-ready JSONL datasets for Large Language Models (LLMs) like GPT-4.

Many organizations possess vast amounts of valuable data locked away in various formats (Notion workspaces, Google Drive folders, Confluence dumps, ZIP archives of mixed files, etc.). This data, while potentially rich in domain-specific knowledge, is unusable for LLM fine-tuning in its raw state. The process of manually cleaning, structuring, and converting this data is time-consuming, error-prone, and requires significant technical expertise. This bottleneck severely limits the ability of organizations to leverage their proprietary data for creating powerful, customized LLM applications.

Dataset Distiller will provide an automated, robust, and extensible solution to this problem, enabling users to:

1.  **Ingest** data from diverse sources.
2.  **Process** and **transform** the data through a configurable pipeline (chunking, PII removal, metadata extraction, etc.).
3.  **Export** clean, validated JSONL files suitable for LLM fine-tuning.
4.  **Maintain** data provenance and quality control throughout the process.

## High-Level Requirements

*   **Modular Ingestion:** Support for various input sources (Notion, GDrive, local files/folders, Confluence initially). Extensible for future sources.
*   **Configurable Pipeline:** Allow users to define and customize data processing steps (e.g., document parsing, chunking strategies, PII redaction, metadata enrichment).
*   **Quality Control:** Implement validation checks and provide reports on data quality and processing outcomes.
*   **Scalability:** Design the system to handle large volumes of data efficiently.
*   **User-Friendly Interface:** Provide a simple CLI and a basic web UI for managing ingestion, pipeline configuration, and monitoring.
*   **Reproducibility:** Ensure that pipeline runs are reproducible and versioned.
*   **Security:** Handle sensitive data with care, including robust PII detection and redaction.

## Key Features (M1 & M2 Milestones)

*   **M1 (Core Pipeline & CLI):**
    *   Local file/folder ingestion (ZIP, TXT, MD, PDF, DOCX, HTML).
    *   Notion API ingestion.
    *   Core processing pipeline:
        *   File type detection and parsing.
        *   Text extraction.
        *   Basic chunking (by size or separator).
        *   Metadata extraction (source, filename, basic stats).
        *   PII detection (using presidio or similar).
        *   Output to JSONL.
    *   CLI for pipeline execution and configuration.
    *   PostgreSQL database for metadata, job status, and extracted content.
    *   Basic reporting (counts, errors).
    *   Ruff, Black, MyPy for code quality. Pytest for testing. Pre-commit hooks.
    *   Initial CI/CD setup (GitHub Actions).
*   **M2 (Web UI & Enhanced Features):**
    *   Web UI (FastAPI + simple frontend) for:
        *   Managing data sources.
        *   Configuring pipelines.
        *   Monitoring job progress.
        *   Viewing/downloading results and reports.
    *   User authentication for UI.
    *   Enhanced PII redaction options.
    *   More sophisticated chunking strategies (e.g., semantic chunking if feasible).
    *   Support for Google Drive ingestion.
    *   Alembic for database migrations.
    *   Basic data versioning.

## Tech Stack (Proposed)

*   **Backend:** Python (FastAPI)
*   **Data Processing:** LangChain, Unstructured.io, Presidio (for PII), custom Python scripts.
*   **Database:** PostgreSQL (via SQLModel)
*   **Frontend (M2):** Simple HTML/CSS/JS or a lightweight framework like HTMX or Vue/React if necessary.
*   **DevOps:** Docker, GitHub Actions, Pre-commit, Poetry.
*   **Orchestration (Future):** Potentially LangGraph or a simple job queue like Celery if complexity grows.

## Getting Started

*(To be filled in as project develops)*

```bash
# Clone the repository
git clone https://github.com/your-org/dataset-distiller.git
cd dataset-distiller

# Install dependencies (using Poetry)
poetry install

# Configure environment variables (see .env.example)
cp .env.example .env
# ... edit .env with your settings ...

# Run database migrations (M2 onwards)
# poetry run alembic upgrade head

# Run the application (M2 onwards for UI)
# poetry run uvicorn backend.main:app --reload
```

## Contributing

Contributions are welcome! Please see `CONTRIBUTING.md` (to be created) for guidelines.

## License

This project is licensed under the MIT License - see the `LICENSE` file (to be created) for details.
