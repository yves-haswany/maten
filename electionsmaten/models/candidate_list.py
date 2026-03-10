from .db import db

class CandidateList(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    election_id = db.Column(db.Integer, db.ForeignKey("election.id"))
    district_id = db.Column(db.Integer, db.ForeignKey("district.id"))
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"))

    # Relationships
    candidates = db.relationship("Candidate", backref="candidate_list", lazy=True)