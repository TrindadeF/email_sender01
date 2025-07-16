"""Aumenta tamanho do password_hash

Revision ID: 1f11d23547c6
Revises: 577a56c47a23
Create Date: 2025-07-16 11:48:39.260857

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f11d23547c6'
down_revision: Union[str, Sequence[str], None] = '577a56c47a23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Altera o tipo da coluna password_hash para Text (ou aumente para 256 se preferir)
    op.alter_column('user', 'password_hash',
        existing_type=sa.VARCHAR(length=128),
        type_=sa.Text(),
        existing_nullable=False
    )


def downgrade() -> None:
    # Reverte para VARCHAR(128) se necessário
    op.alter_column('user', 'password_hash',
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=128),
        existing_nullable=False
    )
