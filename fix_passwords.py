from electionsmaten import create_app, db
from electionsmaten.models import BallotPen
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    pens = BallotPen.query.all()

    updated = 0

    for pen in pens:
        # If password is NOT hashed → hash it
        if not pen.password.startswith("pbkdf2:"):
            pen.password = generate_password_hash(pen.password)
            updated += 1

    db.session.commit()

    print(f"✅ Done. Updated {updated} passwords.")
