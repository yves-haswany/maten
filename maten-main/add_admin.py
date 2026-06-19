from electionsmaten import create_app, db
from electionsmaten.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():

    # ONLY seed admin, DO NOT create schema
    if not User.query.filter_by(username="admin").first():

        admin_user = User(
            username="admin",
            password=generate_password_hash("admin"),
            role="admin"
        )

        db.session.add(admin_user)
        db.session.commit()

        print("Default admin created")
    else:
        print("Admin already exists")