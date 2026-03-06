from datetime import datetime
from . import db


# ---------------------------
# USER MODEL
# ---------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    # Relationships
    electors = db.relationship("Elector", backref="user", lazy=True)
    ballot_pen = db.relationship("BallotPen", backref="user", uselist=False)


# ---------------------------
# ELECTOR MODEL
# ---------------------------
class Elector(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    elector_id = db.Column(db.String(120), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


# ---------------------------
# CANDIDATE LIST MODEL
# ---------------------------
class CandidateList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    list_votes = db.Column(db.Integer, default=0)
    #ballot_pen_id = db.Column(db.Integer, db.ForeignKey("ballot_pen.id"), nullable=False)
    #ballot_pen = db.relationship("BallotPen", backref="candidate_lists", lazy=True)
    candidates = db.relationship("Candidate", backref="candidate_list", lazy=True)


# ---------------------------
# CANDIDATE MODEL
# ---------------------------
class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    party = db.Column(db.String(120), nullable=False)

    votes = db.Column(db.Integer, default=0)

    candidate_list_id = db.Column(db.Integer, db.ForeignKey("candidate_list.id"), nullable=False)
    
   
# ---------------------------
# BALLOT PEN MODEL
# ---------------------------
class BallotPen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(120), unique=True, nullable=False)
    status = db.Column(db.String(50), default="in_use")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)
    
  
class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    list_id = db.Column(db.Integer, db.ForeignKey('candidate_list.id'), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------------------
# BACKEND VOTE SORTING MODELS
# ---------------------------
class VoteList(db.Model):
    __tablename__ = "vote_list"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    votes = db.Column(db.Integer, default=0)

    candidates = db.relationship("VoteCandidate", backref="vote_list", lazy=True)


class VoteCandidate(db.Model):
    __tablename__ = "vote_candidate"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    votes = db.Column(db.Integer, default=0)

    list_id = db.Column(db.Integer, db.ForeignKey("vote_list.id"), nullable=False)

