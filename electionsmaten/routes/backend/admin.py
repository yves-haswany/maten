from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.security import generate_password_hash
import json

from ... import db
from ...models.master_models import (
    Party,
    Tenant,
    District,
    SubDistrict,
    Sect,
    SubdistrictSectSeat
)
from ...models.tenant_models import Elector
from werkzeug.utils import secure_filename

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
@admin_required
def create_district():

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()

        if not name or not code:
            flash("Name and code are required.", "error")
            return redirect(url_for("admin.create_district"))

        if District.query.filter_by(code=code).first():
            flash("District code already exists.", "error")
            return redirect(url_for("admin.create_district"))

        district = District(name=name, code=code)
        db.session.add(district)
        db.session.commit()

        flash("District created successfully.", "success")
        return redirect(url_for("admin.create_district"))

    subdistricts = [
        {
            "id": sd.id,
            "name": sd.name
        }
        for sd in SubDistrict.query.order_by(SubDistrict.name).all()
    ]

    sects = [
        {
            "id": s.id,
            "name": s.name
        }
        for s in Sect.query.order_by(Sect.name).all()
    ]

    return render_template(
        "admin/create_district.html",
        districts=District.query.all(),
        subdistricts=subdistricts,
        sects=sects
    )


@admin_bp.route("/districts")
@admin_required
def view_districts():
    return render_template("admin/view_districts.html", districts=District.query.all())


@admin_bp.route("/edit-district/<int:district_id>", methods=["GET", "POST"])
@admin_required
def edit_district(district_id):

    district = District.query.get_or_404(district_id)

    if request.method == "POST":

        district.name = request.form["name"]
        district.code = request.form["code"]

        payload = json.loads(request.form.get("data", "[]"))

        SubdistrictSectSeat.query.join(SubDistrict).filter(
            SubDistrict.district_id == district.id
        ).delete(synchronize_session=False)

        SubDistrict.query.filter_by(district_id=district.id).delete()
        db.session.flush()

        for sub in payload:

            subdistrict = SubDistrict(
                district_id=district.id,
                name=sub["name"],
                total_seats=sub["seats"]
            )

            db.session.add(subdistrict)
            db.session.flush()

            for sect_data in sub.get("sects", []):

                sect_name = sect_data["name"].strip().lower()

                sect = Sect.query.filter(
                    db.func.lower(Sect.name) == sect_name
                ).first()

                if not sect:
                    sect = Sect(name=sect_data["name"].strip())
                    db.session.add(sect)
                    db.session.flush()

                db.session.add(SubdistrictSectSeat(
                    district_id=district.id,
                    subdistrict_id=subdistrict.id,
                    sect_id=sect.id,
                    seats=sect_data["seats"]
                ))

        db.session.commit()

        flash("District updated", "success")
        return redirect(url_for("admin.view_districts"))

    existing = [
        {
            "name": sd.name,
            "seats": sd.total_seats,
            "sects": [
                {"name": a.sect.name, "seats": a.seats}
                for a in sd.sect_allocations
            ]
        }
        for sd in district.subdistricts
    ]

    return render_template(
        "admin/edit_district.html",
        district=district,
        existing=existing
    )


@admin_bp.route("/delete-district/<int:district_id>", methods=["POST"])
@admin_required
def delete_district(district_id):
    db.session.delete(District.query.get_or_404(district_id))
    db.session.commit()
    flash("District deleted", "success")
    return redirect(url_for("admin.view_districts"))


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

        party = Party.query.filter_by(name=party_name).first()
        if not party:
            party = Party(name=party_name)
            db.session.add(party)
            db.session.flush()

        tenant = Tenant(
            username=username,
            password=generate_password_hash(password),
            party_id=party.id
        )

        db.session.add(tenant)
        db.session.flush()

        for d_id in district_ids:
            district = District.query.get(int(d_id))
            if district:
                tenant.districts.append(district)

        db.session.commit()

        flash("Tenant created", "success")
        return redirect(url_for("admin.create_tenant"))

    return render_template(
        "admin/create_party.html",
        districts=District.query.all()
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


@admin_bp.route("/delete-tenant/<int:tenant_id>", methods=["POST"])
@admin_required
def delete_tenant(tenant_id):
    db.session.delete(Tenant.query.get_or_404(tenant_id))
    db.session.commit()
    flash("Tenant deleted", "success")
    return redirect(url_for("admin.view_tenants"))


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


@admin_bp.route("/subdistrict/edit/<int:subdistrict_id>", methods=["POST"])
@admin_required
def edit_subdistrict(subdistrict_id):

    sd = SubDistrict.query.get_or_404(subdistrict_id)

    sd.name = request.form.get("name", "").strip()
    sd.description = request.form.get("description", "").strip()

    district_id = request.form.get("district_id")
    sd.district_id = district_id if district_id else None

    db.session.commit()

    flash("Subdistrict updated", "success")
    return redirect(url_for("admin.create_subdistrict"))


@admin_bp.route("/subdistrict/delete/<int:subdistrict_id>", methods=["POST"])
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
    return render_template("admin/placeholder.html", title="Ballot Pens")


@admin_bp.route("/electors")
@admin_required
def view_electors():
    return render_template("admin/placeholder.html", title="Electors")
@admin_bp.route("/sects")
@admin_required
def view_sects():
    return render_template(
        "admin/view_sects.html",
        sects=Sect.query.all()
    )
@admin_bp.route("/upload-electors", methods=["GET", "POST"])
def upload_electors():

    if session.get("role") != "admin":
        return redirect(url_for("auth.login"))

    if request.method == "POST":

        file = request.files.get("file")
        district_id = request.form.get("district_id")

        if not file:
            flash("No file selected")
            return redirect(url_for("admin.upload_electors"))

        # TODO: parse file safely here

        flash("Electors uploaded successfully")

        return redirect(url_for("admin.upload_electors"))

    districts = District.query.all()

    return render_template(
        "admin/upload_electors.html",
        districts=districts
    )
@admin_bp.route("/ballot-pens/upload", methods=["GET", "POST"])
@admin_required
def upload_ballot_pens():

    if request.method == "POST":

        file = request.files.get("file")

        if not file:
            flash("No file uploaded", "error")
            return redirect(url_for("admin.upload_ballot_pens"))

        # TODO: parse Excel here

        flash("Ballot pens uploaded successfully", "success")
        return redirect(url_for("admin.view_ballot_pens"))

    return render_template("admin/create_ballot_pen.html")