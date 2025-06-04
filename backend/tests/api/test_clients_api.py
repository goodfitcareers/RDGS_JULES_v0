import pytest
import uuid # For generating test UUIDs
from fastapi.testclient import TestClient

# import backend.models # No longer importing globally here, will do in fixture
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool # For SQLite in-memory with shared connection

from backend.main import app, get_db_session
from backend.models import Client
from backend.schemas import ClientCreate, ClientRead
from backend.settings import settings

# --- Test Database Setup ---
# Using an in-memory SQLite database for test isolation and speed.
TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def test_engine():
    """
    Creates an in-memory SQLite engine for testing using StaticPool.
    Ensures all tables are created before tests run and dropped afterwards.
    StaticPool is crucial for in-memory SQLite to ensure all sessions use the same connection.
    """
    # Import models here to ensure SQLModel.metadata is populated before create_all
    from backend import models as backend_models_fixture_import

    engine = create_engine(
        "sqlite:///:memory:", # Use in-memory SQLite
        connect_args={"check_same_thread": False}, # Required for SQLite in-memory
        poolclass=StaticPool, # Ensures the same connection is used by all sessions
        echo=False # True for SQL debugging, False for cleaner test output
    )

    # SQLModel.metadata is global, so just calling create_all on the engine is fine
    # as long as models were imported via backend_models_fixture_import.
    SQLModel.metadata.create_all(engine)
    yield engine # Provide the engine
    SQLModel.metadata.drop_all(engine) # Drop tables using the same engine

# --- Fixtures ---

@pytest.fixture(scope="function")
def db_session(test_engine): # Depends on the test_engine fixture
    """
    Fixture to provide a test database session, using the test_engine.
    The test_engine fixture handles table creation and teardown.
    """
    with Session(test_engine) as session:
        yield session

@pytest.fixture(scope="function")
def client(db_session: Session): # Depends on db_session (which now depends on test_engine)
    """
    Fixture to provide a TestClient for the FastAPI application.
    Overrides the `get_db_session` dependency to use the test database session.
    """
    def override_get_session_for_test():
        # This function becomes the dependency override for get_db_session
        # It yields the db_session provided by the db_session fixture
        try:
            yield db_session
        finally:
            # db_session fixture handles the session closing and table dropping
            pass

    app.dependency_overrides[get_db_session] = override_get_session_for_test

    with TestClient(app) as c:
        yield c

    # Clean up the dependency override after the test to prevent leakage
    app.dependency_overrides.pop(get_db_session, None)


# --- Helper Functions ---

def create_db_client(db: Session, display_name: str = "Test Client", email: str = "test@example.com") -> Client: # Changed name to display_name
    """
    Helper to create a client directly in the database.
    Uses the provided session (typically from the db_session fixture).
    """
    # Assuming ClientCreate schema does not take 'email' directly, based on typical model structure
    # If ClientCreate requires email, it should be part of its definition.
    # For now, assuming Client model itself handles email, and ClientCreate focuses on display_name & notes.
    # Based on schemas.py, ClientCreate only has display_name and notes. Email is not part of ClientCreate.
    # The Client model itself does not show an email field. Let's remove email from helper for now.
    client_data = ClientCreate(display_name=display_name)
    db_client_instance = Client.model_validate(client_data) # Client model needs display_name
    db.add(db_client_instance)
    db.commit()
    db.refresh(db_client_instance)
    return db_client_instance

# --- Test Cases ---

# POST /api/clients/
def test_create_client_success(client: TestClient):
    response = client.post(
        "/api/clients/",
        json={"display_name": "New Client"}, # Changed name to display_name, removed email
    )
    if response.status_code != 201:
        print(f"Create client failed with {response.status_code}, response: {response.text}")
    assert response.status_code == 201
    data = response.json()
    assert data["display_name"] == "New Client" # Check display_name
    # assert data["email"] == "newclient@example.com" # Email is not in ClientRead based on schemas.py
    assert "id" in data
    assert uuid.UUID(data["id"]) # Check if 'id' is a valid UUID
    assert "created_at" in data
    # assert "updated_at" in data # ClientRead schema does not include updated_at

def test_create_client_invalid_data(client: TestClient):
    response = client.post("/api/clients/", json={}) # Sending empty dict should fail display_name
    assert response.status_code == 422

# GET /api/clients/
def test_list_clients_empty(client: TestClient):
    response = client.get("/api/clients/")
    assert response.status_code == 200
    assert response.json() == []

def test_list_clients_multiple(client: TestClient, db_session: Session):
    create_db_client(db_session, display_name="Client Alpha") # Removed email
    create_db_client(db_session, display_name="Client Beta")  # Removed email

    response = client.get("/api/clients/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["display_name"] == "Client Alpha" # Check display_name
    assert data[1]["display_name"] == "Client Beta"  # Check display_name

def test_list_clients_pagination(client: TestClient, db_session: Session):
    for i in range(5):
        create_db_client(db_session, display_name=f"Client {i}") # Removed email

    response_limit = client.get("/api/clients/?limit=2")
    assert response_limit.status_code == 200
    data_limit = response_limit.json()
    assert len(data_limit) == 2

    response_skip_limit = client.get("/api/clients/?skip=2&limit=2")
    assert response_skip_limit.status_code == 200
    data_skip_limit = response_skip_limit.json()
    assert len(data_skip_limit) == 2
    assert data_skip_limit[0]["display_name"] == "Client 2" # Check display_name
    assert data_skip_limit[1]["display_name"] == "Client 3" # Check display_name

# GET /api/clients/{client_id}
def test_get_client_exists(client: TestClient, db_session: Session):
    created = create_db_client(db_session, display_name="Specific Client") # Changed name to display_name
    response = client.get(f"/api/clients/{created.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Specific Client" # Check display_name
    assert str(data["id"]) == str(created.id)

def test_get_client_not_exists(client: TestClient):
    non_existent_uuid = uuid.uuid4()
    response = client.get(f"/api/clients/{non_existent_uuid}")
    assert response.status_code == 404

# PUT /api/clients/{client_id}
def test_update_client_success(client: TestClient, db_session: Session):
    created = create_db_client(db_session, display_name="Old Name") # Changed name to display_name, removed email
    update_payload = {"display_name": "New Name"} # ClientCreate schema used for PUT

    response = client.put(f"/api/clients/{created.id}", json=update_payload)
    if response.status_code != 200:
        print(f"Update client failed with {response.status_code}, response: {response.text}")
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "New Name"       # Check display_name
    # assert data["email"] == "new@example.com" # Email is not in ClientRead or ClientCreate

    db_session.refresh(created) # Refresh from DB
    assert created.display_name == "New Name"       # Check display_name
    # assert created.email == "new@example.com"   # Email not in model


def test_update_client_not_exists(client: TestClient):
    non_existent_uuid = uuid.uuid4()
    response = client.put(
        f"/api/clients/{non_existent_uuid}",
        json={"display_name": "Trying to update"}, # Changed name to display_name, removed email
    )
    assert response.status_code == 404

def test_update_client_invalid_data(client: TestClient, db_session: Session):
    created = create_db_client(db_session) # This will use display_name
    response = client.put(
        f"/api/clients/{created.id}",
        json={}, # Sending empty dict should fail display_name for ClientCreate
    )
    assert response.status_code == 422

# DELETE /api/clients/{client_id}
def test_delete_client_success(client: TestClient, db_session: Session):
    created = create_db_client(db_session) # This will use display_name
    client_id_to_delete = created.id

    response = client.delete(f"/api/clients/{client_id_to_delete}")
    assert response.status_code == 204
    assert not response.content # Ensure no body for 204

    # Verify client is deleted from DB
    deleted_client_from_db = db_session.get(Client, client_id_to_delete)
    assert deleted_client_from_db is None

def test_delete_client_not_exists(client: TestClient):
    non_existent_uuid = uuid.uuid4()
    response = client.delete(f"/api/clients/{non_existent_uuid}")
    assert response.status_code == 404
