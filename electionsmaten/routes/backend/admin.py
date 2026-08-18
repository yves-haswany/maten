from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.security import generate_password_hash
import json
from ...db.tenant_db import create_database
from ...services.tenant_initializer import populate_tenant_database
import os
import pandas as pd
from sqlalchemy.orm import joinedload, contains_eager
from ... import db
import gc
import time
from ...models.master_models import (
    Party,
    Tenant,
    District,
    SubDistrict,
    Sect,
    SubdistrictSectSeat,
    User, BallotPen, BallotPenSect,
    PollingCenter, Room,Elector
)

from werkzeug.utils import secure_filename
from electionsmaten.db.tenant_engine import (
    TENANT_ENGINES,
    TENANT_SESSIONS,
)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# =========================
# ADMIN GUARD
# =========================

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


# =========================
# DASHBOARD
# =========================

@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    return render_template("admin/dashboard.html")


# =========================
# DISTRICT
# =========================

@admin_bp.route("/create-district", methods=["GET", "POST"])
def create_district():

    if session.get("role") != "admin":
        return redirect(url_for("auth.login"))

    if request.method == "POST":

        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()

        if not code or not name:
            flash("District code and name are required.")
            return redirect(url_for("admin.create_district"))

        exists = District.query.filter_by(code=code).first()

        if exists:
            flash("District code already exists.")
            return redirect(url_for("admin.create_district"))

        district = District(code=code, name=name)
        db.session.add(district)
        db.session.flush()

        payload = request.form.get("data")

        if payload:
            try:
                payload = json.loads(payload)
            except Exception:
                flash("Invalid district data.")
                return redirect(url_for("admin.create_district"))

            for sub_data in payload:

                sub = SubDistrict.query.get(sub_data["subdistrict_id"])
                if not sub:
                    continue

                # ✅ FIX: proper relationship assignment
                sub.district = district

                db.session.flush()

                SubdistrictSectSeat.query.filter_by(
                    subdistrict_id=sub.id
                ).delete()

                for seat in sub_data.get("sects", []):

                    db.session.add(SubdistrictSectSeat(
                        subdistrict=sub,
                        sect_id=seat["sect_id"],
                        seats=seat["seats"]
                    ))

        db.session.commit()

        flash("District created successfully.")
        return redirect(url_for("admin.create_district"))

    # ----------------------------
    # FIX: force fresh loading
    # ----------------------------
    districts_db = District.query.order_by(District.code).all()
    db.session.expire_all()

    districts = []

    for district in districts_db:

        district_json = {
            "id": district.id,
            "code": district.code,
            "name": district.name,
            "subdistricts": []
        }

        for sub in district.subdistricts:

            district_json["subdistricts"].append({
                "id": sub.id,
                "name": sub.name,
                "total_seats": sub.total_seats,
                "sects": [
                    {
                        "id": a.sect.id,
                        "name": a.sect.name,
                        "seats": a.seats
                    }
                    for a in sub.sect_allocations
                ]
            })

        districts.append(district_json)

    available_subdistricts = [
        {"id": s.id, "name": s.name}
        for s in SubDistrict.query.order_by(SubDistrict.name).all()
    ]

    sects = [
        {"id": s.id, "name": s.name}
        for s in Sect.query.order_by(Sect.name).all()
    ]

    return render_template(
        "admin/create_district.html",
        districts=districts,
        subdistricts=available_subdistricts,
        sects=sects
    )


@admin_bp.route("/districts")
@admin_required
def view_districts():
    return render_template("admin/view_districts.html", districts=District.query.all())


@admin_bp.route("/district/edit/<int:district_id>", methods=["POST"])
def edit_district(district_id):

    if session.get("role") != "admin":
        return redirect(url_for("auth.login"))

    district = District.query.get_or_404(district_id)

    code = request.form.get("code", "").strip()
    name = request.form.get("name", "").strip()

    if not code or not name:
        flash("District code and name are required.")
        return redirect(url_for("admin.create_district"))

    duplicate = District.query.filter(
        District.code == code,
        District.id != district.id
    ).first()

    if duplicate:
        flash("Another district already uses this code.")
        return redirect(url_for("admin.create_district"))

    district.code = code
    district.name = name

    payload = request.form.get("data")

    if payload:

        try:
            payload = json.loads(payload)
        except Exception:
            flash("Invalid district data.")
            return redirect(url_for("admin.create_district"))

        # ----------------------------
        # FIX: properly detach subdistricts
        # ----------------------------
        for sub in list(district.subdistricts):
            sub.district = None

        db.session.flush()

        for sub_data in payload:

            sub = SubDistrict.query.get(sub_data["subdistrict_id"])
            if not sub:
                continue

            # FIX: relationship assignment (NOT raw FK only)
            sub.district = district

            db.session.flush()

            SubdistrictSectSeat.query.filter_by(
                subdistrict_id=sub.id
            ).delete()

            for seat in sub_data.get("sects", []):

                db.session.add(SubdistrictSectSeat(
                    subdistrict=sub,
                    sect_id=seat["sect_id"],
                    seats=seat["seats"]
                ))

    db.session.commit()

    flash("District updated successfully.")
    return redirect(url_for("admin.create_district"))


