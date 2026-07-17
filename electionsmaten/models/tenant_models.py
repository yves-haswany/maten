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
from ..models.master_models import Tenant
from ..db.master_db import db
Base = db.Model


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

    district_id = Column(Integer)

    name = Column(String(120))


# =====================================================
# CANDIDATE
# =====================================================

class Candidate(Base):

    __tablename__ = "candidate"

    id = Column(Integer, primary_key=True)


    candidate_list_id = Column(Integer)

    district_id = Column(Integer)

    subdistrict_id = Column(Integer)

    sect_id = Column(Integer)


    name = Column(String(120))


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

    id = Column(Integer, primary_key=True)

    ballot_pen_id = Column(
        Integer,
        ForeignKey("ballot_pen.id"),
        nullable=False
    )

    tenant_id = Column(
        Integer,
        ForeignKey("tenant.id"),
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

    active_session_token = Column(String(255))
class DistrictAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    tenant_id = db.Column(db.Integer, db.ForeignKey("tenant.id"))
    district_id = db.Column(db.Integer, db.ForeignKey("district.id"))

    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))