from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlmodel import (
    Session,
    create_engine,
    select,
)

# select for query construction
# Import models (ensure they are all imported if SQLModel.metadata.create_all is used elsewhere)
from backend.models import (
    Client,
    Role, # Added Role
    RoleStatus, # Added RoleStatus
)

# Role, RoleStatus might be used later
# Import DTOs (schemas)
from backend.schemas import (
    ClientCreate,
    ClientRead,
    Message,
    RoleCreate, # Added RoleCreate
    RoleRead,
    RoleStatusUpdate,
    RoleUpdate, # Added RoleUpdate
    IngestResponse, # Added IngestResponse
)
from datetime import datetime, timezone
from fastapi import UploadFile, File # Added UploadFile, File

# Import settings
from backend.settings import settings

# Database Setup
DATABASE_URL = str(settings.DATABASE_URL)  # Ensure it's a string
engine = create_engine(DATABASE_URL)  # echo=True for debugging SQL


# Dependency to get DB session
def get_db_session():
    with Session(engine) as session:
        yield session


# FastAPI Application Initialization
app = FastAPI(
    title="Dataset Distiller API",
    version="0.2.0",
    description="API for managing clients, roles, and document processing pipelines.",
)

# Clients Router
clients_router = APIRouter(
    prefix="/api/clients",
    tags=["Clients"],
    responses={404: {"description": "Client not found"}},  # Default 404 for this router
)


@clients_router.post(
    "/", response_model=ClientRead, status_code=status.HTTP_201_CREATED
)
def create_client(
    client_data: ClientCreate,  # Using ClientCreate directly as body, not Depends() unless form data
    db_session: Session = Depends(get_db_session),
):
    """
    Create a new client.
    """
    # db_client = Client.from_orm(client_data) # SQLModel v1 style
    db_client = Client.model_validate(
        client_data
    )  # Pydantic v2 / SQLModel style for creating model from schema

    db_session.add(db_client)
    try:
        db_session.commit()
        db_session.refresh(db_client)
    except Exception as e:  # Catch potential db errors, e.g. unique constraints
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating client: {str(e)}",
        )
    return db_client


@clients_router.get("/", response_model=List[ClientRead])
def list_clients(
    skip: int = 0, limit: int = 100, db_session: Session = Depends(get_db_session)
):
    """
    List all clients with pagination.
    """
    statement = select(Client).offset(skip).limit(limit)
    clients = db_session.exec(statement).all()
    return clients


@clients_router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: UUID, db_session: Session = Depends(get_db_session)):
    """
    Get a specific client by their ID.
    """
    client = db_session.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )
    return client


@clients_router.put("/{client_id}", response_model=ClientRead)
def update_client(
    client_id: UUID,
    client_data: ClientCreate,  # Using ClientCreate for update as ClientUpdate wasn't specified for clients
    db_session: Session = Depends(get_db_session),
):
    """
    Update an existing client.
    """
    db_client = db_session.get(Client, client_id)
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    client_update_data = client_data.model_dump(
        exclude_unset=True
    )  # Get only fields that were set
    for key, value in client_update_data.items():
        setattr(db_client, key, value)

    db_session.add(db_client)
    try:
        db_session.commit()
        db_session.refresh(db_client)
    except Exception as e:
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating client: {str(e)}",
        )
    return db_client


@clients_router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_client(client_id: UUID, db_session: Session = Depends(get_db_session)):
    """
    Delete a client.
    """
    db_client = db_session.get(Client, client_id)
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    # Check for dependent roles before deleting if necessary (not specified, but good practice)
    # roles_count_stmt = select(func.count(Role.id)).where(Role.client_id == client_id)
    # roles_count = db_session.exec(roles_count_stmt).one_or_none()
    # if roles_count and roles_count > 0:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail=f"Cannot delete client: {roles_count} role(s) still associated with this client."
    #     )

    try:
        db_session.delete(db_client)
        db_session.commit()
    except Exception as e:  # Catch potential db errors
        db_session.rollback()
        # More specific error handling might be needed for FK constraints if roles are not checked
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting client: {str(e)}",
        )

    # return Message(message="Client deleted successfully") # Removed for 204
    return None


# Include the router in the main FastAPI application
app.include_router(clients_router)

# New router for client-specific role operations
client_roles_router = APIRouter(
    prefix="/api/clients/{client_id}/roles", # Prefix now includes client_id
    tags=["Roles"], # Tag appropriately
    responses={404: {"description": "Client or Role not found"}} # More specific 404
)

