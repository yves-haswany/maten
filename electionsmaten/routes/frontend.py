from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, flash
from werkzeug.security import check_password_hash
from datetime import datetime
from io import BytesIO

from .. import db
from ..models import User, Elector, Candidate, CandidateList, Vote, BallotPen

frontend_bp = Blueprint("frontend_bp", __name__)


# ----------------------------
# Utilities
# ----------------------------

def is_logged_in():
    return session.get("role") == "user"


def current_user():
    if not is_logged_in():
        return None
    return User.query.get(session["user_id"])


# ----------------------------
# USER LOGIN (Voting Operator)
# ----------------------------

@frontend_bp.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username, is_admin=False).first()

        if not user or not check_password_hash(user.password, password):
            return render_template("LoginPage.html", error="Invalid credentials")

        # user must belong to a party
        if not user.party_id:
            return render_template("LoginPage.html", error="Not a valid voting operator")

        # check ballot pen assignment
        pen = BallotPen.query.filter_by(user_id=user.id).first()

        if not pen:
            return render_template("LoginPage.html", error="No ballot pen assigned")

        session.clear()

        session["user_id"] = user.id
        session["party_id"] = user.party_id
        session["district_id"] = user.district_id
        session["ballot_pen_id"] = pen.id
        session["role"] = "user"
        session["last_activity"] = datetime.utcnow().timestamp()

        return redirect(url_for("frontend_bp.dashboard"))

    return render_template("LoginPage.html")


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

    return render_template("dashboard.html")


# ----------------------------
# ELECTOR REGISTRATION
# ----------------------------

@frontend_bp.route("/index")
def index():

    if not is_logged_in():
        return redirect(url_for("frontend.login"))

    user = current_user()

    electors = Elector.query.filter_by(district_id=user.district_id).all()

    return render_template("index.html", electors=electors)


# ----------------------------
# SUBMIT ELECTOR
# ----------------------------

@frontend_bp.route("/submit", methods=["POST"])
def submit_elector():

    if not is_logged_in():
        return redirect(url_for("frontend.login"))

    user = current_user()
    elector_id = request.form.get("elector_id")

    if not elector_id:
        flash("Elector ID required")
        return redirect(url_for("frontend.index"))

    elector = Elector.query.filter_by(elector_id=elector_id).first()

    if elector:
        flash("Elector already registered")
        return redirect(url_for("frontend.index"))

    new_elector = Elector(
        elector_id=elector_id,
        district_id=user.district_id,
        submitted_at=datetime.utcnow()
    )

    db.session.add(new_elector)
    db.session.commit()

    flash("Elector registered successfully")

    return redirect(url_for("frontend.index"))


# ----------------------------
# CAST VOTE PAGE
# ----------------------------

@frontend_bp.route("/cast-vote")
def cast_vote():

    if not is_logged_in():
        return redirect(url_for("frontend.login"))

    lists = CandidateList.query.all()

    return render_template("vote.html", lists=lists)


# ----------------------------
# GET CANDIDATES
# ----------------------------

@frontend_bp.route("/get-candidates/<int:list_id>")
def get_candidates(list_id):

    candidates = Candidate.query.filter_by(candidate_list_id=list_id).all()

    return {
        "candidates": [
            {
                "id": c.id,
                "name": c.name,
                "party": c.party
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

    elector = Elector.query.filter_by(elector_id=elector_id).first()

    if not elector:
        return {"error": "Elector not found"}, 404

    if elector.has_voted:
        return {"error": "Elector already voted"}, 400

    vote = Vote(
        elector_id=elector.id,
        election_id=1,  # current election
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
        return redirect(url_for("frontend.login"))

    lists = CandidateList.query.all()
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
        "sorted_votes.html",
        lists=lists_data,
        candidates=candidates_data
    )