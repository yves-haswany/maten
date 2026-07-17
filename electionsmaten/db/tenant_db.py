import os
from sqlalchemy import create_engine

INSTANCE_PATH = "instance"


def create_database(db_name: str):

    os.makedirs(INSTANCE_PATH, exist_ok=True)

    db_path = os.path.join(INSTANCE_PATH, f"{db_name}.db")

    engine = create_engine(f"sqlite:///{db_path}")

    # Create empty DB file + tables later
    from ..models.tenant_models import Base
    Base.metadata.create_all(engine)

    print(f"Created SQLite DB: {db_path}")