# Endpoint to create a role for a client
@client_roles_router.post(
    "/", # Path is now relative to the new router's prefix
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new role for a specific client"
)
def create_role_for_client( # Function signature remains the same, client_id is from path
    client_id: UUID,
    role_data: RoleCreate,
    db_session: Session = Depends(get_db_session),
):
    # Check if client exists
    client = db_session.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    # Create Role instance from RoleCreate data, plus client_id and defaults
    db_role = Role.model_validate(
        role_data,
        update={
            "client_id": client_id,
            "status": RoleStatus.PARSED, # Default status
            "revision": 0, # Initial revision
        }
    )

    db_session.add(db_role)
    try:
        db_session.commit()
        db_session.refresh(db_role)
    except Exception as e:
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating role: {str(e)}",
        )
    return db_role

# Endpoint to list roles for a client
@client_roles_router.get(
    "/", # Path is now relative to the new router's prefix
    response_model=List[RoleRead],
    summary="List all roles for a specific client"
)
def list_roles_for_client( # Function signature remains the same, client_id is from path
    client_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db_session: Session = Depends(get_db_session),
):
    # Check if client exists
    client = db_session.get(Client, client_id)
    if not client:
        # This router's 404 is "Client or Role not found", which is fine
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found to list roles for"
        )

    statement = select(Role).where(Role.client_id == client_id).offset(skip).limit(limit)
    roles = db_session.exec(statement).all()
    return roles

app.include_router(client_roles_router) # Include the new router

# Roles Router
roles_router = APIRouter(
    prefix="/api/roles",
    tags=["Roles"],
    responses={404: {"description": "Role not found"}},
)

# Define allowed status transitions
ALLOWED_STATUS_TRANSITIONS = {
    RoleStatus.PARSED: [RoleStatus.ROLES_VERIFIED],
    RoleStatus.ROLES_VERIFIED: [RoleStatus.INPUT_SYNTHESIZED],
    RoleStatus.INPUT_SYNTHESIZED: [RoleStatus.INPUT_CURATED],
    RoleStatus.INPUT_CURATED: [RoleStatus.VALIDATED],
    RoleStatus.VALIDATED: [RoleStatus.EXPORTED],
    RoleStatus.EXPORTED: [],  # No transitions from Exported
}


@roles_router.get("/{role_id}", response_model=RoleRead, summary="Get a specific role by its ID")
def get_role(role_id: UUID, db_session: Session = Depends(get_db_session)):
    db_role = db_session.get(Role, role_id)
    if not db_role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return db_role


@roles_router.put("/{role_id}", response_model=RoleRead, summary="Update a role")
def update_role(
    role_id: UUID,
    role_data: RoleUpdate,
    db_session: Session = Depends(get_db_session),
):
    db_role = db_session.get(Role, role_id)
    if not db_role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    # Optimistic Locking
    if db_role.revision != role_data.revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Revision number mismatch. Current revision is {db_role.revision}, "
                f"but update was based on revision {role_data.revision}."
            ),
        )

    # Use model_dump with exclude_defaults=True to get only fields explicitly sent in the request
    # Also exclude 'revision' as it's handled separately for optimistic locking.
    role_update_dict = role_data.model_dump(exclude_defaults=True, exclude={"revision"})
    # print(f"DEBUG: role_update_dict for sqlmodel_update (exclude_defaults): {role_update_dict}") # For debugging

    # Apply updates field by field from the constructed dict
    # Using sqlmodel_update is generally preferred if it handles partial updates correctly.
    # Reverted to setattr loop for explicit control if issues persist with None values.
    for key, value in role_update_dict.items():
        setattr(db_role, key, value)

    db_role.revision += 1
    db_role.updated_at = datetime.now(timezone.utc)

    db_session.add(db_role)
    try:
        db_session.commit()
        db_session.refresh(db_role)
    except Exception as e:
        db_session.rollback()
        db_session.rollback()
        print(f"Error updating role: {str(e)}") # Print the actual error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating role: {str(e)}",
        )
    return db_role


@roles_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a role")
def delete_role(role_id: UUID, db_session: Session = Depends(get_db_session)):
    db_role = db_session.get(Role, role_id)
    if not db_role:
        # No need to raise 404 for DELETE, it's idempotent.
        # If it doesn't exist, it's already in the desired state (deleted).
        return None

    try:
        db_session.delete(db_role)
        db_session.commit()
    except Exception as e: # Catch potential db errors (e.g. FK constraints if not handled)
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting role: {str(e)}",
        )
    return None


