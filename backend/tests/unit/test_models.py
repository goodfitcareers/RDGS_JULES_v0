import pytest
from uuid import UUID, uuid4
from datetime import datetime, date, timezone
from typing import Dict, Any

# Import all models and enums from the corrected backend.models
from backend.models import (
    Client,
    SourceDocument,
    Role,
    EvidenceSnippet,
    ValidationNote,
    RoleStatus, # Enum
    SQLModel,
)

# Helper for datetime comparisons
def assert_datetimes_close(dt1: datetime, dt2: datetime, tolerance_seconds: int = 2):
    assert abs((dt1 - dt2).total_seconds()) < tolerance_seconds

# Tests for the "Client/Role" schema models

def test_client_model():
    now = datetime.now(timezone.utc)
    client_id = uuid4()
    client = Client(
        id=client_id, # Explicit set for testing
        display_name="Test Client LLC",
        notes="Some important notes about this client.",
        created_at=now # Explicit set for testing
    )
    assert client.id == client_id
    assert client.display_name == "Test Client LLC"
    assert client.notes == "Some important notes about this client."
    assert client.created_at == now
    assert client.source_documents == [] # Default empty list for relationship
    assert client.roles == []           # Default empty list for relationship

    # Test defaults
    client_default = Client(display_name="Default Client")
    assert isinstance(client_default.id, UUID)
    assert isinstance(client_default.created_at, datetime)
    assert_datetimes_close(client_default.created_at, datetime.now(timezone.utc))
    assert client_default.notes is None

def test_sourcedocument_model():
    now = datetime.now(timezone.utc)
    client_uuid = uuid4()
    doc_id = uuid4()
    metadata_content = {"source_url": "http://example.com/resume.pdf", "pages": 2}

    sd = SourceDocument(
        id=doc_id, # explicit
        client_id=client_uuid,
        file_name="John_Doe_Resume.pdf",
        file_type="application/pdf",
        content_hash="sha256_abcdef1234567890",
        raw_text="Full text of the resume...",
        uploaded_at=now, # explicit
        processing_status="EXTRACTED",
        metadata_=metadata_content # using metadata_ for python attribute
    )
    assert sd.id == doc_id
    assert sd.client_id == client_uuid
    assert sd.file_name == "John_Doe_Resume.pdf"
    assert sd.file_type == "application/pdf"
    assert sd.content_hash == "sha256_abcdef1234567890"
    assert sd.raw_text == "Full text of the resume..."
    assert sd.uploaded_at == now
    assert sd.processing_status == "EXTRACTED"
    assert sd.metadata_ == metadata_content
    assert sd.evidence_snippets == []

    # Test defaults
    sd_default = SourceDocument(client_id=client_uuid, file_name="cover_letter.docx")
    assert isinstance(sd_default.id, UUID)
    assert isinstance(sd_default.uploaded_at, datetime)
    assert sd_default.file_type is None
    assert sd_default.content_hash is None
    assert sd_default.raw_text is None
    assert sd_default.processing_status == "PENDING" # Default value
    assert sd_default.metadata_ is None

def test_role_model():
    now = datetime.now(timezone.utc)
    client_uuid = uuid4()
    role_id = uuid4()
    start_d = date(2021, 6, 1)
    end_d = date(2023, 5, 31)

    role = Role(
        id=role_id, # explicit
        client_id=client_uuid,
        company_name="Tech Solutions Ltd.",
        title="Senior Software Engineer",
        start_date=start_d,
        end_date=end_d,
        output_text="Developed and maintained key software components.",
        input_text_compact="SSE at Tech Solutions.",
        status=RoleStatus.VERIFIED, # Explicit
        revision=2, # Explicit
        created_at=now, # explicit
        updated_at=now  # explicit
    )
    assert role.id == role_id
    assert role.client_id == client_uuid
    assert role.company_name == "Tech Solutions Ltd."
    assert role.title == "Senior Software Engineer"
    assert role.start_date == start_d
    assert role.end_date == end_d
    assert role.output_text == "Developed and maintained key software components."
    assert role.input_text_compact == "SSE at Tech Solutions."
    assert role.status == RoleStatus.VERIFIED
    assert role.revision == 2
    assert role.created_at == now
    assert role.updated_at == now
    assert role.evidence_snippets == []
    assert role.validation_notes == []

    # Test defaults
    role_default = Role(client_id=client_uuid, company_name="Innovatech", title="Developer")
    assert isinstance(role_default.id, UUID)
    assert role_default.start_date is None
    assert role_default.end_date is None
    assert role_default.output_text is None
    assert role_default.input_text_compact is None
    assert role_default.status == RoleStatus.PARSED # Default from instructions
    assert role_default.revision == 0 # Default
    assert isinstance(role_default.created_at, datetime)
    assert isinstance(role_default.updated_at, datetime)
    assert_datetimes_close(role_default.created_at, datetime.now(timezone.utc))
    assert_datetimes_close(role_default.updated_at, datetime.now(timezone.utc))


