# M0: Vision & Glossary - Dataset Distiller

## 1. Project Vision

**Dataset Distiller** is a fast, fail-loud data processing pipeline designed to convert messy, heterogeneous client-provided archives (Notion, GDrive, Confluence, ZIPs of mixed files) into clean, structured, fine-tune-ready JSONL datasets for Large Language Models (LLMs) like GPT-4.

The core philosophy is **"Garbage In, Explicit Error Out, Clean Data Out."** We prioritize early detection of malformed data, unsupported file types, and inconsistencies, providing clear, actionable error reports rather than attempting to silently fix or ignore issues. This ensures high-quality output and builds user trust.

The system will be modular, extensible, and configurable, allowing users to define ingestion sources, select processing steps (e.g., PII redaction, chunking strategy, metadata extraction), and specify output formats. While initially focused on JSONL for fine-tuning, the architecture should permit future expansion to other structured formats.

**Target Users:**

*   AI/ML engineers and researchers needing to prepare custom datasets for fine-tuning.
*   Data scientists working with unstructured client data.
*   Organizations looking to leverage proprietary data for custom LLM solutions.

**Key Differentiators:**

*   **Speed & Efficiency:** Optimized for fast processing of large datasets.
*   **Robust Error Handling:** "Fail-loud" approach with detailed error reporting.
*   **Configurability:** Flexible pipeline definition to suit diverse needs.
*   **Extensibility:** Modular design for adding new data sources and processing modules.
*   **Focus on Fine-tuning:** Output specifically tailored for LLM fine-tuning workflows.

## 2. Glossary of Terms

| Term                      | Definition                                                                                                                               | Aliases/Notes                                          |
| :------------------------ | :--------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------- |
| **Archive**               | A collection of files and folders provided by a client, often compressed (e.g., ZIP, TAR.GZ) or from a cloud source.                     | Client Data, Raw Data                                  |
| **Source Node**           | An individual file or data entry within an Archive (e.g., a single DOCX file, a Notion page, a row in a CSV).                           | Document, File, Data Item                              |
| **Ingestion**             | The process of reading Source Nodes from an Archive and bringing them into the pipeline.                                                 | Data Intake, Loading                                   |
| **Parsing**               | The process of converting a Source Node from its native format (e.g., PDF, DOCX, HTML) into a structured text representation.             | Text Extraction                                        |
| **Raw Content**           | The direct textual (or structured, if applicable) output from parsing a Source Node, before further processing like cleaning or chunking. | Extracted Text                                         |
| **Content Item**          | A segment of Raw Content, typically a text passage, that has associated metadata and is the fundamental unit for processing.             | Chunk, Text Segment                                    |
| **Chunking**              | The process of dividing Raw Content into smaller, manageable Content Items based on defined strategies (size, separators, semantic).     | Segmentation                                           |
| **PII**                   | Personally Identifiable Information (e.g., names, emails, phone numbers, credit card details).                                           | Sensitive Data                                         |
| **PII Detection**         | The process of identifying potential PII within Content Items.                                                                           |                                                        |
| **PII Redaction**         | The process of removing or masking detected PII from Content Items.                                                                      | Anonymization, Masking                                 |
| **Metadata**              | Data about data; information associated with Source Nodes and Content Items (e.g., filename, source URL, creation date, PII tags).       |                                                        |
| **Enrichment**            | The process of adding or refining Metadata for Content Items (e.g., adding summaries, keywords, sentiment scores).                       | Metadata Enhancement                                   |
| **Transformation**        | Any process that modifies the content or structure of Content Items (e.g., PII redaction, format conversion, text cleaning).             |                                                        |
| **Validation**            | The process of checking Content Items against predefined quality criteria or rules.                                                      | Quality Control (QC), Data Integrity Check             |
| **Golden Row**            | A fully processed, validated, and cleaned Content Item, ready for export, typically in JSONL format.                                     | Fine-tune Ready Record, Output Record                  |
| **JSONL**                 | A text file format where each line is a valid JSON object, commonly used for LLM training data.                                          | JSON Lines                                             |
| **Pipeline**              | A configurable sequence of processing stages (Ingestion, Parsing, Chunking, PII Handling, Transformation, Validation, Export).           | Workflow, Data Flow                                    |
| **Pipeline Run**          | A specific execution of a defined Pipeline on a given Archive.                                                                           | Job, Processing Task                                   |
| **State Database (StateDB)** | PostgreSQL database used to store metadata, pipeline configurations, job status, PII locations, and potentially cached content.          | Metadata Store, Job Store                              |
| **Idempotency**           | The property of an operation that ensures it can be applied multiple times without changing the result beyond the initial application.     | Critical for resumable pipelines                       |
| **Fail-Loud**             | A system design principle where errors are reported explicitly and early, rather than being silently ignored or handled ambiguously.     | Error-First                                            |
| **Unstructured.io**       | A library for parsing various document types into a common format.                                                                       |                                                        |
| **Presidio**              | A library for PII detection and anonymization.                                                                                           |                                                        |
| **LangChain**             | A framework for developing applications powered by language models.                                                                      | Used for some text processing/chunking capabilities. |
| **LangGraph**             | A library for building stateful, multi-actor applications with LLMs, built on top of LangChain.                                        | Potential for pipeline orchestration.                  |
| **Tenant**                | (Future Consideration) A logical separation of data and configurations for different users or clients of the system.                     | Multi-tenancy                                        |
| **Dataset**               | A collection of Golden Rows exported from a Pipeline Run, typically a single JSONL file.                                                 | Output Dataset, Fine-tuning Dataset                    |

This glossary will evolve as the project progresses.