@roles_router.post("/{role_id}/validate", response_model=RoleRead)
def validate_role_input(
    role_id: UUID,
    db_session: Session = Depends(get_db_session),
):
    """
    Validate the input for a role (placeholder) and advance status from InputCurated to Validated.
    """
    db_role = db_session.get(Role, role_id)
    if not db_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    # Placeholder for LangGraph validate_input node call
    print(f"INFO: Placeholder - LangGraph 'validate_input' node would be called for role_id: {role_id}")

    # Status Transition Validation: Only from InputCurated to Validated
    if db_role.status != RoleStatus.INPUT_CURATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Role status must be '{RoleStatus.INPUT_CURATED.value}' to be validated. "
                f"Current status is '{db_role.status.value}'."
            ),
        )

    # Update status, revision, and updated_at
    db_role.status = RoleStatus.VALIDATED
    db_role.revision += 1
    db_role.updated_at = datetime.now(timezone.utc)

    db_session.add(db_role)
    try:
        db_session.commit()
        db_session.refresh(db_role)
    except Exception as e: # Catch potential db errors
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error validating role: {str(e)}",
        )
    return db_role


@roles_router.post("/{role_id}/status", response_model=RoleRead)
def update_role_status(
    role_id: UUID,
    status_update_data: RoleStatusUpdate,
    db_session: Session = Depends(get_db_session),
):
    """
    Update the status of a role, with optimistic locking and status transition validation.
    """
    db_role = db_session.get(Role, role_id)
    if not db_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    # Optimistic Locking
    if db_role.revision != status_update_data.revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Revision number mismatch. Current revision is {db_role.revision}, "
                f"but update was based on revision {status_update_data.revision}."
            ),
        )

    # Status Transition Validation
    current_status = db_role.status
    next_status = status_update_data.status

    if next_status not in ALLOWED_STATUS_TRANSITIONS.get(current_status, []):
        valid_next_statuses = ALLOWED_STATUS_TRANSITIONS.get(current_status, [])
        detail_msg = (
            f"Invalid status transition from '{current_status.value}' to '{next_status.value}'. "
            f"Allowed next statuses: {[s.value for s in valid_next_statuses]}."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail_msg,
        )

    # Update status, revision, and updated_at
    db_role.status = next_status
    db_role.revision += 1
    db_role.updated_at = datetime.now(timezone.utc)

    db_session.add(db_role)
    try:
        db_session.commit()
        db_session.refresh(db_role)
    except Exception as e: # Catch potential db errors
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, # Or 500 for general DB errors
            detail=f"Error updating role status: {str(e)}",
        )
    return db_role

app.include_router(roles_router)

# Ingest Router
ingest_router = APIRouter(
    prefix="/api/ingest",
    tags=["Ingest"]
)

# Import the service function
from backend.services.ingest import process_uploaded_files

@ingest_router.post("/{client_id}", response_model=IngestResponse)
async def ingest_files_for_client(
    client_id: UUID,
    files: List[UploadFile] = File(...),
    db_session: Session = Depends(get_db_session),
):
    """
    Ingest uploaded files (resume and source documents) for a specific client.
    """
    # Ensure client exists
    client = db_session.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No files were uploaded."
        )

    # Call the service function to process files and invoke pipeline
    # This is an async endpoint, but process_uploaded_files is currently sync.
    # For a real application, process_uploaded_files might be run in a threadpool
    # or be an async function itself if it involves I/O-bound operations suitable for asyncio.
    # For M4, direct call is fine.
    processing_result = process_uploaded_files(client_id=client_id, files=files)

    return IngestResponse(
        message=processing_result.get("message", "Processing complete."),
        num_files_processed=processing_result.get("num_files_processed", 0)
        # pipeline_output can be added to IngestResponse schema if needed
    )

app.include_router(ingest_router)


# Placeholder for a root endpoint
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Dataset Distiller API!"}


# TODO: Add other routers (Ingest, etc.) later.
# Example:
# from .routers import roles_router, ingest_router # Hypothetical future routers
# app.include_router(roles_router)
# app.include_router(ingest_router)

# For local development, if you want to run this file directly with uvicorn:
# if __name__ == "__main__":
#     import uvicorn
#     # Create tables if they don't exist (for local dev only, Alembic handles migrations)
#     # SQLModel.metadata.create_all(engine)
#     uvicorn.run(app, host="0.0.0.0", port=8000)
