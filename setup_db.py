from flask import Flask
from electionsmaten.models import db, User
from werkzeug.security import generate_password_hash
import os

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///maten.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()  # <-- This creates ALL tables in the database

    # Create default admin user if not exists
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            password=generate_password_hash("admin"),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created: username='admin', password='admin'")
    else:
        print("Admin user already exists.")