from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# =====================================================
# CORE MASTER DB (ADMIN DATABASE ONLY)
# =====================================================

db = SQLAlchemy()
migrate = Migrate()


def init_master_db(app):
    """
    Initialize ONLY the master database (admin, tenants, parties, districts).
    This does NOT touch tenant databases.
    """

    # -------------------------
    # MASTER DATABASE CONFIG
    # -------------------------
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config.get(
        "MASTER_DATABASE_URL",
        "sqlite:///maten_master.db"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # -------------------------
    # INIT EXTENSIONS
    # -------------------------
    db.init_app(app)
    migrate.init_app(app, db)

    # -------------------------
    # IMPORT MASTER MODELS
    # (ensures tables are registered for migration)
    # -------------------------
    from ..models import master_models  # noqa: F401

    return db