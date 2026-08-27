from datetime import datetime



from sqlalchemy import (

    Column,

    Integer,

    String,

    Date,

    Boolean,

    DateTime,

    ForeignKey
)
from ..models.master_models import Tenant,BallotPen, SubDistrict, Sect, SubdistrictSectSeat
from ..db.master_db import db
from ..db.tenant_base import TenantBase

Base = TenantBase


# =====================================================
# ELECTOR
# =====================================================




# =====================================================
# BALLOT PEN
# =====================================================



# =====================================================
# LIST
# =====================================================

class CandidateList(Base):

    __tablename__ = "candidate_list"

    id = Column(Integer, primary_key=True)

    district_id = Column(
        Integer,
        nullable=False
    )

    name = Column(
        String(120),
        nullable=False
    )


    candidates = db.relationship(
        "Candidate",
        back_populates="candidate_list",
        cascade="all, delete-orphan"
    )


# =====================================================
# CANDIDATE
# =====================================================

class Candidate(Base):

    __tablename__ = "candidate"

    id = Column(Integer, primary_key=True)


    candidate_list_id = Column(
    Integer,
    ForeignKey("candidate_list.id"),
    nullable=False
)
    candidate_list = db.relationship(
    "CandidateList",
    back_populates="candidates"
)

    district_id = Column(Integer)

    subdistrict_id = Column(Integer)

    sect_id = db.Column(
    db.Integer,
    nullable=False
)


    name = Column(String(120))
    political_allegiance_id = Column(
    Integer,
    ForeignKey("political_allegiance.id")
)
    political_allegiance = db.relationship(
        "PoliticalAllegiance",
        back_populates="candidates",
    )


# =====================================================
# VOTE
# =====================================================

class Vote(Base):

    __tablename__ = "vote"

    id = Column(Integer, primary_key=True)


    elector_id = Column(Integer)

    ballot_pen_id = Column(Integer)


    district_id = Column(Integer)

    subdistrict_id = Column(Integer)

    sect_id = Column(Integer)


    list_id = Column(Integer)

    candidate_id = Column(Integer)


    timestamp = Column(

        DateTime,

        default=datetime.utcnow

    )

class BallotPenAccount(Base):

    __tablename__ = "ballot_pen_account"

    id = Column(
        Integer,
        primary_key=True
    )

    ballot_pen_id = Column(
        Integer,
        nullable=False
    )

    username = Column(
        String(120),
        unique=True,
        nullable=False
    )

    password = Column(
        String(255),
        nullable=False
    )

    active_session_token = Column(
        String(255)
    )
class DistrictAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    tenant_id = db.Column(db.Integer, db.ForeignKey("tenant.id"))
    district_id = db.Column(db.Integer, db.ForeignKey("district.id"))

    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
# =====================================================
# ELECTOR SUBMISSION
# =====================================================

class ElectorSubmission(Base):

    __tablename__ = "elector_submission"

    id = Column(
        Integer,
        primary_key=True
    )

    ####################################################
    # Master elector reference
    ####################################################

    elector_id = Column(
        Integer,
        nullable=False
    )

    elector_code = Column(
        String(120),
        nullable=False
    )

    ####################################################
    # Elector snapshot
    ####################################################

    first_name = Column(
        String(120)
    )

    surname = Column(
        String(120)
    )

    ####################################################
    # Submission
    ####################################################

    submitted_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    ####################################################
    # District snapshot
    ####################################################

    district_id = Column(
        Integer
    )

    district_name = Column(
        String(120)
    )

    ####################################################
    # Subdistrict snapshot
    ####################################################

    subdistrict_id = Column(
        Integer
    )

    subdistrict_name = Column(
        String(120)
    )

    ####################################################
    # Municipality
    ####################################################

    municipality = Column(
        String(120)
    )

    ####################################################
    # Ballot Pen
    ####################################################

    ballot_pen_id = Column(
        Integer
    )

    ballot_number = Column(
        Integer
    )

    polling_center_name = Column(
        String(150)
    )

    room_name = Column(
        String(150)
    )
class PoliticalAllegiance(Base):

    __tablename__ = "political_allegiance"

    id = Column(Integer, primary_key=True)

    district_id = Column(
        Integer,
        nullable=False
    )

    name = Column(
        String(120),
        nullable=False
    )
    candidates = db.relationship(
        "Candidate",
        back_populates="political_allegiance"
    )
    # =====================================================
# CANCELED PAPER
# =====================================================

class CanceledPaper(Base):

    __tablename__ = "canceled_paper"

    id = Column(
        Integer,
        primary_key=True
    )

    ballot_pen_id = Column(
        Integer,
        nullable=False
    )

    district_id = Column(
        Integer
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )