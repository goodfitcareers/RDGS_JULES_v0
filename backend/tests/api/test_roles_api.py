import pytest
import uuid
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from backend.main import app, get_db_session # app for TestClient, get_db_session for override
from backend.models import Client, Role, RoleStatus # Models needed for setup and type hints
from backend.schemas import RoleRead, RoleStatusUpdate, RoleCreate, RoleUpdate # Schemas for request/response

# --- Test Database Setup ---
TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def test_engine():
    """
    Creates an in-memory SQLite engine for testing using StaticPool.
    Ensures all tables are created before tests run and dropped afterwards.
    """
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
    """Fixture to provide a test database session using the test_engine."""
    with Session(test_engine) as session:
        yield session

@pytest.fixture(scope="function")
def client(db_session: Session):
    """Fixture to provide a TestClient, overriding the DB session."""
    def override_get_session_for_test():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_session_for_test
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db_session, None)

# --- Helper Functions ---

def create_test_client(db: Session, display_name: str = "Test Client Inc.") -> Client:
    client_obj = Client(display_name=display_name)
    db.add(client_obj)
    db.commit()
    db.refresh(client_obj)
    return client_obj

def create_test_role(
    db: Session,
    client_id: uuid.UUID,
    company_name: str = "Test Company",
    title: str = "Test Role",
    output_text: str = "Initial role description.",
    status: RoleStatus = RoleStatus.PARSED,
    revision: int = 0
) -> Role:
    role_obj = Role(
        client_id=client_id,
        company_name=company_name,
        title=title,
        output_text=output_text,
        status=status,
        revision=revision
    )
    db.add(role_obj)
    db.commit()
    db.refresh(role_obj)
    return role_obj

# --- Test Cases for POST /api/roles/{role_id}/status ---

