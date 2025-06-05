import pytest
import hashlib # For checksum verification in test
import json # For JSONL parsing in test
from uuid import uuid4
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from backend.main import app # Assuming your FastAPI app is named 'app' in main.py
from backend.models import Client, Role, RoleStatus, ExportAudit # For test data creation
from backend.services import export as export_service # To mock its functions

# Fixture for TestClient
@pytest.fixture(name="client")
def client_fixture():
    return TestClient(app)

# Common test data
TEST_CLIENT_ID = uuid4()
TEST_CLIENT_DISPLAY_NAME = "TestClientExport"

@patch('backend.main.get_session') # Mock the get_session dependency
@patch('backend.main.export_service') # Mock the entire export_service module used in main.py
def test_export_client_data_success(mock_export_service, mock_get_session, client):
    mock_db = MagicMock()
    mock_get_session.return_value.__enter__.return_value = mock_db # Adjusted for context manager

    # Mock client fetched by db.get
    mock_client_instance = Client(id=TEST_CLIENT_ID, display_name=TEST_CLIENT_DISPLAY_NAME)
    mock_db.get.return_value = mock_client_instance

    # Mock service function return values
    roles_data = [
        Role(id=uuid4(), client_id=TEST_CLIENT_ID, company_name="C1", title="T1", input_text_compact="input1", output_text="output1", status=RoleStatus.VALIDATED),
        Role(id=uuid4(), client_id=TEST_CLIENT_ID, company_name="C2", title="T2", input_text_compact="input2", output_text="output2", status=RoleStatus.VALIDATED)
    ]
    # Use the real functions from the actual service to generate expected values,
    # as the service itself is mocked in the API test.
    jsonl_content = format_roles_to_jsonl_real(roles_data)
    checksum_val = calculate_checksum_real(jsonl_content)

    mock_export_service.get_validated_roles_for_client.return_value = roles_data
    mock_export_service.format_roles_to_jsonl.return_value = jsonl_content
    mock_export_service.calculate_checksum.return_value = checksum_val
    mock_export_service.create_export_audit_record.return_value = ExportAudit(
        id=uuid4(), client_id=TEST_CLIENT_ID, row_count=len(roles_data), filename="dummy.jsonl", checksum=checksum_val
    )

    response = client.get(f"/api/export/{TEST_CLIENT_ID}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/jsonl"
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert f"dataset-{mock_client_instance.display_name.replace(' ', '_')}-{TEST_CLIENT_ID}-" in response.headers["content-disposition"]
    assert response.headers["x-row-count"] == str(len(roles_data))
    assert response.headers["x-checksum"] == checksum_val
    assert f"dataset-{mock_client_instance.display_name.replace(' ', '_')}-{TEST_CLIENT_ID}-" in response.headers["x-filename"]

    response_content = response.content.decode('utf-8')
    lines = response_content.strip().split('\n')
    assert len(lines) == len(roles_data)
    assert json.loads(lines[0])["input_text_compact"] == "input1"

    mock_export_service.get_validated_roles_for_client.assert_called_once_with(client_id=TEST_CLIENT_ID, db=mock_db)
    mock_export_service.create_export_audit_record.assert_called_once()


@patch('backend.main.get_session')
@patch('backend.main.export_service')
def test_export_client_data_no_validated_roles(mock_export_service, mock_get_session, client):
    mock_db = MagicMock()
    mock_get_session.return_value.__enter__.return_value = mock_db # Adjusted

    mock_client_instance = Client(id=TEST_CLIENT_ID, display_name=TEST_CLIENT_DISPLAY_NAME)
    mock_db.get.return_value = mock_client_instance

    mock_export_service.get_validated_roles_for_client.return_value = []

    response = client.get(f"/api/export/{TEST_CLIENT_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "No validated roles found for this client to export."
    mock_export_service.create_export_audit_record.assert_not_called()


@patch('backend.main.get_session')
@patch('backend.main.export_service')
def test_export_client_data_client_not_found(mock_export_service, mock_get_session, client):
    mock_db = MagicMock()
    mock_get_session.return_value.__enter__.return_value = mock_db # Adjusted
    mock_db.get.return_value = None

    response = client.get(f"/api/export/{TEST_CLIENT_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Client not found"
    mock_export_service.get_validated_roles_for_client.assert_not_called()

# Helper functions to use actual service logic for expected values if needed
# This is because the service itself is mocked.
from backend.services.export import format_roles_to_jsonl as format_roles_to_jsonl_real
from backend.services.export import calculate_checksum as calculate_checksum_real
