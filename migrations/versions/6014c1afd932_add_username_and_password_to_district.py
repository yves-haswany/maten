"""Add username and password to District safely for SQLite"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6014c1afd932'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 1️⃣ Add columns (username nullable to avoid conflicts)
    op.add_column('district', sa.Column('username', sa.String(120), nullable=True))
    op.add_column('district', sa.Column('password', sa.String(200), nullable=False, server_default=""))

    # 2️⃣ Populate username with unique values for existing rows
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id FROM district"))
    for row in result:
        conn.execute(
            sa.text("UPDATE district SET username = :uname WHERE id = :id"),
            {"uname": f"user_{row.id}", "id": row.id}
        )

    # 3️⃣ Add UNIQUE constraint
    op.create_unique_constraint("uq_district_username", "district", ["username"])


def downgrade():
    # Drop UNIQUE constraint and columns
    op.drop_constraint("uq_district_username", "district", type_="unique")
    op.drop_column("district", "username")
    op.drop_column("district", "password")