from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import date, datetime
from typing import List, Optional

from backend.models import RoleStatus # Assuming RoleStatus is defined in backend.models

# Client Schemas
class ClientBase(BaseModel):
    display_name: str
    notes: Optional[str] = None

class ClientCreate(ClientBase):
    pass

class ClientRead(ClientBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Role Schemas
class RoleBase(BaseModel):
    company_name: str
    title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    output_text: str # Corresponds to "Description/Achievements"

class RoleCreate(RoleBase):
    # client_id will be path parameter or from context, not in create schema body for typical REST API
    pass

class RoleRead(RoleBase):
    id: UUID
    client_id: UUID
    status: RoleStatus
    input_text_compact: Optional[str] = None
    validation_notes: Optional[str] = None # Could be structured JSON if needed later
    revision: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class RoleUpdate(BaseModel):
    company_name: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    output_text: Optional[str] = None
    input_text_compact: Optional[str] = None # For internal LLM summary of inputs
    status: Optional[RoleStatus] = None
    validation_notes: Optional[str] = None # For curator feedback
    revision: int = Field(..., description="Current revision number for optimistic locking")

class RoleStatusUpdate(BaseModel):
    status: RoleStatus
    revision: int = Field(..., description="Current revision number for optimistic locking")


# Ingest Schemas
class IngestResponse(BaseModel):
    message: str
    num_files_processed: int
    # client_id: UUID # client_id is usually a path param for ingest, response confirms it or gives job info.
    # job_id: Optional[str] = None # If ingest is async


# General Utility Schemas
class Message(BaseModel):
    """For simple confirmation or error messages from API."""
    message: str
