from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from io import BytesIO
from sqlalchemy import func
import csv
from .. import db
from ..models import User, Elector, BallotPen, Candidate, CandidateList, Vote

backend = Blueprint("backend", __name__)

# ----------------------------
# SYSTEM CONSTANTS
# ----------------------------
MAX_USERS = 361
SESSION_TIMEOUT = 180  # seconds


# ----------------------------
# GLOBAL SESSION TIMEOUT
# ----------------------------
@backend.before_app_request
def check_session_timeout():
    if "user_id" in session:
        now = datetime.utcnow().timestamp()
        last_activity = session.get("last_activity", now)

        if now - last_activity > SESSION_TIMEOUT:
            session.clear()
            flash("Session expired.", "warning")
            return redirect(url_for("backend.admin_login"))

        session["last_activity"] = now


# ----------------------------
# UTILITIES
# ----------------------------
def is_admin():
    return session.get("is_admin") is True


# ----------------------------
# ADMIN AUTH
# ----------------------------
@backend.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password, password):
            return render_template("AdminLoginPage.html",
                                   error="Invalid credentials")

        if not user.is_admin:
            return render_template("AdminLoginPage.html",
                                   error="Not an admin")

        session.clear()
        session["user_id"] = user.id
        session["is_admin"] = True
        session["last_activity"] = datetime.utcnow().timestamp()

        return redirect(url_for("backend.admin_dashboard"))

    return render_template("AdminLoginPage.html")


@backend.route("/admin-logout")
def admin_logout():
    session.clear()
    return redirect(url_for("backend.admin_login"))


@backend.route("/admin/dashboard")
def admin_dashboard():
    if not is_admin():
        return redirect(url_for("backend.admin_login"))
    return render_template("admin_dashboard.html")


# ----------------------------
# ADMIN: CREATE USER
# ----------------------------
@backend.route("/admin/create-user", methods=["GET", "POST"])
def create_user():
    if not is_admin():
        return "Access Denied", 403

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if User.query.count() >= MAX_USERS:
            return render_template("register.html",
                                   error="User limit reached.")

        if User.query.filter_by(username=username).first():
            return render_template("register.html",
                                   error="Username already exists.")

        hashed = generate_password_hash(password)
        new_user = User(username=username, password=hashed)

        db.session.add(new_user)
        db.session.commit()

        return render_template("register.html",
                               success="User created successfully.")

    return render_template("register.html")


# ----------------------------
# DEVELOPER ROUTES
# ----------------------------
@backend.route("/developer/users")
def developer_users():
    if not is_admin():
        return "Access Denied", 403

    users = User.query.all()
    return render_template("developer_users.html", users=users)


@backend.route("/developer/export-all-electors")
def export_all_electors():
    if not is_admin():
        return "Access Denied", 403

    records = []
    users = User.query.all()

    for user in users:
        for e in user.electors:
            records.append(
                f"{e.elector_id},{e.submitted_at},{user.username}"
            )

    content = "Elector ID,Submitted At,Username\n" + "\n".join(records)

    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition":
                 "attachment;filename=all_electors.txt"}
    )


# ----------------------------
# BALLOT PEN
# ----------------------------
@backend.route("/admin/create-ballot-pen", methods=["GET", "POST"])
def create_ballot_pen():
    if not is_admin():
        return "Access Denied", 403

    users = User.query.all()

    if request.method == "POST":
        serial_number = request.form.get("serial_number")
        user_id = request.form.get("user_id")

        new_pen = BallotPen(
            serial_number=serial_number,
            user_id=user_id
        )

        db.session.add(new_pen)
        db.session.commit()

        return render_template("create_ballot_pen.html",
                               users=users,
                               success="Ballot pen created successfully!")

    return render_template("create_ballot_pen.html", users=users)


# ----------------------------
# CANDIDATE LIST
# ----------------------------
@backend.route("/admin/create-candidate-list", methods=["GET", "POST"])
def create_candidate_list():
    if not is_admin():
        return "Access Denied", 403

    candidate_lists = CandidateList.query.all()

    if request.method == "POST":
        name = request.form.get("name")

        if not name:
            return render_template("create_candidate_list.html",
                                   candidate_lists=candidate_lists,
                                   error="List name is required.")

        if CandidateList.query.filter_by(name=name).first():
            return render_template("create_candidate_list.html",
                                   candidate_lists=candidate_lists,
                                   error="List already exists.")

        new_list = CandidateList(name=name)
        db.session.add(new_list)
        db.session.commit()

        return render_template("create_candidate_list.html",
                               candidate_lists=CandidateList.query.all(),
                               success="Created successfully")

    return render_template("create_candidate_list.html",
                           candidate_lists=candidate_lists)


