from datetime import datetime

from sqlalchemy import ForeignKey,Column,Integer,String,Date,Boolean,DateTime
from .. import db



# -----------------------
# Tenant ↔ District link
# -----------------------
tenant_district = db.Table(
    "tenant_district",

    db.Column(
        "tenant_id",
        db.Integer,
        db.ForeignKey("tenant.id"),
        primary_key=True
    ),

    db.Column(
        "district_id",
        db.Integer,
        db.ForeignKey("district.id"),
        primary_key=True
    )
)


# =====================================================
# USER
# =====================================================

class User(db.Model):

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(50),
        nullable=False
    )

    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey("tenant.id")
    )

    district_id = db.Column(
        db.Integer,
        db.ForeignKey("district.id")
    )

    ballot_pen_id = db.Column(db.Integer)


# =====================================================
# PARTY
# =====================================================

class Party(db.Model):

    __tablename__ = "party"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )


# =====================================================
# TENANT
# =====================================================

class Tenant(db.Model):

    __tablename__ = "tenant"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    db_name = db.Column(
        db.String(255),
        nullable=False
    )

    party_id = db.Column(
        db.Integer,
        db.ForeignKey("party.id")
    )

    party = db.relationship("Party")

    districts = db.relationship(

        "District",

        secondary=tenant_district,

        back_populates="tenants"

    )


# =====================================================
# RELIGION
# =====================================================




# =====================================================
# SECT
# =====================================================

class Sect(db.Model):

    __tablename__ = "sect"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(

        db.String(120),

        nullable=False

    )

    religion = db.Column(

        db.String(50),

        nullable=False

    )


# =====================================================
# DISTRICT
# =====================================================

class District(db.Model):

    __tablename__ = "district"

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(

        db.String(10),

        unique=True,

        nullable=False

    )

    name = db.Column(

        db.String(120),

        nullable=False

    )

    tenants = db.relationship(

        "Tenant",

        secondary=tenant_district,

        back_populates="districts"

    )

    subdistricts = db.relationship(

        "SubDistrict",

        back_populates="district",

        cascade="all, delete-orphan"

    )


# =====================================================
# SUBDISTRICT
# =====================================================

class SubDistrict(db.Model):

    __tablename__ = "subdistrict"

    id = db.Column(

        db.Integer,

        primary_key=True

    )

    district_id = db.Column(

        db.Integer,

        db.ForeignKey("district.id"),

        nullable=True

    )

    name = db.Column(

        db.String(120),

        nullable=False

    )

    district = db.relationship(

        "District",

        back_populates="subdistricts"

    )

    sect_allocations = db.relationship(

        "SubdistrictSectSeat",

        back_populates="subdistrict",

        cascade="all, delete-orphan"

    )
    description = db.Column(
        db.String(255),
        nullable=True
    )


# =====================================================
# SEAT ALLOCATION
# =====================================================

class SubdistrictSectSeat(db.Model):

    __tablename__ = "subdistrict_sect_seat"

    id = db.Column(

        db.Integer,

        primary_key=True

    )

    subdistrict_id = db.Column(

        db.Integer,

        db.ForeignKey("subdistrict.id"),

        nullable=False

    )

    sect_id = db.Column(

        db.Integer,

        db.ForeignKey("sect.id"),

        nullable=False

    )

    seats = db.Column(

        db.Integer,

        nullable=False

    )

    subdistrict = db.relationship(

        "SubDistrict",

        back_populates="sect_allocations"

    )

    sect = db.relationship(

        "Sect"

    )

    __table_args__ = (

        db.UniqueConstraint(

            "subdistrict_id",

            "sect_id"

        ),

    )
class BallotPen(db.Model):

    __tablename__ = "ballot_pen"

    id = Column(Integer, primary_key=True)

    serial_number = Column(
        String(120),
        unique=True,
        nullable=False
    )

    district_id = Column(
        Integer,
        ForeignKey("district.id"),
        nullable=False
    )

    subdistrict_id = Column(
        Integer,
        ForeignKey("subdistrict.id"),
        nullable=False
    )

    sect_id = Column(
        Integer,
        ForeignKey("sect.id"),
        nullable=False
    )