from electionsmaten import create_app, db
from electionsmaten.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    admin = User(
        username="admin",
        password=generate_password_hash("admin123"),
        is_admin=True
    )
    db.session.add(admin)
    db.session.commit()
