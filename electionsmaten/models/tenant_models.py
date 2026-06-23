from datetime import datetime

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime

Base = declarative_base()


class Elector(Base):
    __tablename__ = "elector"

    id = Column(Integer, primary_key=True)

    elector_id = Column(String(120), nullable=False)

    district_id = Column(Integer, nullable=False)

    uploaded_at = Column(DateTime, default=datetime.utcnow)


class BallotPen(Base):
    __tablename__ = "ballot_pen"

    id = Column(Integer, primary_key=True)

    serial_number = Column(String(120), nullable=False)

    district_id = Column(Integer, nullable=False)

    username = Column(String(120), unique=True, nullable=False)

    password = Column(String(255), nullable=False)

    active_session_token = Column(String(255))


class CandidateList(Base):
    __tablename__ = "candidate_list"

    id = Column(Integer, primary_key=True)

    district_id = Column(Integer, nullable=False)

    name = Column(String(120), nullable=False)


class Candidate(Base):
    __tablename__ = "candidate"

    id = Column(Integer, primary_key=True)

    candidate_list_id = Column(Integer, nullable=False)

    name = Column(String(120), nullable=False)


class Vote(Base):
    __tablename__ = "vote"

    id = Column(Integer, primary_key=True)

    district_id = Column(Integer, nullable=False)

    ballot_pen_id = Column(Integer, nullable=False)

    list_id = Column(Integer)

    candidate_id = Column(Integer)

    timestamp = Column(DateTime, default=datetime.utcnow)