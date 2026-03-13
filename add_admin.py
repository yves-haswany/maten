from electionsmaten.models import db, User
from werkzeug.security import generate_password_hash
from flask import Flask

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///maten.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

    # Create default admin
    if not User.query.filter_by(username="admin").first():
        admin_user = User(
            username="admin",
            password=generate_password_hash("admin"),
            role = "admin"
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin created: username='admin', password='admin'")
    else:
        print("Admin already exists.")