@admin_bp.route(
    "/district/delete/<int:district_id>",
    methods=["GET", "POST"]
)
def delete_district(district_id):

    ####################################################
    # ADMIN ONLY
    ####################################################

    if session.get("role") != "admin":
        return redirect(url_for("auth.login"))

    ####################################################
    # FIND DISTRICT
    ####################################################

    district = District.query.get_or_404(district_id)

    ####################################################
    # VALIDATION
    ####################################################

    # Prevent deleting a district that is still used
    # by users.

    if User.query.filter_by(
        district_id=district.id
    ).first():

        flash(
            "Cannot delete this district because it is assigned to users."
        )

        return redirect(
            url_for("admin.create_district")
        )

    ####################################################
    # BALLOT PENS
    ####################################################

    BallotPen.query.filter_by(
        district_id=district.id
    ).delete()

    ####################################################
    # REMOVE TENANT LINKS
    ####################################################

    district.tenants.clear()

    ####################################################
    # REMOVE SUBDISTRICT LINKS
    ####################################################

    for sub in district.subdistricts:

        ###############################################
        # Remove seat allocations
        ###############################################

        SubdistrictSectSeat.query.filter_by(
            subdistrict_id=sub.id
        ).delete()

        ###############################################
        # Keep the subdistrict itself
        ###############################################

        sub.district = None

    ####################################################
    # DELETE DISTRICT
    ####################################################

    db.session.delete(district)

    ####################################################
    # SAVE
    ####################################################

    db.session.commit()

    flash(
        "District deleted successfully."
    )

    return redirect(
        url_for("admin.create_district")
    )


# =========================
# TENANT
# =========================

@admin_bp.route("/create-tenant", methods=["GET", "POST"])
@admin_required
def create_tenant():

    if request.method == "POST":

        party_name = request.form.get("party")
        username = request.form.get("username")
        password = request.form.get("password")
        district_ids = request.form.getlist("districts")

        if not all([party_name, username, password]):
            flash("Missing fields", "error")
            return redirect(url_for("admin.create_tenant"))

        # ✅ prevent duplicate username
        existing = Tenant.query.filter_by(username=username).first()
        if existing:
            flash("Username already exists", "error")
            return redirect(url_for("admin.create_tenant"))

        party = Party.query.filter_by(name=party_name).first()
        if not party:
            party = Party(name=party_name)
            db.session.add(party)
            db.session.flush()

        tenant = Tenant(
            username=username,
            password=generate_password_hash(password),
            party_id=party.id,
            db_name=f"tenant_{username.lower()}"
        )

        db.session.add(tenant)
        db.session.flush()
        user = User(
            username=username,
            password=tenant.password,      # reuse the same hash
            role="tenant",
            tenant_id=tenant.id
        )

        db.session.add(user)
        for d_id in district_ids:
            district = District.query.get(int(d_id))
            if district:
                tenant.districts.append(district)
        db.session.commit()

        create_database(tenant.db_name)
        populate_tenant_database(tenant.id)

        db.session.commit()

        flash("Tenant created", "success")
        return redirect(url_for("admin.create_tenant"))

    return render_template(
        "admin/create_party.html",
        districts=District.query.all(),
        tenants=Tenant.query.all()
    )


@admin_bp.route("/tenants")
@admin_required
def view_tenants():
    return render_template("admin/view_tenants.html", tenants=Tenant.query.all())


@admin_bp.route("/edit-tenant/<int:tenant_id>", methods=["GET", "POST"])
@admin_required
def edit_tenant(tenant_id):

    tenant = Tenant.query.get_or_404(tenant_id)

    if request.method == "POST":

        tenant.username = request.form.get("username")

        password = request.form.get("password")
        if password:
            tenant.password = generate_password_hash(password)

        party_name = request.form.get("party")

        party = Party.query.filter_by(name=party_name).first()
        if not party:
            party = Party(name=party_name)
            db.session.add(party)
            db.session.flush()

        tenant.party_id = party.id

        tenant.districts = []

        for d_id in request.form.getlist("districts"):
            district = District.query.get(int(d_id))
            if district:
                tenant.districts.append(district)

        db.session.commit()

        flash("Tenant updated", "success")
        return redirect(url_for("admin.view_tenants"))

    return render_template(
        "admin/edit_tenant.html",
        tenant=tenant,
        districts=District.query.all()
    )


import os


