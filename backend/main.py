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
)

# Role, RoleStatus might be used later
# Import DTOs (schemas)
from backend.schemas import (
    ClientCreate,
    ClientRead,
    Message,
)

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


@clients_router.delete("/{client_id}", response_model=Message)
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

    return Message(message="Client deleted successfully")


# Include the router in the main FastAPI application
app.include_router(clients_router)


# Placeholder for a root endpoint
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Dataset Distiller API!"}


# TODO: Add other routers (Roles, Ingest, etc.) later.
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
