from datetime import datetime
from . import db

class Elector(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    elector_id = db.Column(db.String(120), unique=True, index=True, nullable=False)
    district_id = db.Column(db.Integer, db.ForeignKey("district.id"))

    has_voted = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)