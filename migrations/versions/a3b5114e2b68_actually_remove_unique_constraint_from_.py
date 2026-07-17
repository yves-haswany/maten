"""Actually remove unique constraint from ballot pen code

Revision ID: a3b5114e2b68
Revises: 8ab4c901a496
Create Date: 2026-07-15 14:36:02.953613

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3b5114e2b68'
down_revision = '8ab4c901a496'
branch_labels = None
depends_on = None


def upgrade():

    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE ballot_pen_new (
            id INTEGER NOT NULL,
            polling_center_id INTEGER NOT NULL,
            room_id INTEGER,
            gender_type VARCHAR(20),
            voters_count INTEGER,
            notes VARCHAR(255),
            serial_number VARCHAR(120) NOT NULL,
            district_id INTEGER NOT NULL,
            subdistrict_id INTEGER NOT NULL,
            village VARCHAR(150),
            code VARCHAR(50) NOT NULL,

            PRIMARY KEY (id),

            CONSTRAINT fk_ballot_pen_polling_center_id
            FOREIGN KEY(polling_center_id)
            REFERENCES polling_centers(id),

            CONSTRAINT fk_ballot_pen_room_id
            FOREIGN KEY(room_id)
            REFERENCES rooms(id),

            FOREIGN KEY(district_id)
            REFERENCES district(id),

            FOREIGN KEY(subdistrict_id)
            REFERENCES subdistrict(id)
        )
    """))

    conn.execute(sa.text("""
        INSERT INTO ballot_pen_new
        SELECT
            id,
            polling_center_id,
            room_id,
            gender_type,
            voters_count,
            notes,
            serial_number,
            district_id,
            subdistrict_id,
            village,
            code
        FROM ballot_pen
    """))

    conn.execute(sa.text("""
        DROP TABLE ballot_pen
    """))

    conn.execute(sa.text("""
        ALTER TABLE ballot_pen_new
        RENAME TO ballot_pen
    """))


def downgrade():
    pass
