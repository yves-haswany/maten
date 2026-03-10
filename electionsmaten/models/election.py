from datetime import datetime
from .db import db

class Election(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    districts = db.relationship("District", backref="election", lazy=True)
    # CandidateLists will link to election