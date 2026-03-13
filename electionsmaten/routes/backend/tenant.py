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

@tenant_bp.route("/create-list", methods=["GET","POST"])
def create_list():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    if request.method == "POST":

        name = request.form.get("name")

        new_list = CandidateList(name=name)

        db.session.add(new_list)
        db.session.commit()

        return redirect(url_for("tenant.dashboard"))

    return render_template("tenant/create_list.html")


# -----------------------
# CREATE CANDIDATE
# -----------------------

@tenant_bp.route("/create-candidate", methods=["GET","POST"])
def create_candidate():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    lists = CandidateList.query.all()

    if request.method == "POST":

        name = request.form.get("name")
        list_id = request.form.get("list_id")

        candidate = Candidate(
            name=name,
            candidate_list_id=list_id
        )

        db.session.add(candidate)
        db.session.commit()

        return redirect(url_for("tenant.dashboard"))

    return render_template(
        "tenant/create_candidate.html",
        lists=lists
    )


# -----------------------
# RESULTS
# -----------------------

@tenant_bp.route("/results")
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
    )