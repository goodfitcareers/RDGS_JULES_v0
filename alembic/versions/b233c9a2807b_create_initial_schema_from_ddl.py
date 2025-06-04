"""Create initial schema from DDL

Revision ID: b233c9a2807b
Revises:
Create Date: 2025-06-04 15:09:06.528710

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b233c9a2807b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
    CREATE TABLE clients (
        id           UUID PRIMARY KEY,
        display_name TEXT        NOT NULL,
        notes        TEXT,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)
    op.execute("""
    CREATE TABLE source_documents (
        id           UUID PRIMARY KEY,
        client_id    UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        path         TEXT        NOT NULL,
        mime_type    TEXT        NOT NULL,
        is_final_resume BOOLEAN  NOT NULL DEFAULT FALSE,
        uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        checksum     TEXT        NOT NULL UNIQUE
    )
    """)
    op.execute("""
    CREATE INDEX idx_source_documents_client ON source_documents(client_id)
    """)
    op.execute("""
    CREATE TYPE role_status_enum AS ENUM (
        'Parsed', 'RolesVerified', 'InputSynthesized',
        'InputCurated', 'Validated', 'Exported'
    )
    """)
    op.execute("""
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
    )
    """)
    op.execute("""
    CREATE INDEX idx_roles_client ON roles(client_id)
    """)
    op.execute("""
    CREATE INDEX idx_roles_status ON roles(status)
    """)
    op.execute("""
    CREATE TABLE evidence_snippets (
        id           UUID PRIMARY KEY,
        role_id      UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
        snippet_text TEXT NOT NULL,
        page_number  INT,
        relevance_score REAL,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)
    op.execute("""
    CREATE INDEX idx_evidence_role ON evidence_snippets(role_id)
    """)
    op.execute("""
    CREATE TABLE validation_notes (
        role_id      UUID PRIMARY KEY REFERENCES roles(id) ON DELETE CASCADE,
        notes_json   JSONB NOT NULL,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('validation_notes')
    op.drop_table('evidence_snippets')
    op.drop_table('roles')
    op.execute("DROP TYPE IF EXISTS role_status_enum")
    op.drop_table('source_documents')
    op.drop_table('clients')
