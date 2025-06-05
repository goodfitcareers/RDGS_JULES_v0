import uuid
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from backend.dependencies import get_db_session
from backend.main import app
from backend.services.notion import NotionWebhookPayload, NotionPageInfo, NotionServiceError

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def test_engine_notion():
    # Using a session-scoped engine means all tests in a session share this engine.
    # Tables are created once per session and dropped once per session.
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False}, # Necessary for SQLite in-memory for TestClient
        poolclass=StaticPool, # Disables connection pooling, each connection is unique
        echo=False # Set to True to see SQL queries
    )
    SQLModel.metadata.create_all(engine) # Create tables based on SQLModel metadata
    yield engine
    SQLModel.metadata.drop_all(engine) # Drop tables after tests are done

@pytest.fixture(scope="function")
def db_session_notion(test_engine_notion):
    # This fixture provides a fresh transaction for each test function.
    # It ensures tests are isolated from each other database-wise.
    with Session(test_engine_notion) as session:
        yield session
        # No commit/rollback needed here typically, as TestClient runs in a transaction
        # or the test itself should manage data if it's not read-only.
        # For these tests, no actual DB interaction that needs cleanup per test occurs in the router itself.

@pytest.fixture(scope="function")
def test_client_notion(db_session_notion: Session):
    # This fixture sets up the FastAPI TestClient with overridden dependencies.
    # Specifically, it overrides `get_db_session` to use the test database session.

    def override_get_session_for_test():
        yield db_session_notion

    # Apply the override
    app.dependency_overrides[get_db_session] = override_get_session_for_test

    with TestClient(app) as c:
        yield c

    # Clean up the override after the test client is done
    app.dependency_overrides.pop(get_db_session, None)

def test_handle_notion_webhook_success(test_client_notion: TestClient):
    """Test successful processing of a Notion webhook."""
    client_id = uuid.uuid4()
    payload_dict = {"type": "page.updated", "item_ids": ["item_id_1"], "user_id": "user_test_123"}

    # Expected data that NotionService.process_webhook_event would return
    mock_processed_page_info = NotionPageInfo(id="item_id_1", title="Processed Page Title 1")

    # The response from the API should be a list of these Pydantic models, serialized to JSON
    expected_api_response_json = [mock_processed_page_info.model_dump()]

    # Patch the NotionService within the scope of the API router
    with patch("backend.api.notion_router.NotionService") as MockNotionService:
        # Configure the mock instance that will be created when NotionService() is called
        mock_service_instance = MockNotionService.return_value
        # Set the mock for the async method `process_webhook_event`
        mock_service_instance.process_webhook_event = AsyncMock(return_value=[mock_processed_page_info])

        # Make the API call
        response = test_client_notion.post(
            f"/api/v1/notion/webhook/{client_id}", # Ensure client_id is correctly formatted in URL
            json=payload_dict,
            headers={"X-Notion-API-Token": "fake_notion_token"}
        )

        # Assertions
        assert response.status_code == 200
        assert response.json() == expected_api_response_json

        # Verify NotionService was instantiated correctly
        MockNotionService.assert_called_once_with(notion_api_token="fake_notion_token", client_id=client_id)

        # Verify process_webhook_event was called correctly
        mock_service_instance.process_webhook_event.assert_called_once()

        # Check the argument passed to process_webhook_event
        actual_payload_arg = mock_service_instance.process_webhook_event.call_args[0][0]
        assert isinstance(actual_payload_arg, NotionWebhookPayload)
        assert actual_payload_arg.type == payload_dict["type"]
        assert actual_payload_arg.item_ids == payload_dict["item_ids"]
        assert actual_payload_arg.user_id == payload_dict["user_id"]

def test_handle_notion_webhook_missing_token(test_client_notion: TestClient):
    """Test webhook call when X-Notion-API-Token header is missing."""
    client_id = uuid.uuid4()
    payload_dict = {"type": "page.updated", "item_ids": ["item_id_2"], "user_id": "user_test_456"}

    response = test_client_notion.post(
        f"/api/v1/notion/webhook/{client_id}",
        json=payload_dict
        # No X-Notion-API-Token header
    )

    assert response.status_code == 401 # Based on HTTPException(status_code=401, ...) in router
    json_response = response.json()
    assert "detail" in json_response
    assert "Notion API token not provided" in json_response["detail"]

