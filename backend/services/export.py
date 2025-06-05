import hashlib
import json
from typing import List
from uuid import UUID
from datetime import datetime, timezone

from sqlmodel import Session, select
from backend.models import Role, RoleStatus, ExportAudit, Client # Client import added for completeness

def get_validated_roles_for_client(client_id: UUID, db: Session) -> List[Role]:
    statement = select(Role).where(Role.client_id == client_id).where(Role.status == RoleStatus.VALIDATED)
    roles = db.exec(statement).all()
    return roles

def format_roles_to_jsonl(roles: List[Role]) -> str:
    jsonl_lines = []
    for role in roles:
        # Ensure consistent key ordering for deterministic checksum
        role_data = {
            "input_text_compact": role.input_text_compact,
            "output_text": role.output_text
        }
        jsonl_lines.append(json.dumps(role_data, sort_keys=True))
    return "\n".join(jsonl_lines)

def calculate_checksum(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def create_export_audit_record(db: Session, client_id: UUID, row_count: int, filename: str, checksum: str) -> ExportAudit:
    export_audit = ExportAudit(
        client_id=client_id,
        row_count=row_count,
        filename=filename,
        checksum=checksum,
        # exported_at is handled by default_factory
    )
    db.add(export_audit)
    db.commit()
    db.refresh(export_audit)
    return export_audit
