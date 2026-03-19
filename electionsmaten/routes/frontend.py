from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime

from .. import db
from ..models import Elector, Candidate, CandidateList, Vote, BallotPen

frontend_bp = Blueprint("frontend_bp", __name__)


# ----------------------------
# Utilities
# ----------------------------

def is_logged_in():
    return session.get("role") == "ballot_pen"


# ----------------------------
# LOGIN (Ballot Pen ONLY)
# ----------------------------

@frontend_bp.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        pen = BallotPen.query.filter_by(username=username).first()

        if not pen or pen.password != password:
            return render_template("frontend/login.html", error="Invalid credentials")

        session.clear()

        session["ballot_pen_id"] = pen.id
        session["district_id"] = pen.district_id
        session["role"] = "ballot_pen"

        return redirect(url_for("frontend_bp.dashboard"))

    return render_template("frontend/login.html")


# ----------------------------
# LOGOUT
# ----------------------------

@frontend_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("frontend_bp.login"))


# ----------------------------
# DASHBOARD
# ----------------------------

@frontend_bp.route("/dashboard")
def dashboard():

    if not is_logged_in():
        return redirect(url_for("frontend_bp.login"))

    return render_template("frontend/dashboard.html")


# ----------------------------
# ENTER ELECTOR PAGE
# ----------------------------

@frontend_bp.route("/electors")
def electors():

    if not is_logged_in():
        return redirect(url_for("frontend_bp.login"))

    electors = Elector.query.filter_by(
        district_id=session["district_id"]
    ).all()

    return render_template("frontend/view_electors.html", electors=electors)


# ----------------------------
# SUBMIT ELECTOR
# ----------------------------

@frontend_bp.route("/submit-elector", methods=["POST"])
def submit_elector():

    if not is_logged_in():
        return redirect(url_for("frontend_bp.login"))

    elector_id = request.form.get("elector_id")

    if not elector_id:
        flash("Elector ID required")
        return redirect(url_for("frontend_bp.electors"))

    existing = Elector.query.filter_by(elector_id=elector_id).first()

    if existing:
        flash("Elector already registered")
        return redirect(url_for("frontend_bp.electors"))

    new_elector = Elector(
        elector_id=elector_id,
        district_id=session["district_id"],
        submitted_at=datetime.utcnow()
    )

    db.session.add(new_elector)
    db.session.commit()

    flash("Elector registered successfully")

    return redirect(url_for("frontend_bp.electors"))


# ----------------------------
# CAST VOTE PAGE
# ----------------------------

@frontend_bp.route("/cast-vote")
def cast_vote():

    if not is_logged_in():
        return redirect(url_for("frontend_bp.login"))

    # Only lists in the same district
    lists = CandidateList.query.filter_by(
        district_id=session["district_id"]
    ).all()

    return render_template("frontend/vote.html", lists=lists)


# ----------------------------
# GET CANDIDATES (AJAX)
# ----------------------------

@frontend_bp.route("/get-candidates/<int:list_id>")
def get_candidates(list_id):

    candidates = Candidate.query.filter_by(
        candidate_list_id=list_id
    ).all()

    return {
        "candidates": [
            {
                "candidate_id": c.id,
                "name": c.name,
                "party": c.party.name if c.party else "No Party"
            }
            for c in candidates
        ]
    }


# ----------------------------
# SUBMIT VOTE
# ----------------------------

@frontend_bp.route("/submit-vote", methods=["POST"])
def submit_vote():

    if not is_logged_in():
        return {"error": "Not authorized"}, 401

    elector_id = request.form.get("elector_id")
    list_id = request.form.get("list_id")
    candidate_id = request.form.get("candidate_id")

    if not elector_id:
        return {"error": "Elector ID required"}

    elector = Elector.query.filter_by(
        elector_id=elector_id,
        district_id=session["district_id"]
    ).first()

    if not elector:
        return {"error": "Elector not found"}

    if elector.has_voted:
        return {"error": "Elector already voted"}

    vote = Vote(
        list_id=list_id,
        candidate_id=candidate_id,
        ballot_pen_id=session["ballot_pen_id"]
    )

    elector.has_voted = True

    db.session.add(vote)
    db.session.commit()

    return {"success": True}


# ----------------------------
# RESULTS VIEW
# ----------------------------

@frontend_bp.route("/sorted-votes")
def sorted_votes():

    if not is_logged_in():
        return redirect(url_for("frontend_bp.login"))

    lists = CandidateList.query.filter_by(
        district_id=session["district_id"]
    ).all()

    candidates = Candidate.query.all()

    lists_data = []
    for l in lists:
        votes = Vote.query.filter_by(list_id=l.id).count()

        lists_data.append({
            "id": l.id,
            "name": l.name,
            "votes": votes
        })

    candidates_data = []
    for c in candidates:
        votes = Vote.query.filter_by(candidate_id=c.id).count()

        candidates_data.append({
            "id": c.id,
            "name": c.name,
            "list": c.candidate_list.name,
            "votes": votes
        })

    lists_data.sort(key=lambda x: x["votes"], reverse=True)
    candidates_data.sort(key=lambda x: x["votes"], reverse=True)

    return render_template(
        "frontend/sorted_votes.html",
        lists=lists_data,
        candidates=candidates_data
    )