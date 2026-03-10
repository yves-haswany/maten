from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from io import StringIO
import csv

from ...models.db import db
from ...models import Party, Election, District, CandidateList, Candidate, User, BallotPen, Vote

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# ----------------------------
# Helpers
# ----------------------------
def is_admin():
    return session.get("role") == "admin"

def admin_required(func):
    def wrapper(*args, **kwargs):
        if not is_admin():
            flash("Admin login required.", "error")
            return redirect(url_for("admin.login"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# ----------------------------
# LOGIN / LOGOUT
# ----------------------------
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username, is_admin=True).first()

        if not user or not check_password_hash(user.password, password):
            return render_template("auth/admin_login.html", error="Invalid credentials")

        session.clear()
        session["user_id"] = user.id
        session["role"] = "admin"
        session["last_activity"] = datetime.utcnow().timestamp()
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


# ----------------------------
# DASHBOARD
# ----------------------------
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    parties = Party.query.all()
    elections = Election.query.all()
    districts = District.query.all()
    return render_template("admin/dashboard.html", parties=parties, elections=elections, districts=districts)


# ----------------------------
# CREATE PARTY
# ----------------------------
@admin_bp.route("/create-party", methods=["GET", "POST"])
@admin_required
def create_party():
    if request.method == "POST":
        name = request.form.get("name")
        if not name:
            flash("Party name is required.", "error")
        elif Party.query.filter_by(name=name).first():
            flash("Party already exists.", "error")
        else:
            party = Party(name=name)
            db.session.add(party)
            db.session.commit()
            flash("Party created successfully.", "success")
        return redirect(url_for("admin.create_party"))

    parties = Party.query.all()
    return render_template("admin/create_party.html", parties=parties)


# ----------------------------
# CREATE DISTRICT
# ----------------------------
@admin_bp.route("/create-district", methods=["GET", "POST"])
@admin_required
def create_district():
    elections = Election.query.all()
    if request.method == "POST":
        name = request.form.get("name")
        election_id = request.form.get("election_id")
        if not name or not election_id:
            flash("All fields required.", "error")
        else:
            district = District(name=name, election_id=election_id)
            db.session.add(district)
            db.session.commit()
            flash("District created successfully.", "success")
        return redirect(url_for("admin.create_district"))

    return render_template("admin/create_district.html", elections=elections)


# ----------------------------
# CREATE ELECTION
# ----------------------------
@admin_bp.route("/create-election", methods=["GET", "POST"])
@admin_required
def create_election():
    parties = Party.query.all()
    if request.method == "POST":
        name = request.form.get("name")
        party_id = request.form.get("party_id")
        if not name or not party_id:
            flash("All fields required.", "error")
        else:
            election = Election(name=name, party_id=party_id)
            db.session.add(election)
            db.session.commit()
            flash("Election created successfully.", "success")
        return redirect(url_for("admin.create_election"))

    return render_template("admin/create_election.html", parties=parties)


# ----------------------------
# SORTED VOTES EXPORT
# ----------------------------
@admin_bp.route("/export-votes")
@admin_required
def export_votes():
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
        headers={"Content-Disposition": "attachment; filename=votes.csv"}
    )