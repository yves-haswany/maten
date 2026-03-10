from .db import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    is_admin = db.Column(db.Boolean, default=False)

    # Multi-tenant / operator
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"))
    district_id = db.Column(db.Integer, db.ForeignKey("district.id"))

    # One user can control one ballot pen
    ballot_pen = db.relationship("BallotPen", backref="user", uselist=False)