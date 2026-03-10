from .db import db

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    # Link candidate to party
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"))

    candidate_list_id = db.Column(
        db.Integer,
        db.ForeignKey("candidate_list.id"),
        nullable=False
    )