import pytest
import uuid
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock

from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from backend.main import app, get_db_session
from backend.models import Client
from backend.schemas import IngestResponse

# --- Test Database Setup (similar to other API tests) ---
TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def test_engine():
    from backend import models as backend_models_fixture_import # Ensures all models are registered
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def db_session(test_engine):
    with Session(test_engine) as session:
        yield session

@pytest.fixture(scope="function")
def client(db_session: Session):
    def override_get_session_for_test():
        yield db_session
    app.dependency_overrides[get_db_session] = override_get_session_for_test
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db_session, None)

# --- Helper Functions ---
def create_test_client_for_ingest(db: Session, display_name: str = "Test Client For Ingest") -> Client:
    client_obj = Client(display_name=display_name)
    db.add(client_obj)
    db.commit()
    db.refresh(client_obj)
    return client_obj

# --- Test Cases for POST /api/ingest/{client_id} ---

@patch("backend.main.process_uploaded_files") # Patched where it's looked up
def test_ingest_files_success(mock_process_files: MagicMock, client: TestClient, db_session: Session):
    test_client_obj = create_test_client_for_ingest(db_session)
    client_id = test_client_obj.id

    # Mock the service function's return value
    mock_service_response = {
        "message": "Files processed successfully by mock.",
        "num_files_processed": 2
    }
    mock_process_files.return_value = mock_service_response

    # Create mock UploadFile objects
    # In a real test, these might point to actual temporary files for more integrated testing,
    # but for an API contract test with a mocked service, just the presence/names might be enough.
    mock_file1_content = b"dummy resume content"
    mock_file2_content = b"dummy source content"

    files_to_upload = [
        ("files", ("resume.pdf", mock_file1_content, "application/pdf")),
        ("files", ("source1.txt", mock_file2_content, "text/plain")),
    ]

    response = client.post(f"/api/ingest/{client_id}", files=files_to_upload)

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == mock_service_response["message"]
    assert data["num_files_processed"] == mock_service_response["num_files_processed"]

    # Assert that the mocked service was called correctly
    mock_process_files.assert_called_once()
    called_kwargs = mock_process_files.call_args.kwargs
    assert called_kwargs['client_id'] == client_id
    assert len(called_kwargs['files']) == 2

    # Check file names if important (UploadFile objects will be different instances)
    uploaded_file_names = sorted([f.filename for f in called_kwargs['files']])
    assert uploaded_file_names == ["resume.pdf", "source1.txt"]


def test_ingest_files_non_existent_client(client: TestClient):
    non_existent_client_id = uuid.uuid4()

    mock_file_content = b"dummy content"
    files_to_upload = [("files", ("test.pdf", mock_file_content, "application/pdf"))]

    response = client.post(f"/api/ingest/{non_existent_client_id}", files=files_to_upload)

    assert response.status_code == 404
    assert "Client not found" in response.json()["detail"]


@patch("backend.main.process_uploaded_files") # Patched where it's looked up
def test_ingest_no_files_sent(mock_process_files: MagicMock, client: TestClient, db_session: Session):
    # This test checks FastAPI's behavior for multipart forms where a File(...) field is empty.
    # FastAPI should return a 422 if `files: List[UploadFile] = File(...)` is required and none are sent.
    # However, if `File(...)` has a default or is `Optional`, behavior changes.
    # Current endpoint: `files: List[UploadFile] = File(...)` implies it's required.

    test_client_obj = create_test_client_for_ingest(db_session)
    client_id = test_client_obj.id

    # Sending an empty list for 'files' or no 'files' part at all
    # TestClient handles this by not including the 'files' part in the multipart request
    response = client.post(f"/api/ingest/{client_id}")

    # Depending on FastAPI version and exact setup, this might be 422 or 400
    # For `File(...)` it's usually 422 for missing file.
    # Our endpoint has an explicit check: `if not files: raise HTTPException(status_code=400...`
    # So we expect 400 from our custom check if FastAPI lets it through,
    # or 422 if FastAPI's own validation catches it first.
    # The custom check `if not files:` in the endpoint should lead to 400.
    # FastAPI's `File(...)` for a required parameter makes it return 422 if field is missing.

    assert response.status_code == 422
    # Detail message for 422 from FastAPI might be different, e.g., "Missing file" or "Field required"
    # For now, just checking status code is primary. If this fails, can inspect response.json()["detail"]
    mock_process_files.assert_not_called() # Service should not be called


@patch("backend.main.process_uploaded_files") # Patched where it's looked up
def test_ingest_one_file_success(mock_process_files: MagicMock, client: TestClient, db_session: Session):
    test_client_obj = create_test_client_for_ingest(db_session)
    client_id = test_client_obj.id

    mock_service_response = {"message": "One file processed", "num_files_processed": 1}
    mock_process_files.return_value = mock_service_response

    mock_file_content = b"single file content"
    files_to_upload = [("files", ("document.docx", mock_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))]

    response = client.post(f"/api/ingest/{client_id}", files=files_to_upload)

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "One file processed"
    assert data["num_files_processed"] == 1

    mock_process_files.assert_called_once()
    called_kwargs = mock_process_files.call_args.kwargs
    assert called_kwargs['client_id'] == client_id
    assert len(called_kwargs['files']) == 1
    assert called_kwargs['files'][0].filename == "document.docx"
