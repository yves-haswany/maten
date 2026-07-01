from datetime import datetime

from sqlalchemy.orm import declarative_base

from sqlalchemy import (

    Column,

    Integer,

    String,

    Date,

    Boolean,

    DateTime,

    ForeignKey
)

Base = declarative_base()


# =====================================================
# ELECTOR
# =====================================================

class Elector(Base):

    __tablename__ = "elector"

    id = Column(Integer, primary_key=True)


    elector_id = Column(

        String(120),

        nullable=False

    )


    first_name = Column(String(120))

    surname = Column(String(120))

    family_name = Column(String(120))

    father_name = Column(String(120))

    mother_name = Column(String(120))


    gender = Column(String(10))

    dob = Column(Date)


    religion_id = Column(Integer)

    sect_id = Column(Integer)


    district_id = Column(Integer)

    subdistrict_id = Column(Integer)


    register = Column(String(120))

    register_number = Column(Integer)


    municipality = Column(String(120))

    address = Column(String(255))


    is_dead = Column(Boolean)

    registered = Column(Boolean)


    uploaded_at = Column(

        DateTime,

        default=datetime.utcnow

    )


# =====================================================
# BALLOT PEN
# =====================================================

    class BallotPen(Base):

        __tablename__ = "ballot_pen"

        id = Column(Integer, primary_key=True)

        serial_number = Column(String(120))


        tenant_id = Column(Integer)


        district_id = Column(Integer)

        subdistrict_id = Column(Integer)

        sect_id = Column(Integer)


        username = Column(

            String(120),

            unique=True

        )

        password = Column(String(255))


        active_session_token = Column(String(255))


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