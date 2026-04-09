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

@district_bp.route("/results")
def results():
    # Fetch all votes and eager-load candidate + candidate_list
    votes = (
        Vote.query
        .options(
            joinedload(Vote.candidate).joinedload("candidate_list")
        )
        .all()
    )

    results_data = {}
    for vote in votes:
        candidate = vote.candidate
        candidate_lis_id = candidate.candidate_list_id

        if candidate is None:
            # Skip votes that reference a deleted/missing candidate
            continue


        candidate_list = candidate.candidate_list
        list_name = candidate_list.name if candidate_list else "No List"

        if list_name not in results_data:
            results_data[list_name] = {}

        if candidate.name not in results_data[list_name]:
            results_data[list_name][candidate.name] = 0

        results_data[list_name][candidate.name] += 1

    return render_template("district/results.html", results=results_data)
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
