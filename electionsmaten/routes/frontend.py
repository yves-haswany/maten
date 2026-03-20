from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import re
from .. import db
from ..models import Elector, Candidate, CandidateList, Vote, BallotPen, District, Tenant

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

        # ----------------------------
        # EXTRACT TENANT FROM USERNAME
        # ----------------------------
        match = re.match(r"(\d)[A-Z](\d+)D\d+", username)
        if not match:
            return render_template("frontend/login.html", error="Invalid username format")

        tenant_id = int(match.group(1))
        district_id = int(match.group(2))

        # ----------------------------
        # STORE IN SESSION
        # ----------------------------
        session.clear()
        session["ballot_pen_id"] = pen.id
        session["tenant_id"] = tenant_id
        session["district_id"] = district_id
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
# ENTER ELECTOR PAGE (GET ONLY)
# ----------------------------

@frontend_bp.route("/enter-electors")
def enter_electors():

    if not is_logged_in():
        return redirect(url_for("frontend_bp.login"))

    return render_template("frontend/enter_electors.html")


# ----------------------------
# SUBMIT ELECTOR
# ----------------------------

@frontend_bp.route("/submit-elector", methods=["POST"])
def submit_elector():

    if not is_logged_in():
        return redirect(url_for("frontend_bp.login"))

    elector_id_input = request.form.get("elector_id", "").strip()

    if not elector_id_input:
        flash("Elector ID required", "danger")
        return redirect(url_for("frontend_bp.enter_electors"))

    district_id = session.get("district_id")

    # Optional: tenant_id if you store it in session
    tenant_id = session.get("tenant_id")

    existing = Elector.query.filter_by(
        elector_id=elector_id_input,
        district_id=district_id
    ).first()

    if existing:
        flash("Elector already registered", "warning")
        return redirect(url_for("frontend_bp.enter_electors"))

    new_elector = Elector(
    elector_id=elector_id_input,
    tenant_id=session["tenant_id"],
    district_id=session["district_id"],
    submitted_at=datetime.utcnow()
)

    db.session.add(new_elector)
    db.session.commit()

    flash("Elector added successfully", "success")

    return redirect(url_for("frontend_bp.enter_electors"))


# ----------------------------
# CANCEL ELECTOR ENTRY
# ----------------------------

@frontend_bp.route("/cancel-elector", methods=["POST"])
def cancel_elector():

    if not is_logged_in():
        return redirect(url_for("frontend_bp.login"))

    flash("Elector entry cancelled")

    return redirect(url_for("frontend_bp.enter_electors"))


# ----------------------------
# VIEW ELECTORS
# ----------------------------

@frontend_bp.route("/view-electors")
def view_electors():

    if not is_logged_in():
        return redirect(url_for("frontend_bp.login"))

    electors = Elector.query.order_by(Elector.submitted_at.desc()).all()

    return render_template("frontend/view_electors.html", electors=electors)


# ----------------------------
# CAST VOTE PAGE
# ----------------------------

@frontend_bp.route("/cast-vote")
def cast_vote():

    if not is_logged_in():
        return redirect(url_for("frontend_bp.login"))

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
                "name": c.name
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

    list_id = request.form.get("list_id")
    candidate_id = request.form.get("candidate_id")

    ballot_pen_id = session["ballot_pen_id"]
    district_id = session["district_id"]

    # Count electors (limit votes)
    elector_count = Elector.query.filter_by(
        district_id=district_id
    ).count()

    vote_count = Vote.query.filter_by(
        ballot_pen_id=ballot_pen_id
    ).count()

    if vote_count >= elector_count:
        return {"error": "Maximum number of votes reached"}

    # Validation
    if not list_id and candidate_id:
        return {"error": "Select a list first"}

    if list_id and candidate_id:
        candidate = Candidate.query.get(candidate_id)
        if not candidate or str(candidate.candidate_list_id) != list_id:
            return {"error": "Invalid candidate selection"}

    vote = Vote(
        list_id=list_id if list_id else None,
        candidate_id=candidate_id if candidate_id else None,
        ballot_pen_id=ballot_pen_id
    )

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