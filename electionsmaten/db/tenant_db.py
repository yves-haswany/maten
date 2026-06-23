# db/tenant_db.py

import logging
import psycopg2
from psycopg2 import sql

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