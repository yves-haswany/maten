# models.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from . import db


# ---------------------------
# Association Tables
# ---------------------------

tenant_district = db.Table(
    "tenant_district",
    db.Column("tenant_id", db.Integer, db.ForeignKey("tenant.id"), primary_key=True),
    db.Column("district_id", db.Integer, db.ForeignKey("district.id"), primary_key=True)
)


tenant_ballot_pen = db.Table(
    "tenant_ballot_pen",
    db.Column("tenant_id", db.Integer, db.ForeignKey("tenant.id"), primary_key=True),
    db.Column("ballot_pen_id", db.Integer, db.ForeignKey("ballot_pen.id"), primary_key=True)
)
candidate_list_party = db.Table(
    "candidate_list_party",
    db.Column("candidate_list_id", db.Integer, db.ForeignKey("candidate_list.id"), primary_key=True),
    db.Column("party_id", db.Integer, db.ForeignKey("party.id"), primary_key=True)
)



# ---------------------------
# Party
# ---------------------------

class Party(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), unique=True, nullable=False)

    candidate_lists = db.relationship("CandidateList", secondary=candidate_list_party, backref="party", overlaps="parties.party")


# ---------------------------
# District
# ---------------------------

class District(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    # Many-to-many with tenants
    tenants = db.relationship(
        "Tenant",
        secondary=tenant_district,
        back_populates="districts"
    )

    # One district → many ballot pens
    ballot_pens = db.relationship(
        "BallotPen",
        back_populates="district",
        lazy=True
    )
    candidate_lists = db.relationship("CandidateList", backref="district", lazy=True)
    username = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(200), nullable=False)


# ---------------------------
# Candidate List
# ---------------------------

class CandidateList(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    


    parties = db.relationship("Party", secondary=candidate_list_party, back_populates="candidate_lists",overlaps="candidate_lists,party")


    candidates = db.relationship(
        "Candidate",
        backref="candidate_list",
        lazy=True
    )
    district_id = db.Column(
        db.Integer,
        db.ForeignKey("district.id")
    )


# ---------------------------
# Candidate
# ---------------------------

class Candidate(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    candidate_list_id = db.Column(
        db.Integer,
        db.ForeignKey("candidate_list.id"),
        nullable=False
    )

    

    votes = db.relationship(
        "Vote",
        backref="candidate",
        lazy=True
    )
 


# ---------------------------
# Ballot Pen
# ---------------------------

class BallotPen(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    serial_number = db.Column(db.String(120), nullable=False)

    district_id = db.Column(
        db.Integer,
        db.ForeignKey("district.id"),
        nullable=False
    )

    username = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(200), nullable=False)

    # many ballot pens belong to one district
    district = db.relationship(
        "District",
        back_populates="ballot_pens"
    )

    # many-to-many with tenants
    tenants = db.relationship(
        "Tenant",
        secondary=tenant_ballot_pen,
        back_populates="ballot_pens"
    )

    votes = db.relationship(
        "Vote",
        backref="ballot_pen",
        lazy=True
    )


# ---------------------------
# Vote
# ---------------------------

class Vote(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )

    list_id = db.Column(
        db.Integer,
        db.ForeignKey("candidate_list.id")
    )

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidate.id")
    )

    ballot_pen_id = db.Column(
        db.Integer,
        db.ForeignKey("ballot_pen.id")
    )

    timestamp = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# ---------------------------
# Elector
# ---------------------------

class Elector(db.Model):
    __tablename__ = "elector"
    id = db.Column(db.Integer, primary_key=True)

    elector_id = db.Column(
        db.String(120),
        nullable=False
    )

    district_id = db.Column(
        db.Integer,
        db.ForeignKey("district.id"),
        nullable=False
    )
    tenant_id = db.Column(
        db.Integer, db.ForeignKey("tenant.id"), nullable=False
    )

    submitted_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
    ballot_pen_id = db.Column(db.Integer, db.ForeignKey("ballot_pen.id"), nullable=False)  # <-- new


    


# ---------------------------
# Tenant
# ---------------------------

class Tenant(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), unique=True, nullable=False)

    password = db.Column(db.String(200), nullable=False)

    party_id = db.Column(
        db.Integer,
        db.ForeignKey("party.id"),
        nullable=False
    )

    # many-to-many with districts
    districts = db.relationship(
        "District",
        secondary=tenant_district,
        back_populates="tenants"
    )

    # many-to-many with ballot pens
    ballot_pens = db.relationship(
        "BallotPen",
        secondary=tenant_ballot_pen,
        back_populates="tenants"
    )
    party = db.relationship("Party")


# ---------------------------
# User
# ---------------------------

class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(120), unique=True)

    password = db.Column(db.String(200))

    role = db.Column(db.String(50))   # admin, tenant, voter
