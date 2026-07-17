from datetime import datetime

from sqlalchemy import Enum, ForeignKey,Column,Integer,String,Date,Boolean,DateTime
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
    tenants = db.relationship(
    "Tenant",
    back_populates="party",
    cascade="all, delete"
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

    party = db.relationship(
    "Party",
    back_populates="tenants"
)

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
    ballot_pens = db.relationship(
        "BallotPenSect",
        back_populates="sect"
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

        cascade="all, delete-orphan",
        lazy = "selectin"

    )
    def __repr__(self):
        return f"<District {self.code} - {self.name}>"


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

        cascade="all, delete-orphan",
        lazy = "selectin"

    )
    description = db.Column(
        db.String(255),
        nullable=True
    )
    @property
    def total_seats(self):
        """
        Total seats assigned to this subdistrict.
        Computed from the sect allocations.
        """
        return sum(
            allocation.seats
            for allocation in self.sect_allocations
        )

    def __repr__(self):
        return f"<SubDistrict {self.name}>"



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

        "Sect",
        lazy="joined"

    )

    __table_args__ = (

        db.UniqueConstraint(

            "subdistrict_id",

            "sect_id",
            name = "uq_subdistrict_sect"

        ),

    )
    def __repr__(self):
        return (
            f"<SeatAllocation "
            f"Subdistrict={self.subdistrict_id} "
            f"Sect={self.sect_id} "
            f"Seats={self.seats}>"
        )
class BallotPen(db.Model):
    __tablename__ = "ballot_pen"

    id = db.Column(db.Integer, primary_key=True)
    code= db.Column(db.String(50), nullable=False)
    serial_number = db.Column(db.String(120), nullable=False)

    district_id = db.Column(
        db.Integer,
        db.ForeignKey("district.id"),
        nullable=False
    )

    subdistrict_id = db.Column(
        db.Integer,
        db.ForeignKey("subdistrict.id"),
        nullable=False
    )

    village = db.Column(db.String(150))

    polling_center_id = db.Column(
    db.Integer,
    db.ForeignKey("polling_centers.id"),
    nullable=False
)


    room_id = db.Column(
    db.Integer,
    db.ForeignKey("rooms.id"),
    nullable=True
)


    polling_center = db.relationship(
    "PollingCenter",
    back_populates="ballot_pens"
)


    room = db.relationship(
    "Room",
    back_populates="ballot_pens"
)

    gender_type = db.Column(db.String(20))

    voters_count = db.Column(db.Integer)

    notes = db.Column(db.String(255))

    sects = db.relationship(
        "BallotPenSect",
        backref="ballot_pen",
        cascade="all, delete-orphan"
    )
    district = db.relationship(
    "District",
    backref="ballot_pens",
    lazy="joined"
)

    subdistrict = db.relationship(
    "SubDistrict",
    backref="ballot_pens",
    lazy="joined"
)
class BallotPenSect(db.Model):
    __tablename__ = "ballot_pen_sect"

    id = db.Column(db.Integer, primary_key=True)

    ballot_pen_id = db.Column(
        db.Integer,
        db.ForeignKey("ballot_pen.id"),
        nullable=False
    )

    sect_id = db.Column(
        db.Integer,
        db.ForeignKey("sect.id"),
        nullable=False
    )
    sect = db.relationship(
        "Sect",
        back_populates="ballot_pens"
    )
    register_from = db.Column(
        db.Integer
    )

    register_to = db.Column(
        db.Integer
    )

    register_count = db.Column(
        db.Integer
    )
class GenderType(Enum):
    MIXED = "Mixed"
    MEN = "Men"
    WOMEN = "Women"
class PollingCenter(db.Model):

    __tablename__ = "polling_centers"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(200),
        nullable=False
    )

    code = db.Column(
        db.String(50),
        unique=True
    )

    district_id = db.Column(
        db.Integer,
        db.ForeignKey("district.id"),
        nullable=False
    )

    subdistrict_id = db.Column(
        db.Integer,
        db.ForeignKey("subdistrict.id"),
        nullable=False
    )


    rooms = db.relationship(
        "Room",
        back_populates="polling_center",
        cascade="all, delete-orphan"
    )
    ballot_pens = db.relationship(
    "BallotPen",
    back_populates="polling_center",
    cascade="all, delete-orphan"
)
class Room(db.Model):

    __tablename__ = "rooms"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    name = db.Column(
        db.String(100),
        nullable=False
    )


    polling_center_id = db.Column(
        db.Integer,
        db.ForeignKey("polling_centers.id"),
        nullable=False
    )


    polling_center = db.relationship(
        "PollingCenter",
        back_populates="rooms"
    )


    ballot_pens = db.relationship(
        "BallotPen",
        back_populates="room"
    )
class Elector(db.Model):

    __tablename__ = "elector"

    id = db.Column(db.Integer, primary_key=True)


    elector_id = db.Column(

        String(120),

        nullable=False

    )


    first_name = db.Column(db.String(120))

    surname = db.Column(db.String(120))

    family_name = db.Column(db.String(120))

    father_name = db.Column(db.String(120))

    mother_name = db.Column(db.String(120))


    gender = db.Column(db.String(10))

    dob = db.Column(db.Date)

    birth_sect_id = db.Column(
    db.Integer,
    db.ForeignKey("sect.id")
)

    current_sect_id = db.Column(
    db.Integer,
    db.ForeignKey("sect.id")
)

    birth_sect = db.relationship(
    "Sect",
    foreign_keys=[birth_sect_id]
)

    current_sect = db.relationship(
    "Sect",
    foreign_keys=[current_sect_id]
)


    district_id = db.Column(
    db.Integer,
    db.ForeignKey("district.id"),
    nullable=False
)
    district = db.relationship("District")

    subdistrict_id = db.Column(
    db.Integer,
    db.ForeignKey("subdistrict.id"),
    nullable=False
)
    subdistrict = db.relationship("SubDistrict")


    register = db.Column(db.String(120))

    register_number = db.Column(db.Integer)


    municipality = db.Column(db.String(120))

    address = db.Column(db.String(255))


    is_dead = db.Column(db.Boolean)

    registered = db.Column(db.Boolean)


    uploaded_at = db.Column(

        db.DateTime,

        default=datetime.utcnow

    )