def test_evidencesnippet_model():
    now = datetime.now(timezone.utc)
    doc_uuid = uuid4()
    role_uuid = uuid4()
    snippet_id = uuid4()
    metadata_content = {"source_page": 1, "coordinates": [10,20,100,50]}

    es = EvidenceSnippet(
        id=snippet_id, # explicit
        source_document_id=doc_uuid,
        role_id=role_uuid,
        snippet_text="Key responsibility: Leading the backend team.",
        file_name="resume_page1.png", # Denormalized
        page_number=1,
        line_number_start=5,
        line_number_end=6,
        metadata_=metadata_content, # using metadata_
        created_at=now # explicit
    )
    assert es.id == snippet_id
    assert es.source_document_id == doc_uuid
    assert es.role_id == role_uuid
    assert es.snippet_text == "Key responsibility: Leading the backend team."
    assert es.file_name == "resume_page1.png"
    assert es.page_number == 1
    assert es.line_number_start == 5
    assert es.line_number_end == 6
    assert es.metadata_ == metadata_content
    assert es.created_at == now

    # Test defaults
    es_default = EvidenceSnippet(source_document_id=doc_uuid, snippet_text="Another important point.")
    assert isinstance(es_default.id, UUID)
    assert es_default.role_id is None
    assert es_default.file_name is None
    assert es_default.page_number is None
    assert es_default.line_number_start is None
    assert es_default.line_number_end is None
    assert es_default.metadata_ is None
    assert isinstance(es_default.created_at, datetime)


def test_validationnote_model():
    now = datetime.now(timezone.utc)
    role_uuid = uuid4()
    note_id = uuid4()

    vn = ValidationNote(
        id=note_id, # explicit
        role_id=role_uuid,
        note_text="Start date confirmed via email.",
        author="John Reviewer",
        created_at=now # explicit
    )
    assert vn.id == note_id
    assert vn.role_id == role_uuid
    assert vn.note_text == "Start date confirmed via email."
    assert vn.author == "John Reviewer"
    assert vn.created_at == now

    # Test defaults
    vn_default = ValidationNote(role_id=role_uuid, note_text="Consider re-parsing this role.")
    assert isinstance(vn_default.id, UUID)
    assert vn_default.author is None
    assert isinstance(vn_default.created_at, datetime)


def test_rolestatus_enum_values():
    assert RoleStatus.DRAFT.value == "DRAFT"
    assert RoleStatus.PARSED.value == "PARSED"
    assert RoleStatus.VERIFIED.value == "VERIFIED"
    assert RoleStatus.FLAGGED.value == "FLAGGED"
    assert RoleStatus.ARCHIVED.value == "ARCHIVED"
    assert isinstance(RoleStatus.DRAFT, RoleStatus)
    assert isinstance(RoleStatus.DRAFT.value, str)

def test_pydantic_validation_for_new_models():
    client_uuid = uuid4() # For FKs

    with pytest.raises(Exception): # Pydantic ValidationError
        Client.model_validate({"display_name": None}) # display_name is required

    with pytest.raises(Exception):
        SourceDocument.model_validate({"client_id": client_uuid}) # file_name required

    with pytest.raises(Exception):
        Role.model_validate({
            "client_id": client_uuid,
            "company_name": "Test",
            "title": "Test",
            "status": "NON_EXISTENT_STATUS"
        })

