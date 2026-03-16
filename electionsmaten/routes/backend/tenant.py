from flask import Blueprint, render_template, request, redirect, url_for, session, Response, flash
from werkzeug.security import check_password_hash
from io import StringIO
import csv

from ... import db
from ...models import CandidateList, Candidate, Vote, BallotPen, District, Tenant

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
# CREATE CANDIDATE LIST
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

        return redirect(url_for("tenant.view_lists"))

    return render_template(
        "tenant/create_candidate_list.html",
        districts=tenant.districts
    )

# -----------------------
# CREATE CANDIDATE
# -----------------------

@tenant_bp.route("/create-candidate", methods=["GET", "POST"])
def create_candidate():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    lists = CandidateList.query.join(District).filter(
        District.id.in_([d.id for d in tenant.districts])
    )

    if request.method == "POST":

        name = request.form.get("name")
        party_name = request.form.get("party_name")
        list_id = request.form.get("list_id")

        candidate = Candidate(
            name=name,
            party_name=party_name,
            candidate_list_id=list_id
        )

        db.session.add(candidate)
        db.session.commit()

        return redirect(url_for("tenant.view_candidates"))

    return render_template(
        "tenant/create_candidate.html",
        lists=lists
    )


# -----------------------
# RESULTS
# -----------------------

"""@tenant_bp.route("/results")
def results():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    return render_template(
        "tenant/results.html",
        districts=tenant.districts
    )


# -----------------------
# CSV DOWNLOAD
# -----------------------

@tenant_bp.route("/download-results")
def download_results():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "District",
        "Ballot Pen",
        "Candidate",
        "Votes"
    ])

    for district in tenant.districts:

        for pen in district.ballot_pens:

            for vote in pen.votes:

                writer.writerow([
                    district.name,
                    pen.username,
                    vote.candidate.name,
                    1
                ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=results.csv"
        }
    )"""
@tenant_bp.route("/districts")
def view_districts():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    return render_template(
        "tenant/view_districts.html",
        districts=tenant.districts
    )
@tenant_bp.route("/lists")
def view_lists():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    lists = CandidateList.query.join(District).filter(
        District.id.in_([d.id for d in tenant.districts])
    )

    return render_template(
        "tenant/view_lists.html",
        lists=lists
    )
@tenant_bp.route("/edit-list/<int:list_id>", methods=["GET", "POST"])
def edit_list(list_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate_list = CandidateList.query.get_or_404(list_id)

    if request.method == "POST":

        candidate_list.name = request.form.get("name")

        db.session.commit()

        return redirect(url_for("tenant.view_lists"))

    return render_template(
        "tenant/edit_list.html",
        list=candidate_list
    )@tenant_bp.route("/edit-list/<int:list_id>", methods=["GET", "POST"])
def edit_list(list_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate_list = CandidateList.query.get_or_404(list_id)

    if request.method == "POST":

        candidate_list.name = request.form.get("name")

        db.session.commit()

        return redirect(url_for("tenant.view_lists"))

    return render_template(
        "tenant/edit_list.html",
        list=candidate_list
    )
@tenant_bp.route("/delete-list/<int:list_id>")
def delete_list(list_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate_list = CandidateList.query.get_or_404(list_id)

    db.session.delete(candidate_list)
    db.session.commit()

    return redirect(url_for("tenant.view_lists"))
@tenant_bp.route("/candidates")
def view_candidates():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    candidates = Candidate.query.join(CandidateList).join(District).filter(
        District.id.in_([d.id for d in tenant.districts])
    )

    return render_template(
        "tenant/view_candidates.html",
        candidates=candidates
    )
@tenant_bp.route("/edit-candidate/<int:candidate_id>", methods=["GET","POST"])
def edit_candidate(candidate_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate = Candidate.query.get_or_404(candidate_id)

    if request.method == "POST":

        candidate.name = request.form.get("name")
        candidate.party_name = request.form.get("party_name")

        db.session.commit()

        return redirect(url_for("tenant.view_candidates"))

    return render_template(
        "tenant/edit_candidate.html",
        candidate=candidate
    )
@tenant_bp.route("/delete-candidate/<int:candidate_id>")
def delete_candidate(candidate_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate = Candidate.query.get_or_404(candidate_id)

    candidate_list = candidate.candidate_list

    db.session.delete(candidate)

    db.session.commit()

    # if list has no candidates → delete list
    if len(candidate_list.candidates) == 0:
        db.session.delete(candidate_list)
        db.session.commit()

    return redirect(url_for("tenant.view_candidates"))