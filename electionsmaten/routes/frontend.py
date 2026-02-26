from flask import Blueprint, render_template, request, redirect, url_for, session, send_file
from werkzeug.security import check_password_hash
from datetime import datetime
from io import BytesIO

from .. import db
from ..models import User, Elector, Candidate, CandidateList, Vote

frontend = Blueprint("frontend", __name__)


# ----------------------------
# Utilities
# ----------------------------
def is_logged_in():
    return "user_id" in session


def current_user():
    if not is_logged_in():
        return None
    return User.query.get(session["user_id"])


# ----------------------------
# Authentication
# ----------------------------
@frontend.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            session["last_activity"] = datetime.utcnow().timestamp()
            return redirect(url_for("frontend.dashboard"))

        return render_template("LoginPage.html", error="Invalid username or password")

    return render_template("LoginPage.html")


@frontend.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("frontend.login"))


# ----------------------------
# Dashboard
# ----------------------------
@frontend.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect(url_for("frontend.login"))

    return render_template("dashboard.html")


# ----------------------------
# Electors
# ----------------------------
@frontend.route("/index", methods=["GET", "POST"])
def index():
    if not is_logged_in():
        return redirect(url_for("frontend.login"))

    user = current_user()

    if request.method == "POST":
        elector_id = request.form.get("elector_id", "").strip()

        if elector_id:
            new_elector = Elector(
                elector_id=elector_id,
                user_id=user.id,
                submitted_at=datetime.utcnow()
            )
            db.session.add(new_elector)
            db.session.commit()

    return render_template("index.html")


@frontend.route("/view-electors")
def view_electors():
    if not is_logged_in():
        return redirect(url_for("frontend.login"))

    user = current_user()
    electors = Elector.query.filter_by(user_id=user.id).all()

    return render_template("electors.html", electors=electors)


@frontend.route("/export-electors")
def export_electors():
    if not is_logged_in():
        return redirect(url_for("frontend.login"))

    user = current_user()
    electors = Elector.query.filter_by(user_id=user.id).all()

    lines = ["Elector ID\tSubmitted At"]

    for e in electors:
        submitted = e.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if e.submitted_at else ""
        lines.append(f"{e.elector_id}\t{submitted}")

    output = BytesIO()
    output.write("\n".join(lines).encode("utf-8"))
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="my_electors.txt",
        mimetype="text/plain"
    )


# ----------------------------
# Voting
# ----------------------------
@frontend.route("/cast-vote")
def cast_vote():
    if not is_logged_in():
        return redirect(url_for("frontend.login"))

    lists = CandidateList.query.all()
    return render_template("vote.html", lists=lists)


@frontend.route("/get-candidates/<int:list_id>")
def get_candidates(list_id):
    candidates = Candidate.query.filter_by(candidate_list_id=list_id).all()

    return {
        "candidates": [
            {
                "candidate_id": c.id,
                "name": c.name,
                "party": c.party
            }
            for c in candidates
        ]
    }


@frontend.route("/submit-vote", methods=["POST"])
def submit_vote():
    if not is_logged_in():
        return {"error": "You must be logged in"}, 401

    user = current_user()

    list_id = request.form.get("list_id")
    candidate_id = request.form.get("candidate_id")

    if not list_id:
        return {"error": "You must select a list."}, 400

    try:
        list_id = int(list_id)
        candidate_id = int(candidate_id) if candidate_id else None
    except (ValueError, TypeError):
        return {"error": "Invalid selection."}, 400

    selected_list = CandidateList.query.get(list_id)
    if not selected_list:
        return {"error": "Invalid list."}, 400

    # Optional: validate candidate belongs to list
    if candidate_id:
        candidate = Candidate.query.get(candidate_id)
        if not candidate or candidate.candidate_list_id != list_id:
            return {"error": "Invalid candidate for selected list."}, 400

    # Save vote
    vote = Vote(
        user_id=user.id,
        list_id=list_id,
        candidate_id=candidate_id
    )

    db.session.add(vote)
    db.session.commit()

    return {"success": True}


@frontend.route("/sorted-votes")
def sorted_votes():
    if not is_logged_in():
        return redirect(url_for("frontend.login"))

    lists = CandidateList.query.all()
    candidates = Candidate.query.all()

    lists_data = [
        {
            "id": l.id,
            "name": l.name,
            "list_votes": Vote.query.filter_by(list_id=l.id).count()
        }
        for l in lists
    ]

    candidates_data = [
        {
            "id": c.id,
            "name": c.name,
            "list_name": c.candidate_list.name,
            "votes": Vote.query.filter_by(candidate_id=c.id).count()
        }
        for c in candidates
    ]

    lists_data.sort(key=lambda x: x["list_votes"], reverse=True)
    candidates_data.sort(key=lambda x: x["votes"], reverse=True)

    return render_template(
        "sorted_votes.html",
        lists=lists_data,
        candidates=candidates_data
    )