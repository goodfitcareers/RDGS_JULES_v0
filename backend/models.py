from datetime import date, datetime, timezone
from enum import Enum as PyEnum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.types import JSON # Changed from JSONB for broader compatibility
from sqlmodel import Column, Field, Relationship, SQLModel


# Enum definition for RoleStatus
class RoleStatus(str, PyEnum):
    PARSED = "Parsed"
    ROLES_VERIFIED = "RolesVerified"
    INPUT_SYNTHESIZED = "InputSynthesized"
    INPUT_CURATED = "InputCurated"
    VALIDATED = "Validated"
    EXPORTED = "Exported"


# Table Models
class Client(SQLModel, table=True):
    __tablename__ = "clients"
    id: UUID = Field(
        default_factory=uuid4, primary_key=True, index=True, nullable=False
    )
    display_name: str = Field(
        ..., index=True
    )  # Explicitly Pydantic-required and indexed
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    source_documents: List["SourceDocument"] = Relationship(back_populates="client")
    roles: List["Role"] = Relationship(back_populates="client")
    export_audits: List["ExportAudit"] = Relationship(back_populates="client")


class SourceDocument(SQLModel, table=True):
    __tablename__ = "source_documents"
    id: UUID = Field(
        default_factory=uuid4, primary_key=True, index=True, nullable=False
    )
    client_id: UUID = Field(foreign_key="clients.id", index=True, nullable=False)
    path: str
    mime_type: str
    is_final_resume: bool = Field(default=False)
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
    checksum: str = Field(unique=True)

    client: "Client" = Relationship(back_populates="source_documents")


class Role(SQLModel, table=True):
    __tablename__ = "roles"
    id: UUID = Field(
        default_factory=uuid4, primary_key=True, index=True, nullable=False
    )
    client_id: UUID = Field(foreign_key="clients.id", index=True, nullable=False)
    company_name: str
    title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    output_text: str
    input_text_compact: Optional[str] = Field(default=None)
    validation_notes: Optional[str] = Field(default=None)  # This is a direct text field
    status: RoleStatus = Field(default=RoleStatus.PARSED, nullable=False)
    revision: int = Field(default=0, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)},
    )

    client: "Client" = Relationship(back_populates="roles")
    evidence_snippets: List["EvidenceSnippet"] = Relationship(back_populates="role")
    # The One-to-One ValidationNote is linked via its own role_id PK/FK


class EvidenceSnippet(SQLModel, table=True):
    __tablename__ = "evidence_snippets"
    id: UUID = Field(
        default_factory=uuid4, primary_key=True, index=True, nullable=False
    )
    role_id: UUID = Field(foreign_key="roles.id", index=True, nullable=False)
    snippet_text: str
    page_number: Optional[int] = None
    relevance_score: Optional[float] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    role: "Role" = Relationship(back_populates="evidence_snippets")


class ValidationNote(SQLModel, table=True):
    __tablename__ = "validation_notes"
    # role_id is PK and FK
    role_id: UUID = Field(
        primary_key=True, foreign_key="roles.id", index=True, nullable=False
    )  # Removed default_factory
    notes_json: Dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False) # Changed JSONB to JSON
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    # For one-to-one, SQLModel infers the relationship from the PK/FK.
    # If explicit 'role' attribute is needed for type hinting or access,
    # it can be added but back_populates is tricky for one-to-one where
    # the FK is also the PK on the child. Usually, direct access via querying is done.
    # Per spec, a 'role: Role' relationship is expected.
    role: "Role" = Relationship()


class ExportAudit(SQLModel, table=True):
    __tablename__ = "export_audits"
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    client_id: UUID = Field(foreign_key="clients.id", index=True, nullable=False)
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    row_count: int = Field(nullable=False)
    filename: str = Field(nullable=False)
    checksum: str = Field(nullable=False)  # SHA-256

    client: "Client" = Relationship(back_populates="export_audits")


# Update forward refs for all models
Client.model_rebuild()
SourceDocument.model_rebuild()
Role.model_rebuild()
EvidenceSnippet.model_rebuild()
ValidationNote.model_rebuild()
ExportAudit.model_rebuild()
