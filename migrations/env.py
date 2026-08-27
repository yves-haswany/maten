import os
import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

from electionsmaten.db.tenant_base import TenantBase

# IMPORTANT:
# Import tenant models so they are registered in TenantBase.metadata
import electionsmaten.models.tenant_models


# ============================================================
# ALEMBIC CONFIG
# ============================================================

config = context.config

fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")


# ============================================================
# ENGINE
# ============================================================

def get_engine():

    try:

        # Flask-SQLAlchemy < 3
        return current_app.extensions[
            "migrate"
        ].db.get_engine()

    except (TypeError, AttributeError):

        # Flask-SQLAlchemy >= 3
        return current_app.extensions[
            "migrate"
        ].db.engine


def get_engine_url():

    try:

        return (
            get_engine()
            .url
            .render_as_string(
                hide_password=False
            )
            .replace("%", "%%")
        )

    except AttributeError:

        return str(
            get_engine().url
        ).replace("%", "%%")


# ============================================================
# DATABASE
# ============================================================

config.set_main_option(
    "sqlalchemy.url",
    get_engine_url()
)


# ============================================================
# METADATA
# ============================================================

def get_metadata():

    import os

    db_mode = os.environ.get(
        "DB_MODE"
    )

    print(
        "ALEMBIC DB_MODE:",
        db_mode
    )


    # --------------------------------------------------------
    # TENANT DATABASE
    # --------------------------------------------------------

    if db_mode == "tenant":

        print(
            "ALEMBIC USING TENANT METADATA"
        )

        print(
            "TENANT TABLES:",
            list(
                TenantBase.metadata.tables.keys()
            )
        )

        return TenantBase.metadata


    # --------------------------------------------------------
    # MASTER DATABASE
    # --------------------------------------------------------

    target_db = (
        current_app
        .extensions["migrate"]
        .db
    )


    if hasattr(
        target_db,
        "metadatas"
    ):

        return target_db.metadatas[None]


    return target_db.metadata


# ============================================================
# OFFLINE MIGRATIONS
# ============================================================

def run_migrations_offline():

    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(

        url=url,

        target_metadata=get_metadata(),

        literal_binds=True

    )


    with context.begin_transaction():

        context.run_migrations()


# ============================================================
# ONLINE MIGRATIONS
# ============================================================

def run_migrations_online():

    def process_revision_directives(
        context,
        revision,
        directives
    ):

        if getattr(
            config.cmd_opts,
            "autogenerate",
            False
        ):

            script = directives[0]

            if script.upgrade_ops.is_empty():

                directives[:] = []

                logger.info(
                    "No changes in schema detected."
                )


    conf_args = (

        current_app
        .extensions["migrate"]
        .configure_args
    )


    if conf_args.get(
        "process_revision_directives"
    ) is None:

        conf_args[
            "process_revision_directives"
        ] = process_revision_directives


    connectable = get_engine()


    with connectable.connect() as connection:

        context.configure(

            connection=connection,

            target_metadata=get_metadata(),

            **conf_args

        )


        with context.begin_transaction():

            context.run_migrations()


# ============================================================
# RUN
# ============================================================

if context.is_offline_mode():

    run_migrations_offline()

else:

    run_migrations_online()