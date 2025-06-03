-- Enum for Role Status
CREATE TYPE role_status_enum AS ENUM (
    'DRAFT',
    'PARSED',
    'VERIFIED',
    'FLAGGED',
    'ARCHIVED'
);

-- Clients table
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- Using gen_random_uuid() for PostgreSQL
    display_name TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_clients_display_name ON clients(display_name);

-- Source documents (e.g., resumes, JDs, web pages)
CREATE TABLE source_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_type VARCHAR(50), -- e.g., 'pdf', 'docx', 'notion_page_id'
    content_hash VARCHAR(64), -- SHA256 hash of the raw file content
    raw_text TEXT,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processing_status VARCHAR(50) DEFAULT 'PENDING', -- e.g., PENDING, EXTRACTED, FAILED_EXTRACTION
    metadata JSONB -- Page numbers, URLs, Notion-specific properties etc.
);
CREATE INDEX idx_source_documents_client_id ON source_documents(client_id);
CREATE INDEX idx_source_documents_content_hash ON source_documents(content_hash);

-- Parsed roles from source documents
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    company_name TEXT NOT NULL,
    title TEXT NOT NULL,
    start_date DATE,
    end_date DATE, -- Null if current
    output_text TEXT, -- Full parsed role description from LLM, possibly from description_points
    input_text_compact TEXT, -- Compacted input text provided to LLM for parsing this role
    status role_status_enum DEFAULT 'PARSED', -- Default to PARSED as per prompt example
    revision INTEGER DEFAULT 0, -- For optimistic locking or versioning
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Should auto-update
);
CREATE INDEX idx_roles_client_id ON roles(client_id);
CREATE INDEX idx_roles_company_name ON roles(company_name);
CREATE INDEX idx_roles_title ON roles(title);

-- Evidence snippets linking roles back to source documents
CREATE TABLE evidence_snippets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document_id UUID NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE SET NULL, -- Can be unlinked or linked later
    snippet_text TEXT NOT NULL,
    file_name TEXT, -- Denormalized from source_documents for easier display
    page_number INTEGER,
    line_number_start INTEGER,
    line_number_end INTEGER,
    metadata JSONB, -- e.g., bounding box coordinates for PDFs
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_evidence_snippets_source_document_id ON evidence_snippets(source_document_id);
CREATE INDEX idx_evidence_snippets_role_id ON evidence_snippets(role_id);

-- Validation notes for human review and correction tracking
CREATE TABLE validation_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    note_text TEXT NOT NULL,
    author VARCHAR(255), -- Or a User ID if users table is added
    -- status_change role_status_enum, -- If this note resulted in a status change for the role (optional)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_validation_notes_role_id ON validation_notes(role_id);

-- Trigger for updated_at in roles table (example for PostgreSQL)
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_roles_updated_at
BEFORE UPDATE ON roles
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();
