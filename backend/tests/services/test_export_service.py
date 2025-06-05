import pytest
import hashlib
import json
from uuid import uuid4
from datetime import datetime, timezone

from sqlmodel import Session, create_engine
from sqlalchemy.pool import StaticPool # For in-memory SQLite
from backend.models import Client, Role, RoleStatus, ExportAudit # Assuming models are accessible
from backend.services.export import ( # Direct import of functions
    get_validated_roles_for_client,
    format_roles_to_jsonl,
    calculate_checksum,
    create_export_audit_record,
)

# Test database setup (in-memory SQLite)
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}, # Necessary for SQLite in-memory
        poolclass=StaticPool,
    )
    # SQLModel.metadata.create_all(engine) # This would create all tables, usually handled by migrations in real DB
    # For unit tests, we might need to create tables directly if not using a full test DB setup
    # However, these service tests primarily mock DB interactions or test pure functions.
    # Let's assume for get_validated_roles_for_client and create_export_audit_record,
    # we will mock the session's exec, add, commit, refresh methods.
    # For this subtask, we'll focus on the service logic, mocking DB interactions.
    # A full integration test with a real test DB would be separate.

    # For tests that need a session but don't hit DB heavily (or are mocked):
    with Session(engine) as session:
        # We need to create tables for ExportAudit if we are to test create_export_audit_record properly
        # For simplicity in this subtask, we'll assume the table exists or mock interactions.
        # A better setup would use a test DB fixture that sets up schema.
        # Let's mock the DB session for now to simplify the subtask.
        yield session # This session is not fully configured with tables.

@pytest.fixture
def mock_db_session(mocker):
    session = mocker.MagicMock(spec=Session)

    # Mock for get_validated_roles_for_client
    mock_exec = mocker.MagicMock()
    session.exec.return_value = mock_exec

    # Mock for create_export_audit_record
    # session.add = mocker.MagicMock() # Not needed if we return the object directly after creation
    # session.commit = mocker.MagicMock()
    # session.refresh = mocker.MagicMock()
    return session, mock_exec


def test_get_validated_roles_for_client(mock_db_session):
    session, mock_exec_result = mock_db_session
    client_id = uuid4()

    role1 = Role(id=uuid4(), client_id=client_id, company_name="Test Co", title="Dev", output_text="Role 1 output", status=RoleStatus.VALIDATED, input_text_compact="input1")
    role2 = Role(id=uuid4(), client_id=client_id, company_name="Test Co", title="QA", output_text="Role 2 output", status=RoleStatus.PARSED, input_text_compact="input2")

    # Configure the mock to return these roles when .all() is called
    mock_exec_result.all.return_value = [role1] # Only validated roles

    roles = get_validated_roles_for_client(client_id, session)

    assert len(roles) == 1
    assert roles[0].status == RoleStatus.VALIDATED
    assert roles[0].output_text == "Role 1 output"
    # Check that the select statement was constructed correctly (simplified check)
    session.exec.assert_called_once()
    call_args = session.exec.call_args[0][0] # Get the statement object
    assert str(call_args.whereclause).count("roles.client_id =") == 1 # Basic check
    assert str(call_args.whereclause).count("roles.status =") == 1


def test_format_roles_to_jsonl():
    role1 = Role(id=uuid4(), client_id=uuid4(), company_name="Comp1", title="Title1", output_text="Output1", input_text_compact="Input1", status=RoleStatus.VALIDATED)
    role2 = Role(id=uuid4(), client_id=uuid4(), company_name="Comp2", title="Title2", output_text="Output2", input_text_compact="Input2", status=RoleStatus.VALIDATED)
    roles = [role1, role2]

    expected_line1 = json.dumps({"input_text_compact": "Input1", "output_text": "Output1"}, sort_keys=True)
    expected_line2 = json.dumps({"input_text_compact": "Input2", "output_text": "Output2"}, sort_keys=True)
    expected_jsonl = f"{expected_line1}\n{expected_line2}"

    jsonl_output = format_roles_to_jsonl(roles)

    assert jsonl_output == expected_jsonl

def test_calculate_checksum():
    data = "Hello, World!"
    expected_checksum = hashlib.sha256(data.encode('utf-8')).hexdigest()
    checksum = calculate_checksum(data)
    assert checksum == expected_checksum

def test_create_export_audit_record(mock_db_session):
    session, _ = mock_db_session
    client_id = uuid4()
    row_count = 10
    filename = "test_export.jsonl"
    checksum = "test_checksum"

    # To properly test this, we need to see if db.add, db.commit, db.refresh are called.
    # The function currently returns the created object.
    # We can check if the returned object has the correct attributes.

    # Configure the mock session's add, commit, refresh methods
    # session.add = mocker.MagicMock() # Already part of MagicMock spec
    # session.commit = mocker.MagicMock()
    # session.refresh = mocker.MagicMock(side_effect=lambda x: x) # Make refresh do nothing to the passed object

    audit_record = create_export_audit_record(session, client_id, row_count, filename, checksum)

    session.add.assert_called_once_with(audit_record)
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(audit_record)

    assert audit_record.client_id == client_id
    assert audit_record.row_count == row_count
    assert audit_record.filename == filename
    assert audit_record.checksum == checksum
    assert audit_record.exported_at is not None # Should be set by default_factory
