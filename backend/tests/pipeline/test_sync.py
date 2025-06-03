# Tests for sync_roles_node and related functions in backend.pipeline
import pytest
import uuid
from datetime import date
from unittest.mock import patch, MagicMock, ANY # ANY is useful for verifying objects

from backend.pipeline import sync_roles_node, GraphState, parse_date_string # parse_date_string for test data prep
from backend.models import Role, RoleStatus # Assuming Role, RoleStatus are in backend.models
from sqlalchemy.exc import SQLAlchemyError

# Helper function to create initial GraphState
def get_initial_state(
    client_id: str | None = str(uuid.uuid4()), # Default to a valid UUID string
    roles_draft: list[dict] | None = None,
    error_message: str | None = None,
    current_node_error: str | None = None
) -> GraphState:
    return GraphState(
        client_id=client_id,
        roles_draft=roles_draft if roles_draft is not None else [],
        # Fill other GraphState fields with defaults if necessary for node execution
        resume_file_path="dummy.pdf",
        source_document_paths=[],
        source_document_texts=[],
        resume_text="dummy resume text",
        error_message=error_message,
        current_node_error=current_node_error
    )

@patch('backend.pipeline.Session') # Mocks sqlmodel.Session or sqlalchemy.orm.Session
@patch('backend.pipeline.create_engine') # To prevent actual engine creation
def test_sync_roles_successful(mock_create_engine, mock_session_class):
    """Test successful syncing of roles to the database."""
    mock_engine_instance = MagicMock()
    mock_create_engine.return_value = mock_engine_instance

    mock_session_instance = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session_instance # For "with Session(...) as session:"

    client_uuid = uuid.uuid4()
    roles_data = [
        {"company_name": "Tech Corp", "title": "Engineer", "start_date": "2022-01-01", "end_date": "2023-01-01", "description_points": ["Did stuff."]},
        {"company_name": "Innovate LLC", "title": "Lead Developer", "start_date": "Jul 2023", "end_date": "Present", "description_points": ["Led things."]},
    ]
    initial_state = get_initial_state(client_id=str(client_uuid), roles_draft=roles_data)

    output_state = sync_roles_node(initial_state)

    assert mock_session_instance.add.call_count == len(roles_data)

    # Verify details of objects passed to session.add
    call_args_list = mock_session_instance.add.call_args_list

    # First role
    added_role1 = call_args_list[0][0][0] # arg passed to first call to add()
    assert isinstance(added_role1, Role)
    assert added_role1.client_id == client_uuid
    assert added_role1.company_name == "Tech Corp"
    assert added_role1.title == "Engineer"
    assert added_role1.start_date == date(2022, 1, 1)
    assert added_role1.end_date == date(2023, 1, 1)
    assert added_role1.output_text == "Did stuff."
    assert added_role1.status == RoleStatus.PARSED

    # Second role
    added_role2 = call_args_list[1][0][0] # arg passed to second call to add()
    assert isinstance(added_role2, Role)
    assert added_role2.client_id == client_uuid
    assert added_role2.company_name == "Innovate LLC"
    assert added_role2.title == "Lead Developer"
    assert added_role2.start_date == date(2023, 7, 1)
    assert added_role2.end_date is None # "Present"
    assert added_role2.output_text == "Led things."
    assert added_role2.status == RoleStatus.PARSED

    mock_session_instance.commit.assert_called_once()
    assert output_state['current_node_error'] is None
    assert output_state.get('synced_roles_count', 0) == len(roles_data) # Check if this key is returned

@patch('backend.pipeline.Session')
@patch('backend.pipeline.create_engine')
def test_sync_roles_missing_client_id(mock_create_engine, mock_session_class):
    initial_state = get_initial_state(client_id=None, roles_draft=[{"company_name": "Test"}])
    output_state = sync_roles_node(initial_state)
    assert "Client ID is missing" in output_state['current_node_error']
    mock_session_class.return_value.__enter__.return_value.add.assert_not_called()

@patch('backend.pipeline.Session')
@patch('backend.pipeline.create_engine')
def test_sync_roles_invalid_client_id_format(mock_create_engine, mock_session_class):
    initial_state = get_initial_state(client_id="not-a-uuid", roles_draft=[{"company_name": "Test"}])
    output_state = sync_roles_node(initial_state)
    assert "Invalid client_id format" in output_state['current_node_error']
    mock_session_class.return_value.__enter__.return_value.add.assert_not_called()

@patch('backend.pipeline.Session')
@patch('backend.pipeline.create_engine')
def test_sync_roles_missing_roles_draft_none(mock_create_engine, mock_session_class):
    initial_state = get_initial_state(roles_draft=None)
    output_state = sync_roles_node(initial_state)
    assert output_state['current_node_error'] is None
    assert output_state.get('synced_roles_count', -1) == 0 # Check for explicit 0 count
    mock_session_class.return_value.__enter__.return_value.add.assert_not_called()

@patch('backend.pipeline.Session')
@patch('backend.pipeline.create_engine')
def test_sync_roles_missing_roles_draft_empty_list(mock_create_engine, mock_session_class):
    initial_state = get_initial_state(roles_draft=[])
    output_state = sync_roles_node(initial_state)
    assert output_state['current_node_error'] is None
    assert output_state.get('synced_roles_count', -1) == 0
    mock_session_class.return_value.__enter__.return_value.add.assert_not_called()

