from flask import Flask, redirect, url_for
import os

from .db.master_db import db, init_master_db
from .services.tenant_service import init_tenant_db_registry


def create_app():

    app = Flask(__name__)

    app.config["SECRET_KEY"] = "devsecret"

    app.config["MASTER_DATABASE_URL"] = "sqlite:///maten_master.db"

    # -------------------------------------------------
    # 1. INIT MASTER DB
    # -------------------------------------------------
    init_master_db(app)

    # -------------------------------------------------
    # 2. IMPORT MODELS (IMPORTANT BEFORE MIGRATION/QUERY)
    # -------------------------------------------------
    from .models import master_models

    # -------------------------------------------------
    # 3. CREATE TABLES (ONLY FOR DEV)
    # -------------------------------------------------
    with app.app_context():
        db.create_all()   # ⚠️ only for dev/testing

    # -------------------------------------------------
    # 4. NOW SAFE TO QUERY TENANTS
    # -------------------------------------------------
    init_tenant_db_registry(app)

    # -------------------------------------------------
    # BLUEPRINTS
    # -------------------------------------------------
    from .routes.auth import auth_bp
    from .routes.backend.admin import admin_bp
    from .routes.backend.tenant import tenant_bp
    from .routes.frontend import frontend_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tenant_bp)
    app.register_blueprint(frontend_bp)
    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    return app