from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash,generate_password_hash

from ... import db
from ...models import CandidateList, Candidate, District, Tenant, Vote, Elector, BallotPen
import csv
from io import StringIO
from flask import Response
tenant_bp = Blueprint("tenant", __name__, url_prefix="/tenant")


# -----------------------
# LOGIN
# -----------------------
def get_tenant_letter(tenant_id):
    return chr(64 + tenant_id)  # 1→A, 2→B
@tenant_bp.route("/login", methods=["GET", "POST"])
def login():
    session["role"] = "tenant"
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        tenant = Tenant.query.filter_by(username=username).first()

        if tenant and check_password_hash(tenant.password, password):
            session["tenant_id"] = tenant.id
            return redirect(url_for("tenant.dashboard"))

        flash("Invalid credentials")

    return render_template("tenant/login.html")


# -----------------------
# LOGOUT
# -----------------------

@tenant_bp.route("/logout")
def logout():
    session.pop("tenant_id", None)
    return redirect(url_for("tenant.login"))


# -----------------------
# DASHBOARD
# -----------------------

@tenant_bp.route("/dashboard")
def dashboard():

    if "tenant_id" not in session:
        return redirect(url_for("tenant_bp.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    return render_template(
        "tenant/dashboard.html",
        districts=tenant.districts
    )


# -----------------------
# VIEW DISTRICTS
# -----------------------

@tenant_bp.route("/districts", methods=["GET", "POST"])
def view_districts():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    # 🔥 HANDLE UPDATE
    if request.method == "POST":
        district_id = request.form.get("district_id")

        district = District.query.get(district_id)

        if district and district in tenant.districts:

            # Generate username
            letter = get_tenant_letter(tenant.id)
            username = f"{tenant.id}{letter}{district.id}D"

            district.username = username
            district.password = generate_password_hash(username)  # 🔒 hashed

            db.session.commit()

            flash(f"Credentials set for District {district.id}", "success")

        return redirect(url_for("tenant.view_districts"))

    return render_template(
        "tenant/view_districts.html",
        districts=tenant.districts
    )


# =====================================================
# 🔥 MAIN PAGE: MANAGE LISTS + CANDIDATES
# =====================================================

@tenant_bp.route("/manage-lists")
def manage_lists():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    lists = CandidateList.query.join(District).filter(
        District.id.in_([d.id for d in tenant.districts])
    ).all()

    return render_template(
        "tenant/manage_lists.html",
        lists=lists
    )


# -----------------------
# CREATE LIST
# -----------------------

@tenant_bp.route("/create-list", methods=["GET", "POST"])
def create_list():

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(session["tenant_id"])

    if request.method == "POST":

        name = request.form.get("name")
        district_id = request.form.get("district_id")

        new_list = CandidateList(
            name=name,
            district_id=district_id
        )

        db.session.add(new_list)
        db.session.commit()

        return redirect(url_for("tenant.create_list"))

    return render_template(
        "tenant/create_candidate_list.html",
        districts=tenant.districts
    )


# -----------------------
# EDIT LIST
# -----------------------

@tenant_bp.route("/edit-list/<int:list_id>", methods=["GET", "POST"])
def edit_list(list_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate_list = CandidateList.query.get_or_404(list_id)

    if request.method == "POST":
        candidate_list.name = request.form.get("name")
        db.session.commit()
        return redirect(url_for("tenant.manage_lists"))

    return render_template(
        "tenant/edit_list.html",
        list=candidate_list
    )


# -----------------------
# DELETE LIST
# -----------------------

@tenant_bp.route("/delete-list/<int:list_id>")
def delete_list(list_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate_list = CandidateList.query.get_or_404(list_id)

    db.session.delete(candidate_list)
    db.session.commit()

    return redirect(url_for("tenant.manage_lists"))


# -----------------------
# ADD CANDIDATE (INLINE)
# -----------------------

@tenant_bp.route("/add-candidate/<int:list_id>", methods=["GET", "POST"])
def add_candidate(list_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate_list = CandidateList.query.get_or_404(list_id)

    if request.method == "POST":

        name = request.form.get("name")
        

        # 🔒 Validate party belongs to list
        

        candidate = Candidate(
            name=name,
            candidate_list_id=list_id
        )

        db.session.add(candidate)
        db.session.commit()

        return redirect(url_for("tenant.add_candidate", list_id=list_id))

    return render_template("tenant/add_candidate.html", list=candidate_list)


# -----------------------
# EDIT CANDIDATE
# -----------------------

@tenant_bp.route("/edit-candidate/<int:candidate_id>", methods=["GET", "POST"])
def edit_candidate(candidate_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate = Candidate.query.get_or_404(candidate_id)

    if request.method == "POST":
        name = request.form.get("name")
        party_id = request.form.get("party_id")

        # 🔒 Validate party belongs to the list alliance
        if int(party_id) not in [p.id for p in candidate.candidate_list.parties]:
            flash("Invalid party for this list", "danger")
            return redirect(url_for("tenant.manage_lists"))

        candidate.name = name
        candidate.party_id = party_id  # ✅ correct field

        db.session.commit()

        return redirect(url_for("tenant.manage_lists"))

    return render_template(
        "tenant/edit_candidate.html",
        candidate=candidate
    )


# -----------------------
# DELETE CANDIDATE
# -----------------------

@tenant_bp.route("/delete-candidate/<int:candidate_id>")
def delete_candidate(candidate_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate = Candidate.query.get_or_404(candidate_id)
    candidate_list = candidate.candidate_list

    db.session.delete(candidate)
    db.session.commit()

    # delete list if empty
    if len(candidate_list.candidates) == 0:
        db.session.delete(candidate_list)
        db.session.commit()

    return redirect(url_for("tenant.manage_lists"))


# -----------------------
# MOVE CANDIDATE
# -----------------------

@tenant_bp.route("/move-candidate/<int:candidate_id>", methods=["POST"])
def move_candidate(candidate_id):

    if "tenant_id" not in session:
        return redirect(url_for("tenant.login"))

    candidate = Candidate.query.get_or_404(candidate_id)

    new_list_id = request.form.get("new_list_id")

    candidate.candidate_list_id = new_list_id

    db.session.commit()

    return redirect(url_for("tenant.manage_lists"))
from sqlalchemy import func, distinct

@tenant_bp.route("/results")
def tenant_results():
    tenant_id = session.get("tenant_id")

    if session.get("role") != "tenant":
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(tenant_id)
    districts = tenant.districts

    results_by_district = {}

    for district in districts:

        formatted_rows = []

        # ----------------------------
        # 1. FULL VOTES (list + candidate)
        # ----------------------------
        full_votes = (
            db.session.query(
                CandidateList.name,
                Candidate.name,
                BallotPen.username,
                BallotPen.district_id,
                db.func.count(Vote.id)
            )
            .select_from(Vote)
            .join(Candidate, Candidate.id == Vote.candidate_id)
            .join(CandidateList, CandidateList.id == Vote.list_id)
            .join(BallotPen, BallotPen.id == Vote.ballot_pen_id)
            .join(BallotPen.tenants)  # ✅ IMPORTANT
            .filter(
                BallotPen.district_id == district.id,
                Tenant.id == tenant_id  # ✅ FILTER BY TENANT
            )
            .group_by(
                CandidateList.name,
                Candidate.name,
                BallotPen.username,
                BallotPen.district_id
            )
            .all()
        )

        for list_name, candidate_name, username, district_id, votes in full_votes:
            formatted_rows.append({
                "tenant_id": tenant_id,
                "district_id": district_id,
                "ballot_pen": username[-4:],
                "list_name": list_name,
                "candidate_name": candidate_name,
                "votes": votes
            })

        # ----------------------------
        # 2. LIST ONLY (no candidate)
        # ----------------------------
        list_only_votes = (
            db.session.query(
                CandidateList.name,
                BallotPen.username,
                BallotPen.district_id,
                db.func.count(Vote.id)
            )
            .select_from(Vote)
            .join(CandidateList, CandidateList.id == Vote.list_id)
            .join(BallotPen, BallotPen.id == Vote.ballot_pen_id)
            .join(BallotPen.tenants)  # ✅ IMPORTANT
            .filter(
                BallotPen.district_id == district.id,
                Tenant.id == tenant_id,  # ✅ FILTER
                Vote.candidate_id == None
            )
            .group_by(
                CandidateList.name,
                BallotPen.username,
                BallotPen.district_id
            )
            .all()
        )

        for list_name, username, district_id, votes in list_only_votes:
            formatted_rows.append({
                "tenant_id": tenant_id,
                "district_id": district_id,
                "ballot_pen": username[-4:],
                "list_name": list_name,
                "candidate_name": "No candidate",
                "votes": votes
            })

        # ----------------------------
        # 3. BLANK VOTES
        # ----------------------------
        blank_votes = (
            db.session.query(
                BallotPen.username,
                BallotPen.district_id,
                db.func.count(Vote.id)
            )
            .select_from(Vote)
            .join(BallotPen, BallotPen.id == Vote.ballot_pen_id)
            .join(BallotPen.tenants)  # ✅ IMPORTANT
            .filter(
                BallotPen.district_id == district.id,
                Tenant.id == tenant_id,  # ✅ FILTER
                Vote.list_id == None,
                Vote.candidate_id == None
            )
            .group_by(
                BallotPen.username,
                BallotPen.district_id
            )
            .all()
        )

        for username, district_id, votes in blank_votes:
            formatted_rows.append({
                "tenant_id": tenant_id,
                "district_id": district_id,
                "ballot_pen": username[-4:],
                "list_name": None,
                "candidate_name": None,
                "votes": votes
            })

        results_by_district[district.id] = formatted_rows

    return render_template(
        "tenant/results.html",
        results=results_by_district
    )
@tenant_bp.route("/download-all-results")
def download_all_results():
    tenant_id = session.get("tenant_id")

    if session.get("role") != "tenant":
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(tenant_id)
    districts = tenant.districts

    import csv
    from io import StringIO
    from flask import Response

    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["Tenant", "District", "Ballot Pen", "List", "Candidate", "Votes"])

    for district in districts:

        # reuse SAME queries you already wrote
        # (copy your 3 blocks here)

        # Example for FULL votes:
        full_votes = (
            db.session.query(
                CandidateList.name,
                Candidate.name,
                BallotPen.username,
                db.func.count(Vote.id)
            )
            .select_from(Vote)
            .join(Candidate, Candidate.id == Vote.candidate_id)
            .join(CandidateList, CandidateList.id == Vote.list_id)
            .join(BallotPen, BallotPen.id == Vote.ballot_pen_id)
            .join(BallotPen.tenants)
            .filter(
                BallotPen.district_id == district.id,
                Tenant.id == tenant_id
            )
            .group_by(
                CandidateList.name,
                Candidate.name,
                BallotPen.username
            )
            .all()
        )

        for list_name, candidate_name, username, votes in full_votes:
            writer.writerow([
                tenant_id,
                district.id,
                username[-4:],
                list_name,
                candidate_name,
                votes
            ])

        # 👉 repeat for list_only + blank (same as your tenant_results)

    output.seek(0)

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=all_results.csv"}
    )
@tenant_bp.route("/electors")
def view_electors():
    """View all electors for this tenant grouped by district"""
    tenant_id = session.get("tenant_id")
    session['role'] = 'tenant'

    if not tenant_id or session['role'] != "tenant":
        return redirect(url_for("tenant.login"))

    tenant = Tenant.query.get(tenant_id)
    districts = tenant.districts

    electors_by_district = {}

    for district in districts:
        electors = db.session.query(
            Elector.id,
            Elector.elector_id,
            Elector.submitted_at,
            BallotPen.username
        ) .join(BallotPen, BallotPen.id == Elector.ballot_pen_id) .filter(Elector.tenant_id == tenant_id) .filter(Elector.district_id == district.id) .all()

        formatted = []
        for e in electors:
            ballot_pen_number = e.username[-4:] if e.username else "N/A"
            formatted.append({
                "elector_id": e.elector_id,
                "timestamp": e.submitted_at.strftime("%H:%M"),
                "ballot_pen": ballot_pen_number
            })

        electors_by_district[district.id] = formatted

    return render_template(
        "tenant/electors.html",
        electors=electors_by_district
    )


@tenant_bp.route("/electors/download/<int:district_id>")
def download_electors(district_id):
    """Download electors CSV for a district"""
    tenant_id = session.get("tenant_id")
    session['role'] = 'tenant'

    if not tenant_id or session['role'] != "tenant":
        return redirect(url_for("tenant.login"))

    electors = db.session.query(
        Elector.tenant_id,
        Elector.district_id,
        BallotPen.username,
        Elector.elector_id,
        Elector.submitted_at.label("timestamp")
    ) \
    .join(BallotPen, BallotPen.id == Elector.ballot_pen_id) \
    .filter(Elector.tenant_id == tenant_id) \
    .filter(Elector.district_id == district_id) \
    .all()

    # Create CSV
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "tenant_id",
        "district_id",
        "ballot_pen_number",
        "elector_id",
        "timestamp"
    ])

    # Rows
    for e in electors:
        ballot_pen_number = e.username[-4:] if e.username else "N/A"
        timestamp_hm = e.timestamp.strftime("%H:%M") if e.timestamp else "N/A"
        writer.writerow([
            e.tenant_id,
            e.district_id,
            ballot_pen_number,
            e.elector_id,
            timestamp_hm
        ])

    output.seek(0)

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment;filename=electors_district_{district_id}.csv"
        }
    )