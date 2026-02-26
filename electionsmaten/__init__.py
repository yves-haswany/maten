from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)

    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///electors.db"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Ensure exports folder exists
    os.makedirs("exports", exist_ok=True)

    # Initialize Database
    db.init_app(app)

    # Create Tables
    with app.app_context():
        from . import models
        db.create_all()

    # ✅ Register Blueprints (NEW STRUCTURE)
    from .routes.frontend import frontend
    from .routes.backend import backend

    app.register_blueprint(frontend)
    app.register_blueprint(backend)

    return app