# ----------------------------
# CREATE CANDIDATE
# ----------------------------
@backend.route("/admin/create-candidate", methods=["GET", "POST"])
def create_candidate():
    if not is_admin():
        return "Access Denied", 403

    lists = CandidateList.query.all()

    if request.method == "POST":
        name = request.form.get("name")
        party = request.form.get("party")
        candidate_list_id = request.form.get("list_id")

        if not name or not party or not candidate_list_id:
            return render_template("create_candidate.html",
                                   lists=lists,
                                   error="All fields required.")

        new_candidate = Candidate(
            name=name,
            party=party,
            candidate_list_id=candidate_list_id
        )

        db.session.add(new_candidate)
        db.session.commit()

        return render_template("create_candidate.html",
                               lists=lists,
                               success="Candidate created successfully!")

    return render_template("create_candidate.html",
                           candidates=Candidate.query.all(),
                           lists=lists)


# ----------------------------
# ADMIN SORTED VOTES
# ----------------------------
@backend.route("/admin/sorted-votes")
def admin_sorted_votes():
    if not is_admin():
        return redirect(url_for("backend.admin_login"))

    users = User.query.filter_by(is_admin=False).all()
    user_ids = [u.id for u in users]

    candidates = Candidate.query.all()
    lists = CandidateList.query.all()

    candidates_data = []
    for c in candidates:
        votes = Vote.query.filter(
            Vote.user_id.in_(user_ids),
            Vote.candidate_id == c.id
        ).count()

        candidates_data.append({
            "id": c.id,
            "name": c.name,
            "list_name": c.candidate_list.name,
            "votes": votes
        })

    lists_data = []
    for l in lists:
        votes = Vote.query.filter(
            Vote.user_id.in_(user_ids),
            Vote.list_id == l.id
        ).count()

        lists_data.append({
            "id": l.id,
            "name": l.name,
            "list_votes": votes
        })

    candidates_data.sort(key=lambda x: x["votes"], reverse=True)
    lists_data.sort(key=lambda x: x["list_votes"], reverse=True)

    return render_template("admin_sorted_votes.html",
                           lists=lists_data,
                           candidates=candidates_data)
import io
from flask import send_file

@backend.route("/admin/download-list-totals")
def download_list_totals():
    if not is_admin():
        return "Access denied", 403

    try:
        output = io.StringIO()
        writer = csv.writer(output)
        # Header row
        writer.writerow(["Ballot Pen", "Candidate List", "List Votes"])

        # Query all ballot pens and candidate lists
        ballot_pens = BallotPen.query.all()
        candidate_lists = CandidateList.query.all()

        # For each combination of ballot pen and candidate list, count votes
        for pen in ballot_pens:
            for c_list in candidate_lists:
                votes_count = (
                    db.session.query(func.count(Vote.id))
                    .join(Candidate)
                    .filter(
                        Candidate.list_id == c_list.id,
                        Vote.ballot_pen_id == pen.id
                    )
                    .scalar()
                )
                writer.writerow([pen.serial_number, c_list.name, votes_count])

        output.seek(0)
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=list_totals.csv"}
        )

    except Exception as e:
        return f"Error generating CSV: {e}", 500


@backend.route("/admin/download-candidate-totals")
def download_candidate_totals():
    if not is_admin():
        return "Access denied", 403

    try:
        output = io.StringIO()
        writer = csv.writer(output)
        # Header row
        writer.writerow(["Ballot Pen", "Candidate List", "Candidate", "Candidate Votes"])

        ballot_pens = BallotPen.query.all()
        candidates = Candidate.query.all()

        # Count votes per candidate per ballot pen
        for pen in ballot_pens:
            for candidate in candidates:
                votes_count = (
                    db.session.query(func.count(Vote.id))
                    .filter(
                        Vote.candidate_id == candidate.id,
                        Vote.ballot_pen_id == pen.id
                    )
                    .scalar()
                )
                writer.writerow([pen.serial_number, candidate.candidate_list.name, candidate.name, votes_count])

        output.seek(0)
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=candidate_totals.csv"}
        )

    except Exception as e:
        return f"Error generating CSV: {e}", 500