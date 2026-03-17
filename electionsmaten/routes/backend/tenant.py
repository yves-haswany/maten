from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

from ... import db
from ...models import CandidateList, Candidate, District, Tenant

tenant_bp = Blueprint("tenant", __name__, url_prefix="/tenant")


# -----------------------
# LOGIN
# -----------------------

@tenant_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        tenant = Tenant.query.filter_by(username=username).first()

        if tenant and check_password_hash(tenant.password, password):
            session["tenant_id"] = tenant.id
            return redirect(url_for("tenant.dashboard"))

        flash("Invalid credentials")

    return render_template("tenant/login.html")


# -----------------------
# LOGOUT
# -----------------------

@tenant_bp.route("/logout")
def logout():
    session.pop("tenant_id", None)
    return redirect(url_for("tenant.login"))


# -----------------------
# DASHBOARD
# -----------------------

@tenant_bp.route("/dashboard")
def dashboard():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    return render_template(
        "tenant/dashboard.html",
        districts=tenant.districts
    )


# -----------------------
# VIEW DISTRICTS
# -----------------------

@tenant_bp.route("/districts")
def view_districts():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    return render_template(
        "tenant/view_districts.html",
        districts=tenant.districts
    )


# =====================================================
# 🔥 MAIN PAGE: MANAGE LISTS + CANDIDATES
# =====================================================

@tenant_bp.route("/manage-lists")
def manage_lists():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    lists = CandidateList.query.join(District).filter(
        District.id.in_([d.id for d in tenant.districts])
    ).all()

    return render_template(
        "tenant/manage_lists.html",
        lists=lists
    )


# -----------------------
# CREATE LIST
# -----------------------

@tenant_bp.route("/create-list", methods=["GET", "POST"])
def create_list():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    if request.method == "POST":

        name = request.form.get("name")
        district_id = request.form.get("district_id")

        new_list = CandidateList(
            name=name,
            district_id=district_id
        )

        db.session.add(new_list)
        db.session.commit()

        return redirect(url_for("tenant.manage_lists"))

    return render_template(
        "tenant/create_candidate_list.html",
        districts=tenant.districts
    )


# -----------------------
# EDIT LIST
# -----------------------

@tenant_bp.route("/edit-list/<int:list_id>", methods=["GET", "POST"])
def edit_list(list_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate_list = CandidateList.query.get_or_404(list_id)

    if request.method == "POST":
        candidate_list.name = request.form.get("name")
        db.session.commit()
        return redirect(url_for("tenant.manage_lists"))

    return render_template(
        "tenant/edit_list.html",
        list=candidate_list
    )


# -----------------------
# DELETE LIST
# -----------------------

@tenant_bp.route("/delete-list/<int:list_id>")
def delete_list(list_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate_list = CandidateList.query.get_or_404(list_id)

    db.session.delete(candidate_list)
    db.session.commit()

    return redirect(url_for("tenant.manage_lists"))


# -----------------------
# ADD CANDIDATE (INLINE)
# -----------------------

@tenant_bp.route("/add-candidate/<int:list_id>", methods=["POST"])
def add_candidate(list_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    name = request.form.get("name")
    party_name = request.form.get("party_name")

    candidate = Candidate(
        name=name,
        party_name=party_name,
        candidate_list_id=list_id
    )

    db.session.add(candidate)
    db.session.commit()

    return redirect(url_for("tenant.manage_lists"))


# -----------------------
# EDIT CANDIDATE
# -----------------------

@tenant_bp.route("/edit-candidate/<int:candidate_id>", methods=["GET", "POST"])
def edit_candidate(candidate_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate = Candidate.query.get_or_404(candidate_id)

    if request.method == "POST":
        candidate.name = request.form.get("name")
        candidate.party_name = request.form.get("party_name")
        db.session.commit()
        return redirect(url_for("tenant.manage_lists"))

    return render_template(
        "tenant/edit_candidate.html",
        candidate=candidate
    )


# -----------------------
# DELETE CANDIDATE
# -----------------------

@tenant_bp.route("/delete-candidate/<int:candidate_id>")
def delete_candidate(candidate_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate = Candidate.query.get_or_404(candidate_id)
    candidate_list = candidate.candidate_list

    db.session.delete(candidate)
    db.session.commit()

    # delete list if empty
    if len(candidate_list.candidates) == 0:
        db.session.delete(candidate_list)
        db.session.commit()

    return redirect(url_for("tenant.manage_lists"))


# -----------------------
# MOVE CANDIDATE
# -----------------------

@tenant_bp.route("/move-candidate/<int:candidate_id>", methods=["POST"])
def move_candidate(candidate_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate = Candidate.query.get_or_404(candidate_id)

    new_list_id = request.form.get("new_list_id")

    candidate.candidate_list_id = new_list_id

    db.session.commit()

    return redirect(url_for("tenant.manage_lists"))