def test_update_role_status_success(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, status=RoleStatus.PARSED, revision=0)

    payload = RoleStatusUpdate(status=RoleStatus.ROLES_VERIFIED, revision=0)
    response = client.post(f"/api/roles/{test_role.id}/status", json=payload.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == RoleStatus.ROLES_VERIFIED.value
    assert data["revision"] == 1
    assert uuid.UUID(data["id"]) == test_role.id

    # Verify in DB
    db_session.refresh(test_role)
    assert test_role.status == RoleStatus.ROLES_VERIFIED
    assert test_role.revision == 1
    assert test_role.updated_at is not None

def test_update_role_status_invalid_transition(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, status=RoleStatus.PARSED, revision=0)

    payload = RoleStatusUpdate(status=RoleStatus.INPUT_SYNTHESIZED, revision=0) # Invalid: Parsed -> InputSynthesized
    response = client.post(f"/api/roles/{test_role.id}/status", json=payload.model_dump())

    assert response.status_code == 400
    assert "Invalid status transition" in response.json()["detail"]

def test_update_role_status_incorrect_revision(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, status=RoleStatus.PARSED, revision=1) # Current revision is 1

    payload = RoleStatusUpdate(status=RoleStatus.ROLES_VERIFIED, revision=0) # Trying to update with old revision 0
    response = client.post(f"/api/roles/{test_role.id}/status", json=payload.model_dump())

    assert response.status_code == 409 # Conflict
    assert "Revision number mismatch" in response.json()["detail"]

def test_update_role_status_non_existent_role(client: TestClient):
    non_existent_role_id = uuid.uuid4()
    payload = RoleStatusUpdate(status=RoleStatus.ROLES_VERIFIED, revision=0)
    response = client.post(f"/api/roles/{non_existent_role_id}/status", json=payload.model_dump())

    assert response.status_code == 404

def test_update_role_status_invalid_enum_value(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, status=RoleStatus.PARSED, revision=0)

    # Pydantic should catch this before our endpoint logic if using the enum in the model
    # The request body itself would be invalid.
    invalid_payload_json = {"status": "InvalidStatusValue", "revision": 0}
    response = client.post(f"/api/roles/{test_role.id}/status", json=invalid_payload_json)

    assert response.status_code == 422 # Unprocessable Entity

# --- Test Cases for Role CRUD Endpoints ---

# POST /api/clients/{client_id}/roles/
def test_create_role_for_client_success(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    role_create_data = {
        "company_name": "New Corp",
        "title": "Software Engineer",
        "output_text": "Developed amazing things."
    }
    response = client.post(f"/api/clients/{test_client_obj.id}/roles/", json=role_create_data) # Added trailing slash

    assert response.status_code == 201
    data = response.json()
    assert data["company_name"] == "New Corp"
    assert data["title"] == "Software Engineer"
    assert data["status"] == RoleStatus.PARSED.value
    assert data["revision"] == 0
    assert data["client_id"] == str(test_client_obj.id)
    assert "id" in data

    # Verify in DB
    db_role = db_session.get(Role, uuid.UUID(data["id"]))
    assert db_role is not None
    assert db_role.company_name == "New Corp"

def test_create_role_for_non_existent_client(client: TestClient):
    non_existent_client_id = uuid.uuid4()
    role_create_data = {"company_name": "No Client Corp", "title": "Ghost Role", "output_text": "..."}
    response = client.post(f"/api/clients/{non_existent_client_id}/roles/", json=role_create_data) # Added trailing slash
    assert response.status_code == 404

def test_create_role_invalid_data(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    # Missing required fields like company_name, title, output_text
    invalid_role_data = {}
    response = client.post(f"/api/clients/{test_client_obj.id}/roles/", json=invalid_role_data) # Added trailing slash
    assert response.status_code == 422

# GET /api/clients/{client_id}/roles/
def test_list_roles_for_client(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session, display_name="Client With Roles")
    role1 = create_test_role(db_session, client_id=test_client_obj.id, title="Role 1")
    role2 = create_test_role(db_session, client_id=test_client_obj.id, title="Role 2")

    response = client.get(f"/api/clients/{test_client_obj.id}/roles/") # Added trailing slash
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {role["title"] for role in data} == {"Role 1", "Role 2"}

def test_list_roles_for_client_empty(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session, display_name="Client Without Roles")
    response = client.get(f"/api/clients/{test_client_obj.id}/roles/") # Added trailing slash
    assert response.status_code == 200
    assert response.json() == []

def test_list_roles_for_client_pagination(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    for i in range(5):
        create_test_role(db_session, client_id=test_client_obj.id, title=f"Role {i}")

    response_limit_2 = client.get(f"/api/clients/{test_client_obj.id}/roles/?limit=2") # Added trailing slash
    assert len(response_limit_2.json()) == 2

    response_skip_2_limit_2 = client.get(f"/api/clients/{test_client_obj.id}/roles/?skip=2&limit=2") # Added trailing slash
    data_skip_limit = response_skip_2_limit_2.json()
    assert len(data_skip_limit) == 2
    assert data_skip_limit[0]["title"] == "Role 2"

def test_list_roles_for_non_existent_client(client: TestClient):
    non_existent_client_id = uuid.uuid4()
    response = client.get(f"/api/clients/{non_existent_client_id}/roles/") # Added trailing slash
    assert response.status_code == 404

# GET /api/roles/{role_id}
def test_get_role_by_id_success(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, title="Specific Role")

    response = client.get(f"/api/roles/{test_role.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Specific Role"
    assert uuid.UUID(data["id"]) == test_role.id

def test_get_role_by_id_non_existent(client: TestClient):
    non_existent_role_id = uuid.uuid4()
    response = client.get(f"/api/roles/{non_existent_role_id}")
    assert response.status_code == 404

# PUT /api/roles/{role_id}
def test_update_role_success(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, title="Old Title", revision=0)

    update_data = RoleUpdate(title="New Title", output_text="Updated text", revision=0)
    response = client.put(f"/api/roles/{test_role.id}", json=update_data.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Title"
    assert data["output_text"] == "Updated text"
    assert data["revision"] == 1

    db_session.refresh(test_role)
    assert test_role.title == "New Title"
    assert test_role.revision == 1

def test_update_role_incorrect_revision(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, title="Original Title", revision=1)

    update_data = RoleUpdate(title="Attempted Update", revision=0) # Incorrect revision
    response = client.put(f"/api/roles/{test_role.id}", json=update_data.model_dump())
    assert response.status_code == 409

def test_update_role_non_existent(client: TestClient):
    non_existent_role_id = uuid.uuid4()
    update_data = RoleUpdate(title="Non Existent", revision=0)
    response = client.put(f"/api/roles/{non_existent_role_id}", json=update_data.model_dump())
    assert response.status_code == 404

def test_update_role_invalid_data(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, revision=0)

    # Example: missing revision, or invalid field value if RoleUpdate had stricter validation
    invalid_update_data = {"title": "Only Title"} # Missing revision
    response = client.put(f"/api/roles/{test_role.id}", json=invalid_update_data)
    assert response.status_code == 422 # Pydantic validation error for missing revision

# DELETE /api/roles/{role_id}
def test_delete_role_success(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id)

    response = client.delete(f"/api/roles/{test_role.id}")
    assert response.status_code == 204

    # Verify deleted from DB
    deleted_role = db_session.get(Role, test_role.id)
    assert deleted_role is None

def test_delete_role_non_existent(client: TestClient):
    non_existent_role_id = uuid.uuid4()
    response = client.delete(f"/api/roles/{non_existent_role_id}")
    assert response.status_code == 204 # Idempotent: already deleted

# --- Test Cases for POST /api/roles/{role_id}/validate ---

def test_validate_role_input_success(client: TestClient, db_session: Session):
    """Test successful validation and status change from InputCurated to Validated."""
    test_client_obj = create_test_client(db_session)
    # Create a role with the status InputCurated and an initial revision number
    test_role = create_test_role(
        db_session,
        client_id=test_client_obj.id,
        status=RoleStatus.INPUT_CURATED,
        revision=2  # Assuming it reached InputCurated with revision 2
    )
    initial_revision = test_role.revision # Store initial revision

    response = client.post(f"/api/roles/{test_role.id}/validate") # No request body

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == RoleStatus.VALIDATED.value
    assert data["revision"] == initial_revision + 1 # Verify against initial revision
    assert uuid.UUID(data["id"]) == test_role.id

    # Verify in DB
    db_session.refresh(test_role)
    assert test_role.status == RoleStatus.VALIDATED
    assert test_role.revision == data["revision"] # Ensure DB matches response revision
    assert test_role.updated_at is not None # Should be updated

def test_validate_role_input_invalid_status(client: TestClient, db_session: Session):
    """Test attempting to validate a role that is not in InputCurated status."""
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(
        db_session,
        client_id=test_client_obj.id,
        status=RoleStatus.PARSED, # Not InputCurated
        revision=0
    )

    response = client.post(f"/api/roles/{test_role.id}/validate")

    assert response.status_code == 400
    data = response.json()
    assert "Role status must be 'InputCurated' to be validated" in data["detail"]

def test_validate_role_input_non_existent_role(client: TestClient):
    """Test calling validate on a role_id that does not exist."""
    non_existent_role_id = uuid.uuid4()
    response = client.post(f"/api/roles/{non_existent_role_id}/validate")

    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Role not found"

def test_update_role_status_multiple_sequential_updates(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, status=RoleStatus.PARSED, revision=0)

    # 1. Parsed -> RolesVerified
    payload1 = RoleStatusUpdate(status=RoleStatus.ROLES_VERIFIED, revision=0)
    response1 = client.post(f"/api/roles/{test_role.id}/status", json=payload1.model_dump())
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == RoleStatus.ROLES_VERIFIED.value
    current_revision = data1["revision"] # Should be 1

    # 2. RolesVerified -> InputSynthesized
    payload2 = RoleStatusUpdate(status=RoleStatus.INPUT_SYNTHESIZED, revision=current_revision)
    response2 = client.post(f"/api/roles/{test_role.id}/status", json=payload2.model_dump())
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == RoleStatus.INPUT_SYNTHESIZED.value
    current_revision = data2["revision"] # Should be 2

    # 3. InputSynthesized -> InputCurated
    payload3 = RoleStatusUpdate(status=RoleStatus.INPUT_CURATED, revision=current_revision)
    response3 = client.post(f"/api/roles/{test_role.id}/status", json=payload3.model_dump())
    assert response3.status_code == 200
    data3 = response3.json()
    assert data3["status"] == RoleStatus.INPUT_CURATED.value
    current_revision = data3["revision"] # Should be 3

    # 4. InputCurated -> Validated
    payload4 = RoleStatusUpdate(status=RoleStatus.VALIDATED, revision=current_revision)
    response4 = client.post(f"/api/roles/{test_role.id}/status", json=payload4.model_dump())
    assert response4.status_code == 200
    data4 = response4.json()
    assert data4["status"] == RoleStatus.VALIDATED.value
    current_revision = data4["revision"] # Should be 4

    # 5. Validated -> Exported
    payload5 = RoleStatusUpdate(status=RoleStatus.EXPORTED, revision=current_revision)
    response5 = client.post(f"/api/roles/{test_role.id}/status", json=payload5.model_dump())
    assert response5.status_code == 200
    data5 = response5.json()
    assert data5["status"] == RoleStatus.EXPORTED.value
    current_revision = data5["revision"] # Should be 5

    # Verify in DB
    db_session.refresh(test_role)
    assert test_role.status == RoleStatus.EXPORTED
    assert test_role.revision == 5

def test_update_role_status_to_same_status_invalid(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, status=RoleStatus.PARSED, revision=0)

    payload = RoleStatusUpdate(status=RoleStatus.PARSED, revision=0) # Invalid: Parsed -> Parsed
    response = client.post(f"/api/roles/{test_role.id}/status", json=payload.model_dump())

    assert response.status_code == 400
    assert "Invalid status transition" in response.json()["detail"]

def test_update_role_status_from_exported_invalid(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, status=RoleStatus.EXPORTED, revision=5)

    payload = RoleStatusUpdate(status=RoleStatus.PARSED, revision=5) # Invalid: Exported -> Parsed
    response = client.post(f"/api/roles/{test_role.id}/status", json=payload.model_dump())

    assert response.status_code == 400 # Should be invalid transition
    assert "Invalid status transition" in response.json()["detail"]
    assert "Allowed next statuses: []" in response.json()["detail"]

def test_update_role_status_missing_revision_in_payload(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id)

    invalid_payload_json = {"status": RoleStatus.ROLES_VERIFIED.value} # Missing revision
    response = client.post(f"/api/roles/{test_role.id}/status", json=invalid_payload_json)

    assert response.status_code == 422 # Unprocessable Entity due to schema validation

def test_update_role_status_missing_status_in_payload(client: TestClient, db_session: Session):
    test_client_obj = create_test_client(db_session)
    test_role = create_test_role(db_session, client_id=test_client_obj.id, revision=0)

    invalid_payload_json = {"revision": 0} # Missing status
    response = client.post(f"/api/roles/{test_role.id}/status", json=invalid_payload_json)

    assert response.status_code == 422 # Unprocessable Entity

# --- Debugging tests ---
def test_debug_routes(client: TestClient):
    """Prints all registered routes to help diagnose 404s."""
    response = client.get("/openapi.json")
    openapi_schema = response.json()
    print("Registered paths in OpenAPI schema:")
    if "paths" in openapi_schema:
        for path, methods in openapi_schema["paths"].items():
            print(f"Path: {path}")
            for method in methods.keys():
                print(f"  Method: {method.upper()}")

    # Alternative way to print routes directly from the app instance
    print("\nRoutes directly from app instance:")
    from fastapi.routing import APIRoute
    for route in client.app.routes:
        if isinstance(route, APIRoute):
            print(f"Path: {route.path_format}, Methods: {route.methods}, Name: {route.name}")
        elif hasattr(route, "path"): # Handle other route types like APIRouter itself if needed
            print(f"Router/Mount Path: {route.path}")

    assert response.status_code == 200 # Basic check for openapi.json
