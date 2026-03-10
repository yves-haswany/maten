from electionsmaten import create_app
from electionsmaten.models.db import db
from electionsmaten.models import *

app = create_app()

with app.app_context():
    db.create_all()
    print("Database created successfully")