@admin_bp.route("/delete-tenant/<int:tenant_id>", methods=["POST"])
@admin_required
def delete_tenant(tenant_id):

    print("DELETE TENANT ROUTE CALLED", tenant_id)

    tenant = Tenant.query.get_or_404(tenant_id)

    party = tenant.party
    db_name = tenant.db_name

    try:

        ####################################################
        # Delete users
        ####################################################

        users = User.query.filter_by(
            tenant_id=tenant.id
        ).all()

        for user in users:
            db.session.delete(user)

        db.session.flush()

        ####################################################
        # Delete tenant
        ####################################################

        db.session.delete(tenant)
        db.session.flush()

        ####################################################
        # Delete party if empty
        ####################################################

        if party and len(party.tenants) == 0:
            db.session.delete(party)

        db.session.commit()

        ####################################################
        # Close tenant scoped session
        ####################################################

        tenant_session = TENANT_SESSIONS.pop(
            db_name,
            None
        )

        if tenant_session is not None:
            tenant_session.remove()

        ####################################################
        # Dispose engine
        ####################################################

        tenant_engine = TENANT_ENGINES.pop(
            db_name,
            None
        )

        if tenant_engine is not None:
            tenant_engine.dispose()

        ####################################################
        # Force release of SQLite handles
        ####################################################

        gc.collect()

        ####################################################
        # Delete tenant database
        ####################################################

        db_path = os.path.join(
            current_app.instance_path,
            f"{db_name}.db"
        )

        if os.path.exists(db_path):

            deleted = False

            for _ in range(10):

                try:
                    os.remove(db_path)
                    deleted = True
                    break

                except PermissionError:
                    time.sleep(0.25)

            if not deleted:

                flash(
                    "Tenant was removed, but the database file is still in use. "
                    "Stop the application and delete the file manually.",
                    "warning"
                )

                return redirect(
                    url_for("admin.create_tenant")
                )

        flash(
            "Tenant deleted successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print("DELETE TENANT ERROR:", repr(e))

        flash(
            f"Error deleting tenant: {e}",
            "danger"
        )

    return redirect(
        url_for("admin.create_tenant")
    )


# =========================
# SECTS
# =========================

@admin_bp.route("/create-sect", methods=["GET", "POST"])
@admin_required
def create_sect():

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        religion = request.form.get("religion")

        if not name:
            flash("Name is required", "error")
            return redirect(url_for("admin.create_sect"))

        db.session.add(Sect(name=name, religion=religion))
        db.session.commit()

        return redirect(url_for("admin.create_sect"))

    # ✅ MUST BE SERIALIZED
    sects = [
        {
            "id": s.id,
            "name": s.name,
            "religion": s.religion
        }
        for s in Sect.query.all()
    ]

    return render_template(
        "admin/create_sect.html",
        sects=sects
    )


@admin_bp.route("/sect/edit/<int:sect_id>", methods=["POST"])
@admin_required
def edit_sect(sect_id):

    sect = Sect.query.get_or_404(sect_id)

    name = request.form.get("name", "").strip()
    religion = request.form.get("religion")

    if not name:
        flash("Name required", "error")
        return redirect(url_for("admin.create_sect"))

    duplicate = Sect.query.filter(
        Sect.name == name,
        Sect.id != sect_id
    ).first()

    if duplicate:
        flash("Duplicate sect name", "error")
        return redirect(url_for("admin.create_sect"))

    sect.name = name
    sect.religion = religion

    db.session.commit()

    flash("Sect updated", "success")
    return redirect(url_for("admin.create_sect"))


@admin_bp.route("/sect/delete/<int:sect_id>")
@admin_required
def delete_sect(sect_id):

    db.session.delete(Sect.query.get_or_404(sect_id))
    db.session.commit()

    flash("Sect deleted", "success")
    return redirect(url_for("admin.create_sect"))


# =========================
# SUBDISTRICT
# =========================

@admin_bp.route("/subdistrict/create", methods=["GET", "POST"])
@admin_required
def create_subdistrict():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        district_id = request.form.get("district_id")
        description = request.form.get("description", "").strip()

        district = District.query.get(district_id) if district_id else None

        if district_id and not district:
            flash("Invalid district", "error")
            return redirect(url_for("admin.create_subdistrict"))

        db.session.add(SubDistrict(
            name=name,
            district_id=district.id if district else None,
            description=description
        ))

        db.session.commit()

        flash("Subdistrict created", "success")
        return redirect(url_for("admin.create_subdistrict"))

    # ✅ SERIALIZE FOR SAFE JSON
    subdistricts = [
        {
            "id": sd.id,
            "name": sd.name,
            "description": sd.description,
            "district_id": sd.district_id,
            "district_name": sd.district.name if sd.district else None
        }
        for sd in SubDistrict.query.all()
    ]

    districts = [
        {
            "id": d.id,
            "name": d.name
        }
        for d in District.query.all()
    ]

    return render_template(
        "admin/create_subdistrict.html",
        districts=districts,
        subdistricts=subdistricts
    )


@admin_bp.route("/subdistrict/edit/<int:subdistrict_id>", methods=["GET", "POST"])
@admin_required
def edit_subdistrict(subdistrict_id):

    sd = SubDistrict.query.get_or_404(subdistrict_id)

    if request.method == "POST":

        sd.name = request.form.get("name", "").strip()
        sd.description = request.form.get("description", "").strip()

        district_id = request.form.get("district_id")
        sd.district_id = district_id if district_id else None

        db.session.commit()

        flash("Subdistrict updated", "success")
        return redirect(url_for("admin.create_subdistrict"))

    return render_template("admin/edit_subdistrict.html", subdistrict=sd)


@admin_bp.route("/subdistrict/delete/<int:subdistrict_id>", methods=["GET", "POST"])
@admin_required
def delete_subdistrict(subdistrict_id):

    db.session.delete(SubDistrict.query.get_or_404(subdistrict_id))
    db.session.commit()

    flash("Subdistrict deleted", "success")
    return redirect(url_for("admin.create_subdistrict"))


@admin_bp.route("/subdistricts")
@admin_required
def view_subdistricts():
    return render_template(
        "admin/view_subdistricts.html",
        subdistricts=SubDistrict.query.all()
    )


# =========================
# PLACEHOLDERS
# =========================

@admin_bp.route("/ballot-pens")
@admin_required
def view_ballot_pens():

    ballot_pens = (
        BallotPen.query

        ################################################
        # JOINS USED FOR SORTING
        ################################################
        .join(BallotPen.district)
        .join(BallotPen.subdistrict)
        .join(BallotPen.polling_center)
        .outerjoin(BallotPen.room)

        ################################################
        # TELL SQLALCHEMY TO USE THE JOINS ABOVE
        ################################################
        .options(
            contains_eager(BallotPen.district),
            contains_eager(BallotPen.subdistrict),
            contains_eager(BallotPen.polling_center),
            contains_eager(BallotPen.room),

            joinedload(BallotPen.sects)
                .joinedload(BallotPenSect.sect)
        )

        ################################################
        # SORTING
        ################################################
        .order_by(
            District.name.asc(),
            SubDistrict.name.asc(),
            BallotPen.village.asc(),
            PollingCenter.name.asc(),
            Room.name.asc(),
            BallotPen.serial_number.asc()
        )

        .all()
    )

    return render_template(
        "admin/view_ballot_pens.html",
        ballot_pens=ballot_pens
    )


@admin_bp.route("/electors")
@admin_required
def view_electors():

    electors = (
        Elector.query
        .join(Elector.district)
        .join(Elector.subdistrict)
        .options(
            joinedload(Elector.birth_sect),
            joinedload(Elector.current_sect)
        )
        .order_by(
            District.name.asc(),
            SubDistrict.name.asc(),
            Elector.municipality.asc(),
            Elector.register_number.asc()
        )
        .all()
    )

    return render_template(
        "admin/view_electors.html",
        electors=electors
    )


@admin_bp.route("/sects")
@admin_required
def view_sects():
    return render_template(
        "admin/view_sects.html",
        sects=Sect.query.all()
    )

############################################################
# HELPER FUNCTIONS
############################################################




############################################################
# HELPER FUNCTIONS
############################################################

def get_sect(name):

    name = " ".join(str(name).strip().split())

    aliases = {
        "سريان ارثوذكس": "أقليات",
        "سريان كاثوليك": "أقليات",
        "اشوري ارثوذكس": "أقليات",
        "كلدان": "أقليات",
        "كلدان كاثوليك": "أقليات",
        "قبطي ارثوذكس": "أقليات",
        "لاتيني": "أقليات",
        "اسرائيلي": "أقليات",
        "نسطوري": "أقليات",
        "انجيلي (بروتستانت)": "أقليات",
        "ارمن بروتستانت": "أقليات",
        "--":"أقليات",
        "اشوري":"أقليات",
        "قبطي":"أقليات",
        "مختلط": "مختلف",
        "لا ديني": "مختلف",
    }

    name = aliases.get(name, name)

    sect = (
        Sect.query.filter(
            db.or_(
                Sect.name == name,
                Sect.religion == name
            )
        ).first()
    )

    if not sect:
        raise Exception(f"Sect not found: {name}")

    return sect


############################################################
# ROUTES
############################################################


@admin_bp.route("/upload-electors", methods=["GET", "POST"])
@admin_required
def upload_electors():
    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            flash("No file selected", "error")
            return redirect(url_for("admin.upload_electors"))

        try:
            ####################################################
            # READ EXCEL
            ####################################################
            df = pd.read_excel(file)
            df.columns = df.columns.astype(str).str.strip()

            ####################################################
            # REQUIRED COLUMNS
            ####################################################
            required_columns = [
                ".Counter",
                "Name",
                "Surname",
                "Family",
                "Father",
                "Mother",
                "Gender",
                "DOB",
                "Da2ira",
                "Kazaa",
                "Balda",
                "Sect",
                "Rite",
                "Register",
                "RegisterN",
                "BallotNb",
                "Dead",
                "Registered",
            ]

            missing = [c for c in required_columns if c not in df.columns]

            if missing:
                raise Exception("Missing columns: " + ", ".join(missing))

            ####################################################
            # IMPORT ROWS
            ####################################################
            for _, row in df.iterrows():
                ################################################
                # DISTRICT
                ################################################
                district_name = str(row["Da2ira"]).strip()
                district_aliases = {
                    "جبل لبنان الأولى": "دائرة جبل لبنان الأولى",
                    "جبل لبنان الثانية": "دائرة جبل لبنان الثانية",
                    "جبل لبنان الثالثة": "دائرة جبل لبنان الثالثة",
                    "جبل لبنان الرابعة": "دائرة جبل لبنان الرابعة",
                    "بيروت الأولى": "دائرة بيروت الأولى",
                    "بيروت الثانية": "دائرة بيروت الثانية",
                    "الشمال الأولى": "دائرة الشمال الأولى",
                    "الشمال الثانية": "دائرة الشمال الثانية",
                    "الشمال الثالثة": "دائرة الشمال الثالثة",
                    "البقاع الأولى": "دائرة البقاع الأولى",
                    "البقاع الثانية": "دائرة البقاع الثانية",
                    "البقاع الثالثة": "دائرة البقاع الثالثة",
                    "الجنوب الأولى": "دائرة الجنوب الأولى",
                    "الجنوب الثانية": "دائرة الجنوب الثانية",
                    "الجنوب الثالثة": "دائرة الجنوب الثالثة",
                }
                district_name = district_aliases.get(district_name, district_name)
                district = District.query.filter_by(name=district_name).first()

                if not district:
                    raise Exception(f"District not found: {district_name}")

                ################################################
                # SUBDISTRICT
                ################################################
                subdistrict_name = str(row["Kazaa"]).strip()
                subdistrict = (
                    SubDistrict.query
                    .filter_by(district_id=district.id, name=subdistrict_name)
                    .first()
                )

                if not subdistrict:
                    raise Exception(f"Subdistrict not found: {subdistrict_name}")

                ################################################
                # BIRTH SECT
                ################################################
                birth_sect = get_sect(row["Sect"])

                ################################################
                # CURRENT SECT (RITE)
                ################################################
                current_sect = get_sect(row["Rite"])

                ################################################
                # DOB
                ################################################
                dob = None
                if pd.notna(row["DOB"]):
                    dob = pd.to_datetime(row["DOB"]).date()

                ################################################
                # DEAD
                ################################################
                dead_value = str(row["Dead"]).strip().lower()
                is_dead = dead_value in ("1", "true", "yes", "نعم")

                ################################################
                # REGISTERED
                ################################################
                registered_value = str(row["Registered"]).strip().lower()
                registered = registered_value in ("1", "true", "yes", "نعم")

                ################################################
                # FIND EXISTING ELECTOR
                ################################################
                elector_id = str(row[".Counter"]).strip()
                elector = Elector.query.filter_by(elector_id=elector_id).first()

                ################################################
                # CREATE IF NOT EXISTS
                ################################################
                if not elector:
                    elector = Elector(elector_id=elector_id)
                    db.session.add(elector)

                ################################################
                # UPDATE DATA
                ################################################
                elector.first_name = str(row["Name"]).strip()
                elector.surname = str(row["Surname"]).strip()
                elector.family_name = str(row["Family"]).strip()
                elector.father_name = str(row["Father"]).strip()
                elector.mother_name = str(row["Mother"]).strip()
                elector.gender = str(row["Gender"]).strip()
                elector.dob = dob
                elector.birth_sect_id = birth_sect.id if birth_sect else None
                elector.current_sect_id = current_sect.id if current_sect else None
                elector.district_id = district.id
                elector.subdistrict_id = subdistrict.id
                elector.municipality = str(row["Balda"]).strip()
                elector.register = str(row["Register"]).strip()
                elector.register_number = int(row["RegisterN"])

                # Handle ballot number
                if pd.notna(row["BallotNb"]):
                    ballot_number = int(row["BallotNb"])
                    elector.ballot_number = ballot_number
                    ballot_pen = BallotPen.query.filter_by(code=str(ballot_number)).first()
                    if ballot_pen:
                        elector.ballot_pen_id = ballot_pen.id
                    else:
                        elector.ballot_pen_id = None
                else:
                    elector.ballot_number = None
                    elector.ballot_pen_id = None

                elector.is_dead = is_dead
                elector.registered = registered

            ####################################################
            # SAVE
            ####################################################
            db.session.commit()
            flash("Electors uploaded successfully.", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Upload failed: {e}", "error")

        return redirect(url_for("admin.upload_electors"))

    return render_template(
        "admin/upload_electors.html",
        districts=District.query.order_by(District.name).all(),
    )


@admin_bp.route("/ballot-pens/upload", methods=["GET", "POST"])
@admin_required
def upload_ballot_pens():

    if request.method == "POST":

        ballot_file = request.files.get("ballot_pens_file")

        if not ballot_file or ballot_file.filename == "":
            flash("Please select an Excel file.", "error")
            return redirect(url_for("admin.upload_ballot_pens"))

        try:

            ####################################################
            # READ EXCEL
            ####################################################

            df = pd.read_excel(ballot_file)

            df.columns = (
                df.columns
                .astype(str)
                .str.strip()
            )

            ####################################################
            # REQUIRED COLUMNS
            ####################################################

            required_columns = [
                "Da2ira",
                "Kazaa",
                "Balda",
                "Markaz",
                "ChamberNb",
                "KalamNb",
                "Gender",
                "From Register",
                "To Register",
                "Sect",
                "UNWeb"
            ]

            missing = [
                c for c in required_columns
                if c not in df.columns
            ]

            if missing:
                raise Exception(
                    "Missing columns: "
                    + ", ".join(missing)
                )

            ####################################################
            # IMPORT ROWS
            ####################################################

            for _, row in df.iterrows():

                ################################################
                # DISTRICT
                ################################################

                district_name = str(
                    row["Da2ira"]
                ).strip()
                district_aliases = {
                    "جبل لبنان الثانية": "دائرة جبل لبنان الثانية",
                    "جبل لبنان الأولى": "دائرة جبل لبنان الأولى",
                    "بيروت الأولى": "دائرة بيروت الأولى",
                    "بيروت الثانية": "دائرة بيروت الثانية",
                    "الشمال الأولى": "دائرة الشمال الأولى",
                    "الشمال الثانية": "دائرة الشمال الثانية",
                    "الشمال الثالثة": "دائرة الشمال الثالثة",
                    "البقاع الأولى": "دائرة البقاع الأولى",
                    "البقاع الثانية": "دائرة البقاع الثانية",
                    "البقاع الثالثة": "دائرة البقاع الثالثة",
                    "الجنوب الأولى": "دائرة الجنوب الأولى",
                    "الجنوب الثانية": "دائرة الجنوب الثانية",
                    "الجنوب الثالثة": "دائرة الجنوب الثالثة",
                    "النبطية": "دائرة النبطية"
                }
                district_name = district_aliases.get(
                    district_name,
                    district_name
                )

                district = (
                    District.query
                    .filter_by(name=district_name)
                    .first()
                )

                if not district:
                    raise Exception(
                        f"District not found: {district_name}"
                    )

                ################################################
                # SUBDISTRICT
                ################################################

                subdistrict_name = str(
                    row["Kazaa"]
                ).strip()

                subdistrict = (
                    SubDistrict.query
                    .filter_by(
                        district_id=district.id,
                        name=subdistrict_name
                    )
                    .first()
                )

                if not subdistrict:
                    raise Exception(
                        f"Subdistrict not found: {subdistrict_name}"
                    )

                ################################################
                # POLLING CENTER
                ################################################

                polling_center_name = str(
                    row["Markaz"]
                ).strip()

                polling_center = (
                    PollingCenter.query
                    .filter_by(
                        district_id=district.id,
                        subdistrict_id=subdistrict.id,
                        name=polling_center_name
                    )
                    .first()
                )

                if not polling_center:

                    polling_center = PollingCenter(
                        district_id=district.id,
                        subdistrict_id=subdistrict.id,
                        name=polling_center_name
                    )

                    db.session.add(polling_center)
                    db.session.flush()

                ################################################
                # ROOM
                ################################################

                room_number = str(
                    row["ChamberNb"]
                ).strip()

                room_name = (
                    f" غرفة رقم {room_number}"
                )

                room = (
                    Room.query
                    .filter_by(
                        polling_center_id=polling_center.id,
                        name=room_name
                    )
                    .first()
                )

                if not room:

                    room = Room(
                        polling_center_id=polling_center.id,
                        name=room_name
                    )

                    db.session.add(room)
                    db.session.flush()

                ################################################
                # BALLOT PEN
                ################################################

                serial_number = str(
                    row["KalamNb"]
                ).strip()

                code = str(row["UNWeb"]).strip()

                pens = (
                    BallotPen.query
                    .filter_by(
                        code=code
                    )
                    .all()
                )

                ballot_pen = None

                for pen in pens:
                    if (
                        pen.village == str(row["Balda"]).strip()
                        and
                        pen.gender_type == str(row["Gender"]).strip()
                        and
                        pen.polling_center_id == polling_center.id
                        and
                        pen.room_id == room.id
                    ):
                        ballot_pen = pen
                        break

                if not ballot_pen:

                    ballot_pen = BallotPen(
                        serial_number=serial_number,
                        code=code,
                        district_id=district.id,
                        subdistrict_id=subdistrict.id,
                        village=str(row["Balda"]).strip(),
                        polling_center_id=polling_center.id,
                        room_id=room.id,
                        gender_type=str(row["Gender"]).strip()
                    )

                    db.session.add(ballot_pen)
                    db.session.flush()

                else:

                    ballot_pen.village = str(
                        row["Balda"]
                    ).strip()
                    ballot_pen.code = str(
                        row["UNWeb"]
                    ).strip()
                    ballot_pen.polling_center_id = polling_center.id
                    ballot_pen.room_id = room.id
                    ballot_pen.gender_type = str(
                        row["Gender"]
                    ).strip()

                ################################################
                # SECT
                ################################################

                sect_name = str(
                    row["Sect"]
                ).strip()
                sect_name = " ".join(sect_name.split())
                sect_aliases = {
                    "سريان ارثوذكس": "أقليات",
                    "سريان كاثوليك": "أقليات",
                    "اشوري ارثوذكس": "أقليات",
                    "كلدان": "أقليات",
                    "لاتين": "أقليات",
                    "اسرائيلي": "أقليات",
                    "كلدان كاثوليك": "أقليات",
                    "قبطي ارثوذكس": "أقليات",
                    "نسطوري": "أقليات",
                    "مختلط": "مختلف",
                    "لا ديني": "مختلف",
                }
                sect_name = sect_aliases.get(sect_name, sect_name)
                if sect_name in sect_aliases:
                    sect_name = "اقليات"

                sect = Sect.query.filter(
                    db.or_(
                        Sect.name == sect_name,
                        Sect.religion == sect_name
                    )
                ).first()

                if not sect:
                    raise Exception(
                        f"Sect not found: {sect_name}"
                    )

                ################################################
                # REGISTERS
                ################################################

                register_from = None
                register_to = None
                register_count = None

                if pd.notna(row["From Register"]):
                    register_from = int(row["From Register"])

                if pd.notna(row["To Register"]):
                    register_to = int(row["To Register"])

                if (
                    register_from is not None
                    and
                    register_to is not None
                ):
                    register_count = (
                        register_to
                        - register_from
                        + 1
                    )

                ################################################
                # BALLOT PEN SECT
                ################################################

                exists = (
                    BallotPenSect.query
                    .filter_by(
                        ballot_pen_id=ballot_pen.id,
                        sect_id=sect.id,
                        register_from=register_from,
                        register_to=register_to
                    )
                    .first()
                )

                if not exists:

                    db.session.add(
                        BallotPenSect(
                            ballot_pen_id=ballot_pen.id,
                            sect_id=sect.id,
                            register_from=register_from,
                            register_to=register_to,
                            register_count=register_count
                        )
                    )

            ####################################################
            # SAVE
            ####################################################

            db.session.commit()

            flash(
                "Ballot pens uploaded successfully.",
                "success"
            )

            return redirect(
                url_for("admin.view_ballot_pens")
            )

        except Exception as e:

            db.session.rollback()

            flash(
                f"Upload failed: {e}",
                "error"
            )

            return redirect(
                url_for("admin.upload_ballot_pens")
            )

    return render_template(
        "admin/create_ballot_pen.html"
    )


@admin_bp.route(
    "/ballot-pens/edit/<int:ballot_pen_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_ballot_pen(ballot_pen_id):

    ballot_pen = BallotPen.query.get_or_404(
        ballot_pen_id
    )

    districts = (
        District.query
        .order_by(District.name)
        .all()
    )

    if request.method == "POST":

        ballot_pen.serial_number = request.form.get(
            "serial_number"
        )

        ballot_pen.district_id = request.form.get(
            "district_id"
        )

        ballot_pen.subdistrict_id = request.form.get(
            "subdistrict_id"
        )

        ballot_pen.village = request.form.get(
            "village"
        )

        ballot_pen.polling_center = request.form.get(
            "polling_center"
        )

        ballot_pen.gender_type = request.form.get(
            "gender_type"
        )

        ballot_pen.voters_count = request.form.get(
            "voters_count"
        )

        ballot_pen.notes = request.form.get(
            "notes"
        )

        db.session.commit()

        flash(
            "Ballot pen updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "admin.view_ballot_pens"
            )
        )

    return render_template(
        "admin/edit_ballot_pen.html",
        ballot_pen=ballot_pen,
        districts=districts
    )


@admin_bp.route(
    "/ballot-pens/delete/<int:ballot_pen_id>",
    methods=["POST", "GET"]
)
@admin_required
def delete_ballot_pen(ballot_pen_id):

    ballot_pen = BallotPen.query.get_or_404(
        ballot_pen_id
    )

    ####################################################
    # SAVE RELATED OBJECTS
    ####################################################

    room = ballot_pen.room
    polling_center = ballot_pen.polling_center

    ####################################################
    # DELETE LINKED SECTS
    ####################################################

    BallotPenSect.query.filter_by(
        ballot_pen_id=ballot_pen.id
    ).delete()

    ####################################################
    # DELETE BALLOT PEN
    ####################################################

    db.session.delete(ballot_pen)
    db.session.flush()

    ####################################################
    # DELETE ROOM IF EMPTY
    ####################################################

    if room:

        remaining_pens = BallotPen.query.filter_by(
            room_id=room.id
        ).count()

        if remaining_pens == 0:
            db.session.delete(room)
            db.session.flush()

    ####################################################
    # DELETE POLLING CENTER IF EMPTY
    ####################################################

    if polling_center:

        remaining_rooms = Room.query.filter_by(
            polling_center_id=polling_center.id
        ).count()

        remaining_pens = BallotPen.query.filter_by(
            polling_center_id=polling_center.id
        ).count()

        if remaining_rooms == 0 and remaining_pens == 0:
            db.session.delete(polling_center)

    ####################################################
    # SAVE
    ####################################################

    db.session.commit()

    flash(
        "Ballot pen deleted successfully.",
        "success"
    )

    return redirect(
        url_for("admin.view_ballot_pens")
    )


# =========================
# POLLING CENTERS
# =========================

@admin_bp.route(
    "/polling-centers/create",
    methods=["GET", "POST"]
)
@admin_required
def create_polling_center():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        district_id = request.form.get(
            "district_id"
        )

        subdistrict_id = request.form.get(
            "subdistrict_id"
        )

        address = request.form.get(
            "address"
        )

        if not name:

            flash(
                "Polling center name required.",
                "error"
            )

            return redirect(
                url_for(
                    "admin.create_polling_center"
                )
            )

        center = PollingCenter(

            name=name,

            district_id=district_id,

            subdistrict_id=subdistrict_id,

            address=address
        )

        db.session.add(center)

        db.session.commit()

        flash(
            "Polling center created successfully.",
            "success"
        )

        return redirect(
            url_for(
                "admin.view_polling_centers"
            )
        )

    return render_template(
        "admin/create_polling_center.html",
        districts=District.query.all(),
        subdistricts=SubDistrict.query.all()
    )


@admin_bp.route(
    "/polling-centers"
)
@admin_required
def view_polling_centers():

    centers = (
        PollingCenter.query
        .order_by(
            PollingCenter.name
        )
        .all()
    )

    return render_template(
        "admin/view_polling_centers.html",
        centers=centers
    )


@admin_bp.route(
    "/polling-centers/edit/<int:center_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_polling_center(center_id):

    center = PollingCenter.query.get_or_404(
        center_id
    )

    if request.method == "POST":

        center.name = request.form.get(
            "name"
        )

        center.district_id = request.form.get(
            "district_id"
        )

        center.subdistrict_id = request.form.get(
            "subdistrict_id"
        )

        center.address = request.form.get(
            "address"
        )

        db.session.commit()

        flash(
            "Polling center updated.",
            "success"
        )

        return redirect(
            url_for(
                "admin.view_polling_centers"
            )
        )

    return render_template(
        "admin/edit_polling_center.html",
        center=center,
        districts=District.query.all(),
        subdistricts=SubDistrict.query.all()
    )


@admin_bp.route(
    "/polling-centers/delete/<int:center_id>",
    methods=["POST"]
)
@admin_required
def delete_polling_center(center_id):

    center = PollingCenter.query.get_or_404(
        center_id
    )

    if center.rooms:

        flash(
            "Cannot delete polling center. Remove rooms first.",
            "error"
        )

        return redirect(
            url_for(
                "admin.view_polling_centers"
            )
        )

    db.session.delete(
        center
    )

    db.session.commit()

    flash(
        "Polling center deleted.",
        "success"
    )

    return redirect(
        url_for(
            "admin.view_polling_centers"
        )
    )


@admin_bp.route(
    "/polling-centers/<int:center_id>/rooms/create",
    methods=["GET", "POST"]
)
@admin_required
def create_polling_room(center_id):

    center = PollingCenter.query.get_or_404(
        center_id
    )

    if request.method == "POST":

        name = request.form.get(
            "name"
        )

        room = Room(

            name=name,

            polling_center_id=center.id
        )

        db.session.add(room)

        db.session.commit()

        flash(
            "Room created.",
            "success"
        )

        return redirect(
            url_for(
                "admin.view_polling_rooms",
                center_id=center.id
            )
        )

    return render_template(
        "admin/create_polling_room.html",
        center=center
    )


@admin_bp.route(
    "/polling-centers/<int:center_id>/rooms"
)
@admin_required
def view_polling_rooms(center_id):

    center = PollingCenter.query.get_or_404(
        center_id
    )

    return render_template(
        "admin/view_polling_rooms.html",
        center=center,
        rooms=center.rooms
    )


@admin_bp.route(
    "/polling-rooms/edit/<int:room_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_polling_room(room_id):

    room = Room.query.get_or_404(
        room_id
    )

    if request.method == "POST":

        room.name = request.form.get(
            "name"
        )

        db.session.commit()

        flash(
            "Room updated.",
            "success"
        )

        return redirect(
            url_for(
                "admin.view_polling_rooms",
                center_id=room.polling_center_id
            )
        )

    return render_template(
        "admin/edit_polling_room.html",
        room=room
    )


@admin_bp.route(
    "/polling-rooms/delete/<int:room_id>",
    methods=["POST"]
)
@admin_required
def delete_polling_room(room_id):

    room = Room.query.get_or_404(
        room_id
    )

    if room.ballot_pens:

        flash(
            "Cannot delete room. Ballot pens are assigned.",
            "error"
        )

        return redirect(
            url_for(
                "admin.view_polling_rooms",
                center_id=room.polling_center_id
            )
        )

    center_id = room.polling_center_id

    db.session.delete(
        room
    )

    db.session.commit()

    flash(
        "Room deleted.",
        "success"
    )

    return redirect(
        url_for(
            "admin.view_polling_rooms",
            center_id=center_id
        )
    )


@admin_bp.route(
    "/polling-rooms/<int:room_id>/assign-ballot-pens",
    methods=["GET", "POST"]
)
@admin_required
def assign_ballot_pens(room_id):

    room = Room.query.get_or_404(
        room_id
    )

    if request.method == "POST":

        ballot_pen_ids = request.form.getlist(
            "ballot_pens"
        )

        for bp_id in ballot_pen_ids:

            ballot_pen = BallotPen.query.get(
                int(bp_id)
            )

            if ballot_pen:

                ballot_pen.room_id = room.id

                ballot_pen.polling_center_id = (
                    room.polling_center_id
                )

        db.session.commit()

        flash(
            "Ballot pens assigned successfully.",
            "success"
        )

        return redirect(
            url_for(
                "admin.view_polling_rooms",
                center_id=room.polling_center_id
            )
        )

    available_ballot_pens = (
        BallotPen.query
        .filter(
            BallotPen.room_id.is_(None)
        )
        .all()
    )

    return render_template(
        "admin/assign_ballot_pens.html",
        room=room,
        ballot_pens=available_ballot_pens
    )


@admin_bp.route(
    "/ballot-pens/remove-room/<int:ballot_pen_id>",
    methods=["POST"]
)
@admin_required
def remove_ballot_pen_room(ballot_pen_id):

    ballot_pen = BallotPen.query.get_or_404(
        ballot_pen_id
    )

    ballot_pen.room_id = None
    ballot_pen.polling_center_id = None

    db.session.commit()

    flash(
        "Ballot pen removed from room.",
        "success"
    )

    return redirect(
        url_for(
            "admin.view_ballot_pens"
        )
    )


@admin_bp.route("/ballot-pens/delete-all")
@admin_required
def delete_all_ballot_pens():

    BallotPenSect.query.delete()

    BallotPen.query.delete()

    Room.query.delete()

    PollingCenter.query.delete()

    db.session.commit()

    flash(
        "تم حذف جميع أقلام الاقتراع ومراكز الاقتراع والغرف.",
        "success"
    )

    return redirect(url_for("admin.view_ballot_pens"))
@admin_bp.route("/electors/delete-all", methods=["POST"])
@admin_required
def delete_all_electors():

    try:

        Elector.query.delete()

        db.session.commit()

        flash(
            "All electors were deleted successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Delete failed: {e}",
            "error"
        )

    return redirect(url_for("admin.view_electors"))