@patch('backend.pipeline.Session')
@patch('backend.pipeline.create_engine')
def test_sync_roles_role_data_missing_required_fields(mock_create_engine, mock_session_class):
    mock_session_instance = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session_instance

    roles_data = [
        {"title": "Missing company"}, # Missing company_name
        {"company_name": "Valid Inc.", "title": "Good Role"}
    ]
    initial_state = get_initial_state(roles_draft=roles_data)
    output_state = sync_roles_node(initial_state)

    # Only the valid role should be added
    mock_session_instance.add.assert_called_once()
    added_role = mock_session_instance.add.call_args[0][0]
    assert added_role.company_name == "Valid Inc."
    mock_session_instance.commit.assert_called_once()
    assert output_state['current_node_error'] is None
    # The node currently just prints a skip message, doesn't set an error for this.

@patch('backend.pipeline.Session')
@patch('backend.pipeline.create_engine')
def test_sync_roles_db_commit_error(mock_create_engine, mock_session_class):
    mock_session_instance = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session_instance
    mock_session_instance.commit.side_effect = SQLAlchemyError("Commit failed")

    roles_data = [{"company_name": "TestCo", "title": "Tester", "start_date": "2023-01-01"}]
    initial_state = get_initial_state(roles_draft=roles_data)
    output_state = sync_roles_node(initial_state)

    assert "Database error while syncing roles" in output_state['current_node_error']
    assert "Commit failed" in output_state['current_node_error']
    # `with Session(...)` handles rollback on exception automatically.

@patch('backend.pipeline.Session')
@patch('backend.pipeline.create_engine')
def test_sync_roles_db_add_error(mock_create_engine, mock_session_class):
    """Test a scenario where session.add() itself might raise an error."""
    mock_session_instance = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session_instance
    # Simulate error on the first add, then proceed normally for any subsequent ones (if any)
    mock_session_instance.add.side_effect = [SQLAlchemyError("Add failed"), None]

    roles_data = [
        {"company_name": "FailCo", "title": "Bad Role"},
        {"company_name": "GoodCo", "title": "Good Role"} # This won't be added if loop breaks
    ]
    initial_state = get_initial_state(roles_draft=roles_data)
    output_state = sync_roles_node(initial_state)

    # The current loop in sync_roles_node is inside the try block.
    # So, an error on .add() for the first role will propagate to the except SQLAlchemyError.
    assert "Database error while syncing roles" in output_state['current_node_error']
    assert "Add failed" in output_state['current_node_error']
    mock_session_instance.commit.assert_not_called() # Commit should not be reached if add fails

@patch('backend.pipeline.Session')
@patch('backend.pipeline.create_engine')
def test_sync_roles_with_pre_existing_error(mock_create_engine, mock_session_class):
    initial_state = get_initial_state(
        roles_draft=[{"company_name": "Test"}],
        error_message="Previous error from another node",
        current_node_error=None # This node hasn't run yet or failed in a way that set its own current_node_error
    )
    output_state = sync_roles_node(initial_state)

    # Node should skip execution due to pre-existing error_message
    assert "Skipping Sync Roles Node due to pre-existing critical errors" # Check log output (requires caplog)
    mock_session_class.return_value.__enter__.return_value.add.assert_not_called()
    mock_session_class.return_value.__enter__.return_value.commit.assert_not_called()
    assert output_state['current_node_error'] is None # This node itself did not produce an error
    assert output_state['error_message'] == "Previous error from another node" # Original error preserved

@patch('backend.pipeline.Session')
@patch('backend.pipeline.create_engine')
def test_sync_roles_date_parsing_integration(mock_create_engine, mock_session_class):
    mock_session_instance = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session_instance
    client_uuid_str = str(uuid.uuid4())

    roles_data = [
        {"company_name": "DateTestCo", "title": "Time Lord", "start_date": "2022-07-15", "end_date": "Jul 2023", "description_points": []},
        {"company_name": "DateTestCo", "title": "Historian", "start_date": "2021", "end_date": "Present", "description_points": []},
        {"company_name": "DateTestCo", "title": "Futurist", "start_date": "Invalid Date", "end_date": "2025-13-01", "description_points": []}, # Invalid dates
    ]
    initial_state = get_initial_state(client_id=client_uuid_str, roles_draft=roles_data)
    sync_roles_node(initial_state)

    assert mock_session_instance.add.call_count == len(roles_data)
    call_args_list = mock_session_instance.add.call_args_list

    # Role 1
    role1 = call_args_list[0][0][0]
    assert role1.start_date == date(2022, 7, 15)
    assert role1.end_date == date(2023, 7, 1)

    # Role 2
    role2 = call_args_list[1][0][0]
    assert role2.start_date == date(2021, 1, 1)
    assert role2.end_date is None # "Present"

    # Role 3 (invalid dates should parse to None)
    role3 = call_args_list[2][0][0]
    assert role3.start_date is None # "Invalid Date"
    assert role3.end_date is None # "2025-13-01" (invalid month)

    mock_session_instance.commit.assert_called_once()

# Considerations:
# - The test for pre-existing errors assumes that if `error_message` is set from a *previous* node,
#   `sync_roles_node` will skip. This matches the boilerplate skip logic in the provided nodes.
# - `RoleStatus` and `Role` model details (like default revision, created_at, updated_at) are assumed
#   to be handled by the model definitions themselves and not explicitly set in `sync_roles_node` unless required.
# - Test for `synced_roles_count` key in output state could be added if the node is meant to return it.
#   The current node logic doesn't explicitly return this, it's more of an internal variable.
#   If GraphState needs it, the node should return it. (Added a check for this in successful test)File 'backend/tests/pipeline/test_sync.py' overwritten successfully.
