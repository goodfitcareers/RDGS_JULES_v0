from datetime import datetime, date, timezone
from enum import Enum as PyEnum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel, Column, JSON, Enum as SaEnum # For SQLAlchemy Enum type
from sqlalchemy import Text # For TEXT column type explicitly

# Enum definition for RoleStatus
# This matches CREATE TYPE role_status_enum AS ENUM (...) in DDL
class RoleStatus(str, PyEnum):
    DRAFT = "DRAFT"
    PARSED = "PARSED"
    VERIFIED = "VERIFIED"
    FLAGGED = "FLAGGED"
    ARCHIVED = "ARCHIVED"

# Table Models
class ClientBase(SQLModel):
    display_name: str = Field(index=True) # DDL has NOT NULL, implies required
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))

class Client(ClientBase, table=True):
    __tablename__ = "clients"
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    source_documents: List["SourceDocument"] = Relationship(back_populates="client")
    roles: List["Role"] = Relationship(back_populates="client")

class SourceDocumentBase(SQLModel):
    file_name: str # NOT NULL in DDL
    file_type: Optional[str] = Field(default=None, max_length=50) # VARCHAR(50) in DDL
    content_hash: Optional[str] = Field(default=None, max_length=64, index=True) # VARCHAR(64)
    raw_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    processing_status: Optional[str] = Field(default="PENDING", max_length=50) # VARCHAR(50)
    # Using metadata_ to avoid conflict with SQLModel's own .metadata attribute
    # The DDL column name is 'metadata'. Pydantic alias allows instantiation with 'metadata'.
    metadata_: Optional[Dict[str, Any]] = Field(default=None, alias="metadata", sa_column=Column(JSON, name="metadata"))

class SourceDocument(SourceDocumentBase, table=True):
    __tablename__ = "source_documents"
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    client_id: UUID = Field(foreign_key="clients.id", index=True, nullable=False) # NOT NULL in DDL
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    client: Client = Relationship(back_populates="source_documents")
    evidence_snippets: List["EvidenceSnippet"] = Relationship(back_populates="source_document")

class RoleBase(SQLModel):
    company_name: str # NOT NULL in DDL
    title: str # NOT NULL in DDL
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    output_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    input_text_compact: Optional[str] = Field(default=None, sa_column=Column(Text))
    # For status, using SaEnum to map to PostgreSQL native ENUM type
    status: RoleStatus = Field(default=RoleStatus.PARSED, sa_column=Column(SaEnum(RoleStatus, name="role_status_enum", create_type=False), nullable=False))
    revision: int = Field(default=0, nullable=False) # Default 0, NOT NULL

class Role(RoleBase, table=True):
    __tablename__ = "roles"
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    client_id: UUID = Field(foreign_key="clients.id", index=True, nullable=False) # NOT NULL
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)} # For DB-side update
    )

    client: Client = Relationship(back_populates="roles")
    evidence_snippets: List["EvidenceSnippet"] = Relationship(back_populates="role")
    validation_notes: List["ValidationNote"] = Relationship(back_populates="role")

class EvidenceSnippetBase(SQLModel):
    snippet_text: str = Field(sa_column=Column(Text)) # NOT NULL
    file_name: Optional[str] = Field(default=None) # TEXT in DDL
    page_number: Optional[int] = None
    line_number_start: Optional[int] = None
    line_number_end: Optional[int] = None
    metadata_: Optional[Dict[str, Any]] = Field(default=None, alias="metadata", sa_column=Column(JSON, name="metadata"))

class EvidenceSnippet(EvidenceSnippetBase, table=True):
    __tablename__ = "evidence_snippets"
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    source_document_id: UUID = Field(foreign_key="source_documents.id", index=True, nullable=False) # NOT NULL
    role_id: Optional[UUID] = Field(default=None, foreign_key="roles.id", index=True) # Nullable
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    source_document: SourceDocument = Relationship(back_populates="evidence_snippets")
    role: Optional[Role] = Relationship(back_populates="evidence_snippets")

class ValidationNoteBase(SQLModel):
    note_text: str = Field(sa_column=Column(Text)) # NOT NULL
    author: Optional[str] = Field(default=None, max_length=255) # VARCHAR(255)
    # status_change: Optional[RoleStatus] = Field(default=None, sa_column=Column(SaEnum(RoleStatus, name="role_status_enum", create_type=False)))


class ValidationNote(ValidationNoteBase, table=True):
    __tablename__ = "validation_notes"
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    role_id: UUID = Field(foreign_key="roles.id", index=True, nullable=False) # NOT NULL
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    role: Role = Relationship(back_populates="validation_notes")

# Update forward refs for all models
Client.model_rebuild()
SourceDocument.model_rebuild()
Role.model_rebuild()
EvidenceSnippet.model_rebuild()
ValidationNote.model_rebuild()
