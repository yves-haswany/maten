from flask import Blueprint, render_template, request, session, redirect, url_for,Response
from werkzeug.security import check_password_hash
from electionsmaten.models import District,Elector,Vote,Candidate,CandidateList
import csv
from io import StringIO
from sqlalchemy.orm import joinedload


district_bp = Blueprint('district', __name__, url_prefix='/district')

@district_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Find district associated with this tenant
        district = District.query.filter_by(username=username).first()

        if district and check_password_hash(district.password, password):
            session['district_id'] = district.id
            return redirect(url_for('district.dashboard'))

        return "Invalid credentials", 401

    return render_template('district/login.html')

@district_bp.route('/dashboard')
def dashboard():
    if 'district_id' not in session:
        return redirect(url_for('district.login'))

    district = District.query.get(session['district_id'])

    return render_template('district/dashboard.html',district=district)
@district_bp.route('/logout')
def logout():
    session.pop('district_id', None)
    return redirect(url_for('district.login'))
@district_bp.route('/electors')
def electors():
    if 'district_id' not in session:
        return redirect(url_for('district.login'))

    district_id = session['district_id']

    electors = Elector.query.filter_by(district_id=district_id).all()

    return render_template(
        'district/electors.html',
        electors=electors
    )

from flask import render_template, request, abort
from sqlalchemy import func
from electionsmaten.models import Vote, Candidate, CandidateList, BallotPen, District, db

@district_bp.route("/results/<int:district_id>")
def results(district_id):
    district = District.query.get_or_404(district_id)

    formatted_rows = []

    # ----------------------------
    # 1. FULL VOTES (list + candidate)
    # ----------------------------
    full_votes = (
        db.session.query(
            CandidateList.name.label("list_name"),
            Candidate.name.label("candidate_name"),
            BallotPen.username.label("username"),
            func.count(Vote.id).label("votes_count")
        )
        .select_from(Vote)
        .join(BallotPen, BallotPen.id == Vote.ballot_pen_id)
        .outerjoin(Candidate, Candidate.id == Vote.candidate_id)
        .outerjoin(CandidateList, CandidateList.id == Vote.list_id)
        .filter(
            BallotPen.district_id == district_id,
            Vote.candidate_id.isnot(None),
            Vote.list_id.isnot(None)
        )
        .group_by(
            CandidateList.name,
            Candidate.name,
            BallotPen.username
        )
        .all()
    )

    for row in full_votes:
        formatted_rows.append({
            "ballot_pen": row.username[-4:],
            "list_name": row.list_name,
            "candidate_name": row.candidate_name,
            "votes": row.votes_count
        })

    # ----------------------------
    # 2. LIST ONLY (no candidate)
    # ----------------------------
    list_only_votes = (
        db.session.query(
            CandidateList.name.label("list_name"),
            BallotPen.username.label("username"),
            func.count(Vote.id).label("votes_count")
        )
        .select_from(Vote)
        .join(BallotPen, BallotPen.id == Vote.ballot_pen_id)
        .outerjoin(CandidateList, CandidateList.id == Vote.list_id)
        .filter(
            BallotPen.district_id == district_id,
            Vote.candidate_id.is_(None),
            Vote.list_id.isnot(None)
        )
        .group_by(
            CandidateList.name,
            BallotPen.username
        )
        .all()
    )

    for row in list_only_votes:
        formatted_rows.append({
            "ballot_pen": row.username[-4:],
            "list_name": row.list_name,
            "candidate_name": "No candidate",
            "votes": row.votes_count
        })

    # ----------------------------
    # 3. BLANK VOTES
    # ----------------------------
    blank_votes = (
        db.session.query(
            BallotPen.username.label("username"),
            func.count(Vote.id).label("votes_count")
        )
        .select_from(Vote)
        .join(BallotPen, BallotPen.id == Vote.ballot_pen_id)
        .filter(
            BallotPen.district_id == district_id,
            Vote.list_id.is_(None),
            Vote.candidate_id.is_(None)
        )
        .group_by(BallotPen.username)
        .all()
    )

    for row in blank_votes:
        formatted_rows.append({
            "ballot_pen": row.username[-4:],
            "list_name": None,
            "candidate_name": None,
            "votes": row.votes_count
        })

    return render_template(
        "district/results.html",
        results=formatted_rows,
        district=district
    )
@district_bp.route('/results/download')
def download_results():
    if 'district_id' not in session:
        return redirect(url_for('district.login'))

    district_id = session['district_id']

    votes = Vote.query.join(Elector).filter(
        Elector.district_id == district_id
    ).all()

    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Elector ID",
        "Candidate Name",
        "Candidate ID",
        "List ID"
    ])

    # Rows
    for vote in votes:
        writer.writerow([
            vote.elector.elector_id,
            vote.candidate.name,
            vote.candidate.id,
            vote.candidate.candidate_list_id
        ])

    output.seek(0)

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment;filename=district_results.csv"
        }
    )
