# master_models.py
from datetime import datetime
from .. import db


tenant_district = db.Table(
    "tenant_district",
    db.Column("tenant_id", db.Integer, db.ForeignKey("tenant.id"), primary_key=True),
    db.Column("district_id", db.Integer, db.ForeignKey("district.id"), primary_key=True),
)


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
        db.ForeignKey("tenant.id"),
        nullable=True
    )

    district_id = db.Column(
        db.Integer,
        db.ForeignKey("district.id"),
        nullable=True
    )

    ballot_pen_id = db.Column(
        db.Integer,
        nullable=True
    )


class Party(db.Model):
    __tablename__ = "party"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)


class Tenant(db.Model):
    __tablename__ = "tenant"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    # THIS is key for multi-db routing
    db_name = db.Column(db.String(255), nullable=False)

    party_id = db.Column(db.Integer, db.ForeignKey("party.id"))
    party = db.relationship("Party")

    districts = db.relationship(
        "District",
        secondary=tenant_district,
        back_populates="tenants"
    )


class District(db.Model):
    __tablename__ = "district"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)

    tenants = db.relationship(
        "Tenant",
        secondary=tenant_district,
        back_populates="districts"
    )