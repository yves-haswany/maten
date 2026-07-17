from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response,
    abort
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)

from sqlalchemy import func, distinct

from io import StringIO
import csv

from ... import db

from ...models.master_models import (
    Tenant,
    District,
    BallotPen,
    Party,
    User,
    tenant_district,
    Elector
)

from ...models.tenant_models import (
    CandidateList,
    Candidate,
    Vote,
    BallotPenAccount
)

tenant_bp = Blueprint(
    "tenant",
    __name__,
    url_prefix="/tenant"
)

# ==========================================================
# HELPERS
# ==========================================================

def get_current_tenant():
    """
    Returns the currently logged-in tenant.

    Returns None if the session is invalid.
    """

    tenant_id = session.get("tenant_id")

    if (
        not tenant_id or
        session.get("role") != "tenant"
    ):
        return None

    return Tenant.query.get(tenant_id)


def get_tenant_or_redirect():
    """
    Returns the tenant or redirects to login.
    """

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))

    return tenant


def get_allowed_districts(tenant):
    """
    Returns all districts assigned to this tenant.
    """

    return tenant.districts


def get_selected_districts(tenant):
    """
    Allows every page to support:

        /page
        /page?district_id=5

    If district_id is omitted,
    all assigned districts are returned.

    If supplied, verifies the district belongs
    to the tenant.
    """

    district_id = request.args.get(
        "district_id",
        type=int
    )

    districts = tenant.districts

    if district_id is None:
        return districts

    selected = [
        d for d in districts
        if d.id == district_id
    ]

    if not selected:
        abort(403)

    return selected


def tenant_has_district(
    tenant,
    district_id
):
    """
    Returns True if this tenant
    participates in the district.
    """

    return any(
        d.id == district_id
        for d in tenant.districts
    )


def get_tenant_letter(
    tenant_id
):
    """
    Converts

        1 -> A
        2 -> B
        3 -> C

    Used when generating usernames.
    """

    return chr(64 + tenant_id)

# ==========================================================
# DASHBOARD
# ==========================================================

@tenant_bp.route("/dashboard")
def dashboard():

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))

    districts = tenant.districts

    return render_template(
        "tenant/dashboard.html",
        tenant=tenant,
        districts=districts,
        district_count=len(districts)
    )
# ==========================================================
# DISTRICT CREDENTIALS
# ==========================================================

@tenant_bp.route("/districts", methods=["GET", "POST"])
def view_districts():

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))

    # ---------------------------------------
    # Generate / Update credentials
    # ---------------------------------------
    if request.method == "POST":

        district_id = request.form.get(
            "district_id",
            type=int
        )

        action = request.form.get("action")

        district = District.query.get_or_404(
            district_id
        )

        # Security:
        # Tenant can only manage
        # their assigned districts.
        if district not in tenant.districts:
            abort(403)

        # -----------------------------------
        # Generate credentials
        # -----------------------------------
        if action == "generate":

            letter = get_tenant_letter(
                tenant.id
            )

            username = (
                f"{tenant.id}"
                f"{letter}"
                f"{district.id}"
                "D"
            )

            district.username = username
            district.password = generate_password_hash(
                username
            )

            flash(
                f"Credentials generated for "
                f"{district.name}.",
                "success"
            )

        # -----------------------------------
        # Update password
        # -----------------------------------
        elif action == "update_password":

            new_password = request.form.get(
                "new_password",
                ""
            ).strip()

            if not new_password:

                flash(
                    "Password cannot be empty.",
                    "danger"
                )

            else:

                district.password = (
                    generate_password_hash(
                        new_password
                    )
                )

                flash(
                    f"Password updated for "
                    f"{district.name}.",
                    "success"
                )

        db.session.commit()

        return redirect(
            url_for("tenant.view_districts")
        )

    # ---------------------------------------
    # Optional district filter
    # ---------------------------------------
    districts = get_selected_districts(
        tenant
    )

    return render_template(
        "tenant/view_districts.html",
        tenant=tenant,
        districts=districts,
        all_districts=tenant.districts
    )
# ==========================================================
# BALLOT PEN CREDENTIALS
# ==========================================================

@tenant_bp.route("/ballot-pens", methods=["GET"])
def ballot_pens():

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))

    districts = get_selected_districts(tenant)

    district_ids = [d.id for d in districts]

    ballot_pens = (
        BallotPen.query
        .filter(BallotPen.district_id.in_(district_ids))
        .order_by(
            BallotPen.district_id,
            BallotPen.number
        )
        .all()
    )

    return render_template(
        "tenant/ballot_pens.html",
        ballot_pens=ballot_pens,
        districts=tenant.districts,
        selected_district=request.args.get(
            "district_id",
            type=int
        )
    )
