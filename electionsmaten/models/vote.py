from datetime import datetime
from .db import db

class Vote(db.Model):
    id = db.Column(db.BigInteger, primary_key=True)

    elector_id = db.Column(db.Integer, db.ForeignKey("elector.id"), nullable=False)
    election_id = db.Column(db.Integer, db.ForeignKey("election.id"), nullable=False)
    list_id = db.Column(db.Integer, db.ForeignKey("candidate_list.id"), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate.id"), nullable=True)
    ballot_pen_id = db.Column(db.Integer, db.ForeignKey("ballot_pen.id"), nullable=False)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            'elector_id',
            'election_id',
            name='unique_vote_per_election'
        ),
        db.Index('idx_vote_election', 'election_id'),
        db.Index('idx_vote_candidate', 'candidate_id'),
    )