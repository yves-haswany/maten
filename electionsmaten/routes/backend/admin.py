from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

from ... import db
from ...models import Party, Tenant, District, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# -----------------------
# LOGIN
# -----------------------

@admin_bp.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        admin = User.query.filter_by(username=username, role="admin").first()

        if admin and check_password_hash(admin.password, password):

            session["admin_id"] = admin.id

            return redirect(url_for("admin.dashboard"))

        flash("Invalid credentials")

    return render_template("admin/login.html")


# -----------------------
# LOGOUT
# -----------------------

@admin_bp.route("/logout")
def logout():

    session.pop("admin_id", None)

    return redirect(url_for("admin.login"))


# -----------------------
# DASHBOARD
# -----------------------

@admin_bp.route("/dashboard")
def dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    tenants = Tenant.query.all()
    districts = District.query.all()

    return render_template(
        "admin/dashboard.html",
        tenants=tenants,
        districts=districts
    )


# -----------------------
# CREATE DISTRICT
# -----------------------

@admin_bp.route("/create-district", methods=["GET","POST"])
def create_district():

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    if request.method == "POST":

        name = request.form.get("name")

        district = District(name=name)

        db.session.add(district)
        db.session.commit()

        flash("District created")

        return redirect(url_for("admin.create_district"))

    return render_template("admin/create_district.html")


# -----------------------
# CREATE TENANT
# -----------------------

@admin_bp.route("/create-tenant", methods=["GET","POST"])
def create_tenant():

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    districts = District.query.all()

    if request.method == "POST":

        party_name = request.form.get("party")
        username = request.form.get("username")
        password = request.form.get("password")

        district_ids = request.form.getlist("districts")

        party = Party.query.filter_by(name=party_name).first()

        if not party:
            party = Party(name=party_name)
            db.session.add(party)
            db.session.commit()

        tenant = Tenant(
            username=username,
            password=generate_password_hash(password),
            party_id=party.id
        )

        for d_id in district_ids:
            district = District.query.get(d_id)
            tenant.districts.append(district)

        db.session.add(tenant)
        db.session.commit()

        flash("Tenant created")

        return redirect(url_for("admin.create_tenant"))

    return render_template(
        "admin/create_party.html",
        districts=districts
    )
@admin_bp.route("/edit-district/<int:district_id>", methods=["GET", "POST"])
def edit_district(district_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    district = District.query.get_or_404(district_id)

    if request.method == "POST":
        district.name = request.form.get("name")
        db.session.commit()
        flash("District updated")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/edit_district.html", district=district)

# -----------------------
# EDIT TENANT
# -----------------------
@admin_bp.route("/edit-tenant/<int:tenant_id>", methods=["GET", "POST"])
def edit_tenant(tenant_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    tenant = Tenant.query.get_or_404(tenant_id)
    districts = District.query.all()

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
            db.session.commit()
        tenant.party_id = party.id

        # Update districts
        tenant.districts = []  # clear previous districts
        district_ids = request.form.getlist("districts")
        for d_id in district_ids:
            district = District.query.get(d_id)
            tenant.districts.append(district)

        db.session.commit()
        flash("Tenant updated")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/edit_tenant.html", tenant=tenant, districts=districts)