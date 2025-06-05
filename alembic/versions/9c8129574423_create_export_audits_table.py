"""create_export_audits_table

Revision ID: 9c8129574423
Revises: b233c9a2807b
Create Date: 2025-06-04 23:55:43.748600

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel # Required for sqlmodel.sql.sqltypes.GUID


# revision identifiers, used by Alembic.
revision: str = '9c8129574423'
down_revision: Union[str, None] = 'b233c9a2807b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('export_audits',
        sa.Column('id', sqlmodel.sql.sqltypes.GUID, primary_key=True),
        sa.Column('client_id', sqlmodel.sql.sqltypes.GUID, sa.ForeignKey('clients.id'), nullable=False, index=True),
        sa.Column('exported_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('checksum', sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('export_audits')