def test_handle_notion_webhook_service_error(test_client_notion: TestClient):
    """Test webhook call when NotionService raises a NotionServiceError."""
    client_id = uuid.uuid4()
    payload_dict = {"type": "page.updated", "item_ids": ["item_id_3"], "user_id": "user_test_789"}

    with patch("backend.api.notion_router.NotionService") as MockNotionService:
        mock_service_instance = MockNotionService.return_value
        # Configure the mock to raise NotionServiceError
        mock_service_instance.process_webhook_event = AsyncMock(
            side_effect=NotionServiceError("Simulated failure to process event")
        )

        response = test_client_notion.post(
            f"/api/v1/notion/webhook/{client_id}",
            json=payload_dict,
            headers={"X-Notion-API-Token": "fake_notion_token"}
        )

        assert response.status_code == 500 # Based on HTTPException(status_code=500, ...)
        json_response = response.json()
        assert "detail" in json_response
        assert "Error processing Notion data: Simulated failure to process event" in json_response["detail"]

        MockNotionService.assert_called_once_with(notion_api_token="fake_notion_token", client_id=client_id)
        mock_service_instance.process_webhook_event.assert_called_once()

def test_handle_notion_webhook_empty_processed_items(test_client_notion: TestClient):
    """Test webhook call when NotionService processes successfully but returns an empty list."""
    client_id = uuid.uuid4()
    # Payload has item_ids, so we expect processing, but service returns empty list
    payload_dict = {"type": "page.updated", "item_ids": ["item_id_4", "item_id_5"], "user_id": "user_test_000"}

    with patch("backend.api.notion_router.NotionService") as MockNotionService:
        mock_service_instance = MockNotionService.return_value
        # Configure process_webhook_event to return an empty list
        mock_service_instance.process_webhook_event = AsyncMock(return_value=[])

        response = test_client_notion.post(
            f"/api/v1/notion/webhook/{client_id}",
            json=payload_dict,
            headers={"X-Notion-API-Token": "fake_notion_token"}
        )

        assert response.status_code == 200
        assert response.json() == [] # Expect an empty list in the JSON response

        MockNotionService.assert_called_once_with(notion_api_token="fake_notion_token", client_id=client_id)
        mock_service_instance.process_webhook_event.assert_called_once()

        actual_payload_arg = mock_service_instance.process_webhook_event.call_args[0][0]
        assert isinstance(actual_payload_arg, NotionWebhookPayload)
        assert actual_payload_arg.item_ids == payload_dict["item_ids"]

def test_handle_notion_webhook_no_item_ids_in_payload(test_client_notion: TestClient):
    """Test webhook call with a payload that has an empty item_ids list."""
    client_id = uuid.uuid4()
    payload_dict = {"type": "page.updated", "item_ids": [], "user_id": "user_test_empty_items"}

    with patch("backend.api.notion_router.NotionService") as MockNotionService:
        mock_service_instance = MockNotionService.return_value
        mock_service_instance.process_webhook_event = AsyncMock(return_value=[]) # Should still return empty list

        response = test_client_notion.post(
            f"/api/v1/notion/webhook/{client_id}",
            json=payload_dict,
            headers={"X-Notion-API-Token": "fake_notion_token"}
        )

        assert response.status_code == 200
        assert response.json() == []

        MockNotionService.assert_called_once_with(notion_api_token="fake_notion_token", client_id=client_id)
        # The service's process_webhook_event is still called, and it's up to the service
        # to decide how to handle an empty item_ids list (current service logic processes it and returns empty).
        mock_service_instance.process_webhook_event.assert_called_once()
        actual_payload_arg = mock_service_instance.process_webhook_event.call_args[0][0]
        assert actual_payload_arg.item_ids == []
```
