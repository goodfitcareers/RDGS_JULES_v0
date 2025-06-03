-- clients -------------------------------------------------------------------
CREATE TABLE clients (
    id           UUID PRIMARY KEY,
    display_name TEXT        NOT NULL,
    notes        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- source_documents ----------------------------------------------------------
CREATE TABLE source_documents (
    id           UUID PRIMARY KEY,
    client_id    UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    path         TEXT        NOT NULL,  -- e.g. /blob/xyz.pdf
    mime_type    TEXT        NOT NULL,
    is_final_resume BOOLEAN  NOT NULL DEFAULT FALSE,
    uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum     TEXT        NOT NULL UNIQUE
);

CREATE INDEX idx_source_documents_client ON source_documents(client_id);

-- roles ---------------------------------------------------------------------
CREATE TYPE role_status_enum AS ENUM (
    'Parsed', 'RolesVerified', 'InputSynthesized',
    'InputCurated', 'Validated', 'Exported'
);

CREATE TABLE roles (
    id              UUID PRIMARY KEY,
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    company_name    TEXT NOT NULL,
    title           TEXT NOT NULL,
    start_date      DATE,
    end_date        DATE,
    output_text     TEXT NOT NULL,
    input_text_compact TEXT,
    validation_notes   TEXT,
    status          role_status_enum NOT NULL DEFAULT 'Parsed',
    revision        INT  NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_roles_client ON roles(client_id);
CREATE INDEX idx_roles_status ON roles(status);

-- evidence_snippets ---------------------------------------------------------
CREATE TABLE evidence_snippets (
    id           UUID PRIMARY KEY,
    role_id      UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    snippet_text TEXT NOT NULL,
    page_number  INT,
    relevance_score REAL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evidence_role ON evidence_snippets(role_id);

-- validation_notes ----------------------------------------------------------
CREATE TABLE validation_notes (
    role_id      UUID PRIMARY KEY REFERENCES roles(id) ON DELETE CASCADE,
    notes_json   JSONB NOT NULL,  -- arbitrary GPT‑4 output (schema‑validated upstream)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
