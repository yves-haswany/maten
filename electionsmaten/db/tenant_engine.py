# db/tenant_engine.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

TENANT_ENGINES = {}
TENANT_SESSIONS = {}


def get_tenant_db_url(db_name):
    return f"postgresql://postgres:password@localhost/{db_name}"


def get_tenant_session(db_name):

    if db_name not in TENANT_SESSIONS:

        engine = create_engine(
            get_tenant_db_url(db_name),
            pool_pre_ping=True
        )

        session_factory = sessionmaker(bind=engine)
        session = scoped_session(session_factory)

        TENANT_ENGINES[db_name] = engine
        TENANT_SESSIONS[db_name] = session

    return TENANT_SESSIONS[db_name]