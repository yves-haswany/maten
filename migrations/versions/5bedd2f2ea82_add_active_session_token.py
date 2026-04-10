from alembic import op
import sqlalchemy as sa

revision = '5bedd2f2ea82'
down_revision = '6014c1afd932'
branch_labels = None
depends_on = None


def upgrade():
    # ✅ Ensure no NULL usernames BEFORE constraint
    op.execute("""
        UPDATE district
        SET username = 'user_' || id
        WHERE username IS NULL
    """)

    # ✅ Now safe to alter
    with op.batch_alter_table('district', schema=None) as batch_op:
        batch_op.alter_column(
            'username',
            existing_type=sa.VARCHAR(length=120),
            nullable=False
        )

        batch_op.create_unique_constraint(
            'uq_district_username',
            ['username']
        )


def downgrade():
    with op.batch_alter_table('district', schema=None) as batch_op:
        batch_op.drop_constraint('uq_district_username', type_='unique')

        batch_op.alter_column(
            'username',
            existing_type=sa.VARCHAR(length=120),
            nullable=True
        )