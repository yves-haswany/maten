from datetime import datetime
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime


Base = declarative_base()


# =====================================================
# BALLOT PEN
# =====================================================

class BallotPen(Base):

    __tablename__ = "ballot_pen"

    id = Column(Integer, primary_key=True)

    serial_number = Column(
        String(120),
        nullable=False
    )

    district_id = Column(
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


# =====================================================
# CANDIDATE LIST
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


# =====================================================
# CANDIDATE
# =====================================================

class Candidate(Base):

    __tablename__ = "candidate"

    id = Column(Integer, primary_key=True)

    candidate_list_id = Column(
        Integer,
        nullable=False
    )

    name = Column(
        String(120),
        nullable=False
    )


# =====================================================
# VOTE
# =====================================================

class Vote(Base):

    __tablename__ = "vote"

    id = Column(Integer, primary_key=True)

    district_id = Column(
        Integer,
        nullable=False
    )

    ballot_pen_id = Column(
        Integer,
        nullable=False
    )

    list_id = Column(
        Integer
    )

    candidate_id = Column(
        Integer
    )

    timestamp = Column(
        DateTime,
        default=datetime.utcnow
    )
class TenantInfo(Base):
    __tablename__ = "tenant_info"

    id = Column(Integer, primary_key=True)

    tenant_id = Column(Integer)

    party_name = Column(String(120))