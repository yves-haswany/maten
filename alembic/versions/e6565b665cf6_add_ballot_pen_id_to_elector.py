"""Add ballot_pen_id to elector

Revision ID: e6565b665cf6
Revises: f4dd64d4095c
Create Date: 2026-03-20 11:35:52.453840

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6565b665cf6'
down_revision: Union[str, Sequence[str], None] = 'f4dd64d4095c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
