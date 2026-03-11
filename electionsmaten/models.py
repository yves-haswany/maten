# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from . import db


class Party(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    elections = db.relationship("Election", backref="party", lazy=True)
    users = db.relationship("User", backref="party", lazy=True)

class Election(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"), nullable=True)
    districts = db.relationship("District", backref="election", lazy=True)
    candidate_lists = db.relationship("CandidateList", backref="election", lazy=True)

class District(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    election_id = db.Column(db.Integer, db.ForeignKey("election.id"), nullable=False)
    users = db.relationship("User", backref="district", lazy=True)

class CandidateList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    election_id = db.Column(db.Integer, db.ForeignKey("election.id"), nullable=False)
    candidates = db.relationship("Candidate", backref="candidate_list", lazy=True)
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"))

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    candidate_list_id = db.Column(db.Integer, db.ForeignKey("candidate_list.id"), nullable=False)
    votes = db.relationship("Vote", backref="candidate", lazy=True)
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"))

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"))
    district_id = db.Column(db.Integer, db.ForeignKey("district.id"))
    ballot_pen = db.relationship("BallotPen", backref="user", uselist=False)

class BallotPen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(120), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    votes = db.relationship("Vote", backref="ballot_pen", lazy=True)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    list_id = db.Column(db.Integer, db.ForeignKey("candidate_list.id"))
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate.id"))
    ballot_pen_id = db.Column(db.Integer, db.ForeignKey("ballot_pen.id"))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
class Elector(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    elector_id = db.Column(db.String(120), unique=True, nullable=False)
    district_id = db.Column(db.Integer, db.ForeignKey("district.id"), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    has_voted = db.Column(db.Boolean, default=False) 
class Tenant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    party_id = db.Column(db.Integer, db.ForeignKey("party.id"), nullable=False)