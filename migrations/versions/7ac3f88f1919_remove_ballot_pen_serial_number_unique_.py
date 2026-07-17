"""Remove ballot pen serial number unique constraint

Revision ID: 7ac3f88f1919
Revises: 22e2592ffc4c
Create Date: 2026-07-15 13:51:14.560738

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7ac3f88f1919'
down_revision = '22e2592ffc4c'
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
            REFERENCES polling_centers (id),

            CONSTRAINT fk_ballot_pen_room_id
            FOREIGN KEY(room_id)
            REFERENCES rooms (id),

            CONSTRAINT uq_ballot_pen_code
            UNIQUE(code),

            FOREIGN KEY(district_id)
            REFERENCES district(id),

            FOREIGN KEY(subdistrict_id)
            REFERENCES subdistrict(id)
        )
    """))

    conn.execute(sa.text("""
        INSERT INTO ballot_pen_new
        (
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
        )
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
