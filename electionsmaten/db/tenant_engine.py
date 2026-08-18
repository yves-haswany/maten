# db/tenant_engine.py

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

INSTANCE_PATH = "instance"

TENANT_ENGINES = {}
TENANT_SESSIONS = {}


def get_tenant_db_url(db_name):
    db_path = os.path.join(INSTANCE_PATH, f"{db_name}.db")
    return f"sqlite:///{db_path}"


def get_tenant_session(db_name):

    if db_name not in TENANT_SESSIONS:

        engine = create_engine(
            get_tenant_db_url(db_name),
            pool_pre_ping=True
        )

        session_factory = sessionmaker(bind=engine)

        TENANT_ENGINES[db_name] = engine
        TENANT_SESSIONS[db_name] = scoped_session(session_factory)

    return TENANT_SESSIONS[db_name]