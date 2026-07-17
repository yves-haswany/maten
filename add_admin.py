from electionsmaten import create_app
from electionsmaten.db.master_db import db
from electionsmaten.models.master_models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():

    db.create_all()

    if not User.query.filter_by(username="admin").first():

        admin_user = User(
            username="admin",
            password=generate_password_hash("admin"),
            role="admin"
        )

        db.session.add(admin_user)
        db.session.commit()

        print("Default admin created in MASTER DB")

    else:
        print("Admin already exists")