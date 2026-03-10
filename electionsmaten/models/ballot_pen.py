from .db import db

class BallotPen(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    serial_number = db.Column(db.String(120), unique=True, nullable=False)
    status = db.Column(db.String(50), default="active")

    district_id = db.Column(db.Integer, db.ForeignKey("district.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)