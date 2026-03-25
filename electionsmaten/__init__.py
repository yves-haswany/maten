from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os


db = SQLAlchemy()

def create_app():

    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "devsecret")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///maten.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    from . import  models  # Import models after db is initialized

    # Import models AFTER db is initialized
    

    # Blueprints
    from .routes.backend.admin import admin_bp
    from .routes.backend.tenant import tenant_bp
    from .routes.frontend import frontend_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(tenant_bp)
    app.register_blueprint(frontend_bp)

    return app
