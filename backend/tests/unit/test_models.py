import pytest
from uuid import UUID, uuid4
from datetime import datetime, date, timezone # MODIFIED: Ensured timezone is imported
from typing import Dict, Any
from pydantic import ValidationError # For testing validation errors

# Import all models and enums from the corrected backend.models
from backend.models import (
    Client,
    SourceDocument,
    Role,
    EvidenceSnippet,
    ValidationNote,
    RoleStatus,
    # SQLModel, # Not directly used in tests for instantiation
)

# Helper for datetime comparisons (now expecting timezone-aware datetimes)
def assert_datetimes_close(dt1: datetime, dt2: datetime, tolerance_seconds: int = 2):
    # Ensure both are aware and in UTC for fair comparison
    if dt1.tzinfo is None:
        dt1 = dt1.replace(tzinfo=timezone.utc)
    else:
        dt1 = dt1.astimezone(timezone.utc)

    if dt2.tzinfo is None:
        dt2 = dt2.replace(tzinfo=timezone.utc)
    else:
        dt2 = dt2.astimezone(timezone.utc)

    assert abs((dt1 - dt2).total_seconds()) < tolerance_seconds

# Tests for the "Client/Role" schema models (Updated for new schema)

def test_client_model():
    now_utc = datetime.now(timezone.utc)
    client_id = uuid4()
    client = Client(
        id=client_id,
        display_name="Test Client LLC",
        notes="Some important notes about this client.",
        created_at=now_utc
    )
    assert client.id == client_id
    assert client.display_name == "Test Client LLC"
    assert client.notes == "Some important notes about this client."
    assert client.created_at == now_utc
    assert client.source_documents == []
    assert client.roles == []

    # Test defaults
    client_default = Client(display_name="Default Client") # display_name is required
    assert isinstance(client_default.id, UUID)
    assert isinstance(client_default.created_at, datetime)
    assert_datetimes_close(client_default.created_at, datetime.now(timezone.utc))
    assert client_default.notes is None

def test_sourcedocument_model():
    now_utc = datetime.now(timezone.utc)
    client_uuid = uuid4()
    doc_id = uuid4()

    sd = SourceDocument(
        id=doc_id,
        client_id=client_uuid,
        path="/documents/John_Doe_Resume.pdf",
        mime_type="application/pdf",
        is_final_resume=True,
        uploaded_at=now_utc,
        checksum="sha256_abcdef1234567890"
    )
    assert sd.id == doc_id
    assert sd.client_id == client_uuid
    assert sd.path == "/documents/John_Doe_Resume.pdf"
    assert sd.mime_type == "application/pdf"
    assert sd.is_final_resume is True
    assert sd.uploaded_at == now_utc
    assert sd.checksum == "sha256_abcdef1234567890"

    # Test defaults
    sd_default = SourceDocument(
        client_id=client_uuid,
        path="/docs/cover_letter.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        checksum="sha256_0987654321fedcba"
    )
    assert isinstance(sd_default.id, UUID)
    assert isinstance(sd_default.uploaded_at, datetime)
    assert_datetimes_close(sd_default.uploaded_at, datetime.now(timezone.utc))
    assert sd_default.is_final_resume is False # Default value

def test_role_model():
    now_utc = datetime.now(timezone.utc)
    client_uuid = uuid4()
    role_id = uuid4()
    start_d = date(2021, 6, 1)
    end_d = date(2023, 5, 31)

    role = Role(
        id=role_id,
        client_id=client_uuid,
        company_name="Tech Solutions Ltd.",
        title="Senior Software Engineer",
        start_date=start_d,
        end_date=end_d,
        output_text="Developed and maintained key software components.", # Required
        input_text_compact="SSE at Tech Solutions.",
        validation_notes="This role has been cross-verified.", # String field
        status=RoleStatus.ROLES_VERIFIED, # Enum from new definition
        revision=2,
        created_at=now_utc,
        updated_at=now_utc
    )
    assert role.id == role_id
    assert role.client_id == client_uuid
    assert role.company_name == "Tech Solutions Ltd."
    assert role.title == "Senior Software Engineer"
    assert role.start_date == start_d
    assert role.end_date == end_d
    assert role.output_text == "Developed and maintained key software components."
    assert role.input_text_compact == "SSE at Tech Solutions."
    assert role.validation_notes == "This role has been cross-verified."
    assert role.status == RoleStatus.ROLES_VERIFIED
    assert role.revision == 2
    assert role.created_at == now_utc
    assert role.updated_at == now_utc
    assert role.evidence_snippets == []
    # validation_notes is a field on Role, not a separate list of ValidationNote objects

    # Test defaults
    role_default = Role(
        client_id=client_uuid,
        company_name="Innovatech",
        title="Developer",
        output_text="Default output text." # Required
    )
    assert isinstance(role_default.id, UUID)
    assert role_default.start_date is None
    assert role_default.end_date is None
    assert role_default.input_text_compact is None
    assert role_default.validation_notes is None # Default for Optional[str]
    assert role_default.status == RoleStatus.PARSED # Default from model
    assert role_default.revision == 0 # Default
    assert isinstance(role_default.created_at, datetime)
    assert isinstance(role_default.updated_at, datetime)
    assert_datetimes_close(role_default.created_at, datetime.now(timezone.utc))
    assert_datetimes_close(role_default.updated_at, datetime.now(timezone.utc))