# ==========================================================
# GENERATE BALLOT PEN CREDENTIALS
# ==========================================================
@tenant_bp.route("/ballot-pen-credentials")
def manage_ballot_pen_credentials():

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("auth.login"))


    districts = (
        District.query
        .join(tenant_district)
        .filter(
            tenant_district.c.tenant_id == tenant.id
        )
        .all()
    )


    return render_template(
        "tenant/ballot_pen_credentials.html",
        districts=districts
    )
@tenant_bp.route(
    "/ballot-pens/<int:ballot_pen_id>/generate",
    methods=["POST"]
)
def generate_ballot_pen_credentials(ballot_pen_id):

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))

    ballot_pen = BallotPen.query.get_or_404(ballot_pen_id)

    if ballot_pen.district not in tenant.districts:
        abort(403)

    account = BallotPenAccount.query.filter_by(
        ballot_pen_id=ballot_pen.id
    ).first()

    if account is None:

        letter = get_tenant_letter(tenant.id)

        username = (
            f"{tenant.id}"
            f"{letter}"
            f"{ballot_pen.district_id}"
            f"P{ballot_pen.number}"
        )

        account = BallotPenAccount(
            ballot_pen_id=ballot_pen.id,
            username=username,
            password=generate_password_hash(username)
        )

        db.session.add(account)

    else:

        account.password = generate_password_hash(
            account.username
        )

    db.session.commit()

    flash(
        f"Credentials generated for Ballot Pen {ballot_pen.number}.",
        "success"
    )

    return redirect(url_for("tenant.ballot_pens"))
# ==========================================================
# UPDATE BALLOT PEN PASSWORD
# ==========================================================

@tenant_bp.route(
    "/ballot-pens/<int:ballot_pen_id>/password",
    methods=["POST"]
)
def update_ballot_pen_password(ballot_pen_id):

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))

    ballot_pen = BallotPen.query.get_or_404(ballot_pen_id)

    if ballot_pen.district not in tenant.districts:
        abort(403)

    account = BallotPenAccount.query.filter_by(
        ballot_pen_id=ballot_pen.id
    ).first()

    if account is None:

        flash(
            "Generate credentials first.",
            "danger"
        )

        return redirect(url_for("tenant.ballot_pens"))

    new_password = request.form.get(
        "new_password",
        ""
    ).strip()

    if not new_password:

        flash(
            "Password cannot be empty.",
            "danger"
        )

        return redirect(url_for("tenant.ballot_pens"))

    account.password = generate_password_hash(
        new_password
    )

    db.session.commit()

    flash(
        f"Password updated for Ballot Pen {ballot_pen.number}.",
        "success"
    )

    return redirect(url_for("tenant.ballot_pens"))
# ==========================================================
# MANAGE LISTS
# ==========================================================

@tenant_bp.route("/manage-lists")
def manage_lists():

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))

    districts = get_selected_districts(tenant)

    district_ids = [d.id for d in districts]

    lists = (
        CandidateList.query
        .filter(
            CandidateList.district_id.in_(district_ids)
        )
        .order_by(
            CandidateList.district_id,
            CandidateList.name
        )
        .all()
    )

    return render_template(
        "tenant/manage_lists.html",
        lists=lists,
        districts=tenant.districts,
        selected_district=request.args.get(
            "district_id",
            type=int
        )
    )
# ==========================================================
# CREATE LIST
# ==========================================================

@tenant_bp.route(
    "/create-list",
    methods=["GET", "POST"]
)
def create_list():

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))

    if request.method == "POST":

        district_id = request.form.get(
            "district_id",
            type=int
        )

        if not tenant_has_district(
            tenant,
            district_id
        ):
            abort(403)

        name = request.form.get(
            "name",
            ""
        ).strip()

        if not name:

            flash(
                "List name is required.",
                "danger"
            )

            return redirect(
                url_for("tenant.create_list")
            )

        existing = CandidateList.query.filter_by(
            district_id=district_id,
            name=name
        ).first()

        if existing:

            flash(
                "A list with this name already exists.",
                "danger"
            )

            return redirect(
                url_for("tenant.create_list")
            )

        candidate_list = CandidateList(
            name=name,
            district_id=district_id
        )

        db.session.add(candidate_list)
        db.session.commit()

        flash(
            "List created successfully.",
            "success"
        )

        return redirect(
            url_for("tenant.manage_lists")
        )

    return render_template(
        "tenant/create_candidate_list.html",
        districts=tenant.districts
    )
