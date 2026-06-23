from datetime import datetime
from . import db


# =====================================================
# ASSOCIATION TABLE
# =====================================================

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
# DISTRICT
# =====================================================

class District(db.Model):

    __tablename__ = "district"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(120),
        nullable=False
    )

    tenants = db.relationship(
        "Tenant",
        secondary=tenant_district,
        back_populates="districts"
    )

    electors = db.relationship(
        "Elector",
        back_populates="district",
        cascade="all, delete-orphan"
    )


# =====================================================
# TENANT
# =====================================================

class Tenant(db.Model):

    __tablename__ = "tenant"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(100),
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
# ELECTOR
# =====================================================

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

    district = db.relationship(
        "District",
        back_populates="electors"
    )

    uploaded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =====================================================
# USER
# =====================================================

class User(db.Model):

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(120),
        unique=True
    )

    password = db.Column(
        db.String(255)
    )

    role = db.Column(
        db.String(50)
    )