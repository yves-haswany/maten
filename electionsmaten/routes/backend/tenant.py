from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import csv
from io import StringIO
from ... import db
from ...models import User, Candidate, CandidateList, BallotPen,Party, Vote

tenant_bp = Blueprint("tenant", __name__, url_prefix="/tenant")

# ----------------------------
# Helpers
# ----------------------------
def is_tenant():
    return session.get("role") == "tenant"

def tenant_required(func):
    def wrapper(*args, **kwargs):
        if not is_tenant():
            flash("Tenant login required.", "error")
            return redirect(url_for("tenant.login"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# ----------------------------
# LOGIN / LOGOUT
# ----------------------------
@tenant_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter(
    User.username == username,
    User.is_admin == False,
    User.party_id != None
).first()

        if not user or not check_password_hash(user.password, password):
            return render_template("tenant/login.html", error="Invalid credentials")

        session.clear()
        session["user_id"] = user.id
        session["role"] = "tenant"
        session["last_activity"] = datetime.utcnow().timestamp()
        return redirect(url_for("tenant.dashboard"))

    return render_template("tenant/login.html")


@tenant_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("tenant.login"))


# ----------------------------
# DASHBOARD
# ----------------------------
@tenant_bp.route("/dashboard")
@tenant_required
def dashboard():
    users = User.query.filter_by(party_id=session.get("user_id")).all()
    candidate_lists = CandidateList.query.filter_by(party_id=session.get("user_id")).all()
    candidates = Candidate.query.filter_by(party_id=session.get("user_id")).all()
    ballot_pens = BallotPen.query.filter_by(user_id=session.get("user_id")).all()

    return render_template(
        "tenant/dashboard.html",
        users=users,
        candidate_lists=candidate_lists,
        candidates=candidates,
        ballot_pens=ballot_pens
    )


# ----------------------------
# CREATE USER
# ----------------------------
@tenant_bp.route("/create-user", methods=["GET", "POST"])
@tenant_required
def create_user():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        hashed = generate_password_hash(password)
        new_user = User(username=username, password=hashed, party_id=session.get("user_id"))
        db.session.add(new_user)
        db.session.commit()
        flash("User created successfully.", "success")
        return redirect(url_for("tenant.create_user"))

    return render_template("tenant/create_user.html")


# ----------------------------
# CREATE BALLOT PEN
# ----------------------------
@tenant_bp.route("/create-ballot-pen", methods=["GET", "POST"])
@tenant_required
def create_ballot_pen():
    if request.method == "POST":
        serial_number = request.form.get("serial_number")
        user_id = request.form.get("user_id")
        new_pen = BallotPen(serial_number=serial_number, user_id=user_id)
        db.session.add(new_pen)
        db.session.commit()
        flash("Ballot pen created successfully.", "success")
        return redirect(url_for("tenant.create_ballot_pen"))

    users = User.query.filter_by(party_id=session.get("user_id")).all()
    return render_template("tenant/create_ballot_pen.html", users=users)


# ----------------------------
# CREATE CANDIDATE LIST
# ----------------------------
@tenant_bp.route("/create-candidate-list", methods=["GET", "POST"])
@tenant_required
def create_candidate_list():
    if request.method == "POST":
        name = request.form.get("name")
        new_list = CandidateList(name=name, party_id=session.get("user_id"))
        db.session.add(new_list)
        db.session.commit()
        flash("Candidate list created successfully.", "success")
        return redirect(url_for("tenant.create_candidate_list"))

    candidate_lists = CandidateList.query.filter_by(party_id=session.get("user_id")).all()
    return render_template("tenant/create_candidate_list.html", candidate_lists=candidate_lists)


# ----------------------------
# CREATE CANDIDATE
# ----------------------------
@tenant_bp.route("/create-candidate", methods=["GET", "POST"])
@tenant_required
def create_candidate():
    candidate_lists = CandidateList.query.filter_by(party_id=session.get("user_id")).all()

    if request.method == "POST":
        name = request.form.get("name")
        party = request.form.get("party")
        list_id = request.form.get("list_id")

        new_candidate = Candidate(name=name, party=party, candidate_list_id=list_id)
        db.session.add(new_candidate)
        db.session.commit()
        flash("Candidate created successfully.", "success")
        return redirect(url_for("tenant.create_candidate"))

    return render_template("tenant/create_candidate.html", lists=candidate_lists)
@tenant_bp.route("/export-results")
@tenant_required
def export_results():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ballot Pen", "List Name", "Candidate", "Votes"])

    ballot_pens = BallotPen.query.all()
    candidates = Candidate.query.all()

    for pen in ballot_pens:
        for c in candidates:
            votes = Vote.query.filter(Vote.candidate_id == c.id, Vote.ballot_pen_id == pen.id).count()
            writer.writerow([pen.serial_number, c.candidate_list.name, c.name, votes])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"}
    )