# ==========================================================
# EDIT LIST
# ==========================================================

@tenant_bp.route(
    "/edit-list/<int:list_id>",
    methods=["GET", "POST"]
)
def edit_list(list_id):

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))

    candidate_list = CandidateList.query.get_or_404(
        list_id
    )

    if not tenant_has_district(
        tenant,
        candidate_list.district_id
    ):
        abort(403)

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        if not name:

            flash(
                "List name cannot be empty.",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.edit_list",
                    list_id=list_id
                )
            )

        candidate_list.name = name

        db.session.commit()

        flash(
            "List updated successfully.",
            "success"
        )

        return redirect(
            url_for("tenant.manage_lists")
        )

    return render_template(
        "tenant/edit_list.html",
        list=candidate_list
    )
# ==========================================================
# DELETE LIST
# ==========================================================

@tenant_bp.route(
    "/delete-list/<int:list_id>",
    methods=["POST"]
)
def delete_list(list_id):

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))

    candidate_list = CandidateList.query.get_or_404(
        list_id
    )

    if not tenant_has_district(
        tenant,
        candidate_list.district_id
    ):
        abort(403)

    db.session.delete(candidate_list)

    db.session.commit()

    flash(
        "List deleted successfully.",
        "success"
    )

    return redirect(
        url_for("tenant.manage_lists")
    )
@tenant_bp.route(
    "/candidate/add/<int:list_id>",
    methods=["POST"]
)
def add_candidate(list_id):

    ####################################################
    # Tenant authentication
    ####################################################

    if session.get("role") != "tenant":
        abort(403)


    tenant_id = session.get(
        "tenant_id"
    )


    ####################################################
    # Validate candidate list ownership
    ####################################################

    candidate_list = CandidateList.query.filter_by(
        id=list_id,
        tenant_id=tenant_id
    ).first()


    if not candidate_list:
        abort(403)



    ####################################################
    # Read form
    ####################################################

    name = request.form.get(
        "name",
        ""
    ).strip()


    if not name:

        flash(
            "Candidate name is required",
            "danger"
        )

        return redirect(
            url_for(
                "tenant.manage_lists"
            )
        )



    ####################################################
    # Create candidate
    ####################################################

    candidate = Candidate(
        name=name,
        list_id=candidate_list.id
    )


    db.session.add(candidate)

    db.session.commit()



    flash(
        "Candidate added successfully",
        "success"
    )


    return redirect(
        url_for(
            "tenant.manage_lists"
        )
    )
@tenant_bp.route(
    "/candidate/edit/<int:candidate_id>",
    methods=["POST"]
)
def edit_candidate(candidate_id):


    ####################################################
    # Tenant authentication
    ####################################################

    if session.get("role") != "tenant":
        abort(403)


    tenant_id = session.get(
        "tenant_id"
    )



    ####################################################
    # Find candidate through tenant list
    ####################################################

    candidate = (
        Candidate.query
        .join(CandidateList)
        .filter(
            Candidate.id == candidate_id,
            CandidateList.tenant_id == tenant_id
        )
        .first()
    )


    if not candidate:
        abort(403)



    ####################################################
    # Update
    ####################################################

    name = request.form.get(
        "name",
        ""
    ).strip()


    if not name:

        flash(
            "Candidate name is required",
            "danger"
        )

        return redirect(
            url_for(
                "tenant.manage_lists"
            )
        )


    candidate.name = name


    db.session.commit()



    flash(
        "Candidate updated successfully",
        "success"
    )


    return redirect(
        url_for(
            "tenant.manage_lists"
        )
    )
@tenant_bp.route(
    "/candidate/delete/<int:candidate_id>",
    methods=["POST"]
)
def delete_candidate(candidate_id):


    ####################################################
    # Tenant authentication
    ####################################################

    if session.get("role") != "tenant":
        abort(403)


    tenant_id = session.get(
        "tenant_id"
    )



    ####################################################
    # Validate ownership
    ####################################################

    candidate = (
        Candidate.query
        .join(CandidateList)
        .filter(
            Candidate.id == candidate_id,
            CandidateList.tenant_id == tenant_id
        )
        .first()
    )


    if not candidate:
        abort(403)



    ####################################################
    # Delete
    ####################################################

    db.session.delete(candidate)

    db.session.commit()



    flash(
        "Candidate deleted successfully",
        "success"
    )


    return redirect(
        url_for(
            "tenant.manage_lists"
        )
    )
