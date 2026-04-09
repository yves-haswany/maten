from sqlalchemy import text
from electionsmaten import create_app, db

app = create_app()
with app.app_context():
    result = db.session.execute(text("PRAGMA table_info(district)")).fetchall()
    print("Columns in 'district' table:")
    for row in result:
        print(row)