def test_evidencesnippet_model():
    now_utc = datetime.now(timezone.utc)
    role_uuid = uuid4() # Changed from doc_uuid as it links to Role
    snippet_id = uuid4()

    es = EvidenceSnippet(
        id=snippet_id,
        role_id=role_uuid, # Required, links to Role
        snippet_text="Key responsibility: Leading the backend team.",
        page_number=1,
        relevance_score=0.85, # New field
        created_at=now_utc
    )
    assert es.id == snippet_id
    assert es.role_id == role_uuid
    assert es.snippet_text == "Key responsibility: Leading the backend team."
    assert es.page_number == 1
    assert es.relevance_score == 0.85
    assert es.created_at == now_utc

    # Test defaults
    es_default = EvidenceSnippet(role_id=role_uuid, snippet_text="Another important point.")
    assert isinstance(es_default.id, UUID)
    assert es_default.page_number is None
    assert es_default.relevance_score is None # Default for Optional[float]
    assert isinstance(es_default.created_at, datetime)
    assert_datetimes_close(es_default.created_at, datetime.now(timezone.utc))


def test_validationnote_model():
    now_utc = datetime.now(timezone.utc)
    associated_role_id = uuid4()

    notes_data = {"accuracy": "Confirmed", "source": "Email from HR"}
    vn = ValidationNote(
        role_id=associated_role_id, # Is PK and FK
        notes_json=notes_data, # Changed from note_text
        created_at=now_utc
    )
    assert vn.role_id == associated_role_id
    assert vn.notes_json == notes_data
    assert vn.created_at == now_utc

    # Test defaults
    vn_default = ValidationNote(role_id=uuid4()) # role_id is required (PK)
    assert isinstance(vn_default.role_id, UUID)
    assert vn_default.notes_json == {} # Default factory for Dict
    assert isinstance(vn_default.created_at, datetime)
    assert_datetimes_close(vn_default.created_at, datetime.now(timezone.utc))


def test_rolestatus_enum_values():
    # Test new enum values
    assert RoleStatus.PARSED.value == "Parsed"
    assert RoleStatus.ROLES_VERIFIED.value == "RolesVerified"
    assert RoleStatus.INPUT_SYNTHESIZED.value == "InputSynthesized"
    assert RoleStatus.INPUT_CURATED.value == "InputCurated"
    assert RoleStatus.VALIDATED.value == "Validated"
    assert RoleStatus.EXPORTED.value == "Exported"

    assert isinstance(RoleStatus.PARSED, RoleStatus)
    assert isinstance(RoleStatus.PARSED.value, str)

def test_pydantic_validation_for_new_models():
    client_uuid = uuid4()
    role_uuid = uuid4()

    with pytest.raises(ValidationError, match="display_name"):
        Client.model_validate({})

    with pytest.raises(ValidationError): # Check for multiple missing fields
        SourceDocument.model_validate({"client_id": client_uuid}) # path, mime_type, checksum missing

    with pytest.raises(ValidationError): # Check for multiple missing fields
        Role.model_validate({"client_id": client_uuid}) # company_name, title, output_text missing

    with pytest.raises(ValidationError, match="type=enum"): # Updated regex for enum validation error
        Role.model_validate({
            "client_id": client_uuid, "company_name": "Test", "title": "Test",
            "output_text": "text", "status": "NON_EXISTENT_STATUS"
        })

    with pytest.raises(ValidationError): # snippet_text missing
        EvidenceSnippet.model_validate({"role_id": role_uuid})

    with pytest.raises(ValidationError, match="role_id"): # role_id is PK
        ValidationNote.model_validate({})


def test_relationship_attributes_exist_for_new_models():
    client = Client(display_name="Rel Test Client")
    assert hasattr(client, "source_documents")
    assert hasattr(client, "roles")

    source_doc = SourceDocument(
        client_id=uuid4(), path="p", mime_type="m", checksum="c"
    )
    assert hasattr(source_doc, "client")
    # No evidence_snippets on SourceDocument anymore

    role = Role(
        client_id=uuid4(), company_name="Comp", title="Title", output_text="text"
    )
    assert hasattr(role, "client")
    assert hasattr(role, "evidence_snippets")
    assert isinstance(role.validation_notes, (str, type(None))) # It's a field now

    evidence_snippet = EvidenceSnippet(role_id=uuid4(), snippet_text="text")
    # No source_document on EvidenceSnippet anymore
    assert hasattr(evidence_snippet, "role")

    validation_note = ValidationNote(role_id=uuid4())
    assert hasattr(validation_note, "role")

# This test is obsolete as metadata_ and its alias have been removed from models
# def test_metadata_aliasing_in_new_models():
#     pass