@tenant_bp.route(
    "/candidate/move/<int:candidate_id>",
    methods=["POST"]
)
def move_candidate(candidate_id):


    ####################################################
    # Tenant authentication
    ####################################################

    if session.get("role") != "tenant":
        abort(403)


    tenant_id = session.get(
        "tenant_id"
    )



    ####################################################
    # Find candidate owned by tenant
    ####################################################

    candidate = (
        Candidate.query
        .join(CandidateList)
        .filter(
            Candidate.id == candidate_id,
            CandidateList.tenant_id == tenant_id
        )
        .first()
    )


    if not candidate:
        abort(403)



    ####################################################
    # Destination list
    ####################################################

    new_list_id = request.form.get(
        "list_id"
    )


    if not new_list_id:
        abort(400)



    destination_list = CandidateList.query.filter_by(
        id=int(new_list_id),
        tenant_id=tenant_id
    ).first()


    if not destination_list:
        abort(403)



    ####################################################
    # Move candidate
    ####################################################

    candidate.list_id = destination_list.id


    db.session.commit()



    flash(
        "Candidate moved successfully",
        "success"
    )


    return redirect(
        url_for(
            "tenant.manage_lists"
        )
    )
@tenant_bp.route("/results")
def tenant_results():

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("auth.login"))


    ##################################################
    # Get tenant districts
    ##################################################

    districts = (
    District.query
    .join(tenant_district)
    .filter(
        tenant_district.c.tenant_id == tenant.id
    )
    .all()
)


    ##################################################
    # Prepare template data
    ##################################################

    results = {}


    for district in districts:

        votes = (
    Vote.query
    .join(Elector, Vote.elector_id == Elector.id)
    .filter(
        Elector.district_id == district.id
    )
    .all()
)


        rows = []

        for vote in votes:

            candidate = vote.candidate
            elector = vote.elector


            rows.append({

                "district": district.name,

                "ballot_pen": (
                    vote.ballot_pen.name
                    if vote.ballot_pen
                    else ""
                ),

                "list_name": (
                    candidate.candidate_list.name
                    if candidate
                    and candidate.candidate_list
                    else ""
                ),

                "candidate_name": (
                    candidate.name
                    if candidate
                    else ""
                ),

                "candidate_id": (
                    candidate.id
                    if candidate
                    else ""
                )
            })


        results[district.id] = rows


    ##################################################
    # Render page
    ##################################################

    return render_template(
        "tenant/results.html",
        results=results
    )
# ==========================================================
# VIEW ELECTORS
# ==========================================================

@tenant_bp.route("/electors")
def view_electors():

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("auth.login"))

    ####################################################
    # Selected districts
    ####################################################

    districts = get_selected_districts(
        tenant
    )

    district_ids = [
        d.id for d in districts
    ]

    ####################################################
    # Get electors
    ####################################################

    electors = (
        Elector.query
        .filter(
            Elector.district_id.in_(district_ids)
        )
        .order_by(
            Elector.district_id,
            Elector.elector_id
        )
        .all()
    )

    return render_template(
        "tenant/view_electors.html",
        electors=electors,
        districts=tenant.districts,
        selected_district=request.args.get(
            "district_id",
            type=int
        )
    )
@tenant_bp.route("/results/download")
def download_all_results():

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("auth.login"))

    ##################################################
    # Get tenant districts
    ##################################################

    districts = District.query.filter_by(
        tenant_id=tenant.id
    ).all()

    if not districts:
        return Response(
            "No districts found for this tenant.",
            mimetype="text/plain"
        )


    district_ids = [
        d.id for d in districts
    ]


    ##################################################
    # Get all votes for tenant districts
    ##################################################

    votes = (
        Vote.query
        .join(Elector)
        .filter(
            Elector.district_id.in_(district_ids)
        )
        .all()
    )


    ##################################################
    # Build CSV
    ##################################################

    output = StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "District",
        "Ballot Pen",
        "List Name",
        "Candidate Name",
        "Candidate ID"
    ])


    for vote in votes:

        elector = vote.elector
        candidate = vote.candidate


        writer.writerow([
            elector.district.name
                if elector.district else "",

            vote.ballot_pen.name
                if vote.ballot_pen else "",

            candidate.candidate_list.name
                if candidate and candidate.candidate_list
                else "",

            candidate.name
                if candidate
                else "",

            candidate.id
                if candidate
                else ""
        ])


    ##################################################
    # Return download
    ##################################################

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )

    response.headers["Content-Disposition"] = (
        "attachment; filename=tenant_results.csv"
    )

    return response