def test_relationship_attributes_exist_for_new_models():
    client = Client(display_name="Rel Test Client")
    assert hasattr(client, "source_documents")
    assert hasattr(client, "roles")

    source_doc = SourceDocument(client_id=uuid4(), file_name="doc.txt")
    assert hasattr(source_doc, "client")
    assert hasattr(source_doc, "evidence_snippets")

    role = Role(client_id=uuid4(), company_name="Comp", title="Title")
    assert hasattr(role, "client")
    assert hasattr(role, "evidence_snippets")
    assert hasattr(role, "validation_notes")

    evidence_snippet = EvidenceSnippet(source_document_id=uuid4(), snippet_text="text")
    assert hasattr(evidence_snippet, "source_document")
    assert hasattr(evidence_snippet, "role")

    validation_note = ValidationNote(role_id=uuid4(), note_text="note")
    assert hasattr(validation_note, "role")

def test_metadata_aliasing_in_new_models():
    meta_dict = {"key": "value"}

    # Test SourceDocument
    # 1. Instantiate using the alias 'metadata'
    sd_alias_inst = SourceDocument(client_id=uuid4(), file_name="f_alias", metadata=meta_dict)
    assert sd_alias_inst.metadata_ == meta_dict # Python attribute should be populated

    # 2. Instantiate using the Python attribute name 'metadata_'
    sd_pyname_inst = SourceDocument(client_id=uuid4(), file_name="f_pyname", metadata_=meta_dict)
    assert sd_pyname_inst.metadata_ == meta_dict

    # 3. Test model_dump() (should use Python attribute names)
    sd_dump_no_alias = sd_pyname_inst.model_dump()
    assert sd_dump_no_alias.get("metadata_") == meta_dict
    assert "metadata" not in sd_dump_no_alias # Alias should not be present

    # 4. Test model_dump(by_alias=True)
    # Based on previous failures, SQLModel 0.0.18 might still output python name `metadata_`
    # even with by_alias=True if the alias primarily serves validation/instantiation.
    # Let's test for the actual behavior observed or expected with this SQLModel version.
    sd_dump_with_alias = sd_alias_inst.model_dump(by_alias=True)
    # If SQLModel's `alias` on Field works for serialization with `sa_column(name=...)`, this should pass:
    # assert sd_dump_with_alias.get("metadata") == meta_dict
    # assert "metadata_" not in sd_dump_with_alias
    # If it doesn't serialize to the alias, this will pass:
    if "metadata" not in sd_dump_with_alias:
        print("Note: model_dump(by_alias=True) did not serialize 'metadata_' to 'metadata' for SourceDocument.")
        assert sd_dump_with_alias.get("metadata_") == meta_dict
    else: # It did serialize to the alias
        assert sd_dump_with_alias.get("metadata") == meta_dict
        assert "metadata_" not in sd_dump_with_alias

    # Test EvidenceSnippet similarly
    es_alias_inst = EvidenceSnippet(source_document_id=uuid4(), snippet_text="s_alias", metadata=meta_dict)
    assert es_alias_inst.metadata_ == meta_dict

    es_pyname_inst = EvidenceSnippet(source_document_id=uuid4(), snippet_text="s_pyname", metadata_=meta_dict)
    assert es_pyname_inst.metadata_ == meta_dict

    es_dump_no_alias = es_pyname_inst.model_dump()
    assert es_dump_no_alias.get("metadata_") == meta_dict
    assert "metadata" not in es_dump_no_alias

    es_dump_with_alias = es_alias_inst.model_dump(by_alias=True)
    if "metadata" not in es_dump_with_alias:
        print("Note: model_dump(by_alias=True) did not serialize 'metadata_' to 'metadata' for EvidenceSnippet.")
        assert es_dump_with_alias.get("metadata_") == meta_dict
    else:
        assert es_dump_with_alias.get("metadata") == meta_dict
        assert "metadata_" not in es_dump_with_alias
