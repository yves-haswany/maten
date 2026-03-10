from .db import db

class District(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    election_id = db.Column(db.Integer, db.ForeignKey("election.id"))

    # Relationships
    electors = db.relationship("Elector", backref="district", lazy=True)
    ballot_pens = db.relationship("BallotPen", backref="district", lazy=True)
    candidate_lists = db.relationship("CandidateList", backref="district", lazy=True)