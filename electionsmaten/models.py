from datetime import datetime
from . import db


# ---------------------------
# TENANT / PARTY
# ---------------------------
class Party(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    users = db.relationship("User", backref="party", lazy=True)
    elections = db.relationship("Election", backref="party", lazy=True)


# ---------------------------
# USERS (OPERATORS / ADMINS)
# ---------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    is_admin = db.Column(db.Boolean, default=False)

    party_id = db.Column(db.Integer, db.ForeignKey("party.id"))

    district_id = db.Column(db.Integer, db.ForeignKey("district.id"))

    ballot_pen = db.relationship("BallotPen", backref="user", uselist=False)


# ---------------------------
# ELECTION
# ---------------------------
class Election(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)

    party_id = db.Column(db.Integer, db.ForeignKey("party.id"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    districts = db.relationship("District", backref="election", lazy=True)


# ---------------------------
# DISTRICT
# ---------------------------
class District(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    election_id = db.Column(db.Integer, db.ForeignKey("election.id"))

    electors = db.relationship("Elector", backref="district", lazy=True)
    ballot_pens = db.relationship("BallotPen", backref="district", lazy=True)
    candidate_lists = db.relationship("CandidateList", backref="district", lazy=True)


# ---------------------------
# ELECTORS (VOTERS)
# ---------------------------
class Elector(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    elector_id = db.Column(db.String(120), nullable=False)

    district_id = db.Column(db.Integer, db.ForeignKey("district.id"))

    has_voted = db.Column(db.Boolean, default=False)

    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------
# CANDIDATE LIST
# ---------------------------
class CandidateList(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    election_id = db.Column(db.Integer, db.ForeignKey("election.id"))
    district_id = db.Column(db.Integer, db.ForeignKey("district.id"))

    candidates = db.relationship("Candidate", backref="candidate_list", lazy=True)


# ---------------------------
# CANDIDATE
# ---------------------------
class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    party = db.Column(db.String(120))

    candidate_list_id = db.Column(
        db.Integer,
        db.ForeignKey("candidate_list.id"),
        nullable=False
    )


# ---------------------------
# BALLOT PEN (VOTING DEVICE)
# ---------------------------
class BallotPen(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    serial_number = db.Column(db.String(120), unique=True, nullable=False)

    status = db.Column(db.String(50), default="active")

    district_id = db.Column(db.Integer, db.ForeignKey("district.id"))

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)


# ---------------------------
# VOTES
# ---------------------------
class Vote(db.Model):
    id = db.Column(db.BigInteger, primary_key=True)

    elector_id = db.Column(
        db.Integer,
        db.ForeignKey("elector.id"),
        nullable=False
    )

    election_id = db.Column(
        db.Integer,
        db.ForeignKey("election.id"),
        nullable=False
    )

    list_id = db.Column(
        db.Integer,
        db.ForeignKey("candidate_list.id"),
        nullable=False
    )

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidate.id"),
        nullable=True
    )

    ballot_pen_id = db.Column(
        db.Integer,
        db.ForeignKey("ballot_pen.id"),
        nullable=False
    )

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            'elector_id',
            'election_id',
            name='unique_vote_per_election'
        ),
    )