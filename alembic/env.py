import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

# ----------------------------------------------------
# Project path
# ----------------------------------------------------

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            ".."
        )
    )
)

# ----------------------------------------------------
# Import metadata
# ----------------------------------------------------

from electionsmaten import db
import electionsmaten.models

from electionsmaten.models.tenant_models import Base

# ----------------------------------------------------
# Alembic config
# ----------------------------------------------------

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

# ----------------------------------------------------
# Migration mode
# ----------------------------------------------------

DB_MODE = os.getenv(
    "DB_MODE",
    "master"
).lower()

# ----------------------------------------------------
# Select metadata
# ----------------------------------------------------

if DB_MODE == "master":

    target_metadata = db.metadata

else:

    target_metadata = Base.metadata

# ----------------------------------------------------
# Database URL
# ----------------------------------------------------

if DB_MODE == "master":

    DATABASE_URL = config.get_main_option(
        "sqlalchemy.url"
    )

else:

    TENANT_DB = os.getenv("TENANT_DB")

    if not TENANT_DB:

        raise RuntimeError(
            "TENANT_DB environment variable is required."
        )

    DATABASE_URL = (
        f"sqlite:///instance/{TENANT_DB}.db"
    )

# ----------------------------------------------------
# Offline migrations
# ----------------------------------------------------

def run_migrations_offline():

    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
        compare_type=True,
        compare_server_default=True
    )

    with context.begin_transaction():

        context.run_migrations()

# ----------------------------------------------------
# Online migrations
# ----------------------------------------------------

def run_migrations_online():

    connectable = create_engine(
        DATABASE_URL,
        poolclass=pool.NullPool
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True
        )

        with context.begin_transaction():

            context.run_migrations()

# ----------------------------------------------------
# Run
# ----------------------------------------------------

if context.is_offline_mode():

    run_migrations_offline()

else:

    run_migrations_online()