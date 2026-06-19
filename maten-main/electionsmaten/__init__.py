from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "devsecret")

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "MASTER_DATABASE_URL",
        "sqlite:///maten_master.db"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # ✅ ONLY HERE
    migrate.init_app(app, db)

    from . import models

    from .routes.backend.admin import admin_bp
    from .routes.backend.tenant import tenant_bp
    from .routes.frontend import frontend_bp
    from .routes.backend.district import district_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(tenant_bp)
    app.register_blueprint(frontend_bp)
    app.register_blueprint(district_bp)

    from .tenant_db import init_tenant_db_registry
    init_tenant_db_registry(app)

    return app