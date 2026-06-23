from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import logging
import psycopg2
from psycopg2 import sql

TENANT_ENGINES = {}
TENANT_SESSIONS = {}

# ✅ FIX 1: logger definition
logger = logging.getLogger(__name__)


DB_HOST = "localhost"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = "password"
MASTER_DB = "postgres"


def create_database(db_name: str):
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=MASTER_DB
    )

    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute(
            sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(db_name)
            )
        )
        logger.info(f"Created DB: {db_name}")

    except psycopg2.errors.DuplicateDatabase:
        logger.info(f"DB already exists: {db_name}")

    finally:
        cur.close()
        conn.close()


def get_tenant_db_url(db_name):
    return f"postgresql://postgres:password@localhost/{db_name}"


def get_tenant_session(db_name):

    if db_name not in TENANT_SESSIONS:

        engine = create_engine(get_tenant_db_url(db_name), pool_pre_ping=True)

        session_factory = sessionmaker(bind=engine)
        session = scoped_session(session_factory)

        TENANT_ENGINES[db_name] = engine
        TENANT_SESSIONS[db_name] = session

    return TENANT_SESSIONS[db_name]


def init_tenant_db_registry(app):

    with app.app_context():
        from .models import Tenant

        tenants = Tenant.query.all()

        if not tenants:
            logger.info("No tenants found in master DB")
            return

        logger.info(f"Found {len(tenants)} tenants")

        for tenant in tenants:
            db_name = f"tenant_{tenant.username}".lower()

            logger.info(f"Checking DB for tenant: {tenant.username}")

            create_database(db_name)

        logger.info("✅ Tenant DB registry initialization complete")