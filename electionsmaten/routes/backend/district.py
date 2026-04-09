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

    # FULL VOTES
    full_votes = (
        db.session.query(
            CandidateList.name,
            Candidate.name,
            BallotPen.username,
            func.count(Vote.id)
        )
        .select_from(Vote)
        .join(Candidate, Candidate.id == Vote.candidate_id)
        .join(CandidateList, CandidateList.id == Vote.list_id)
        .join(BallotPen, BallotPen.id == Vote.ballot_pen_id)
        .filter(BallotPen.district_id == district_id)
        .group_by(CandidateList.name, Candidate.name, BallotPen.username)
        .all()
    )

    for list_name, candidate_name, username, votes_count in full_votes:
        formatted_rows.append({
            "ballot_pen": username[-4:],
            "list_name": list_name,
            "candidate_name": candidate_name,
            "votes": votes_count
        })

    # LIST ONLY
    list_only_votes = (
        db.session.query(
            CandidateList.name,
            BallotPen.username,
            func.count(Vote.id)
        )
        .select_from(Vote)
        .join(CandidateList, CandidateList.id == Vote.list_id)
        .join(BallotPen, BallotPen.id == Vote.ballot_pen_id)
        .filter(
            BallotPen.district_id == district_id,
            Vote.candidate_id == None
        )
        .group_by(CandidateList.name, BallotPen.username)
        .all()
    )

    for list_name, username, votes_count in list_only_votes:
        formatted_rows.append({
            "ballot_pen": username[-4:],
            "list_name": list_name,
            "candidate_name": "No candidate",
            "votes": votes_count
        })

    # BLANK VOTES
    blank_votes = (
        db.session.query(
            BallotPen.username,
            func.count(Vote.id)
        )
        .select_from(Vote)
        .join(BallotPen, BallotPen.id == Vote.ballot_pen_id)
        .filter(
            BallotPen.district_id == district_id,
            Vote.list_id == None,
            Vote.candidate_id == None
        )
        .group_by(BallotPen.username)
        .all()
    )

    for username, votes_count in blank_votes:
        formatted_rows.append({
            "ballot_pen": username[-4:],
            "list_name": None,
            "candidate_name": None,
            "votes": votes_count
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