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
from sqlalchemy.orm import joinedload
from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)
from collections import OrderedDict
from sqlalchemy import func, distinct

from io import StringIO
import csv

from ... import db
from flask import jsonify
from ...models.master_models import (
    Sect,
    Tenant,
    District,
    BallotPen,
    Party,
    User,
    tenant_district,
    Elector,
    SubdistrictSectSeat,SubDistrict
)

from ...models.tenant_models import (
    CandidateList,
    Candidate,
    Vote,
    BallotPenAccount
)
from ...db.tenant_engine import get_tenant_session
from ...db.master_db import db
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
        return redirect(url_for("auth.login"))

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

@tenant_bp.route("/ballot-pens")
def ballot_pens():

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))

    pens = (
        BallotPen.query
        .order_by(
            BallotPen.district_id,
            BallotPen.subdistrict_id,
            BallotPen.village,
            BallotPen.polling_center_id,
            BallotPen.room_id,
            BallotPen.serial_number
        )
        .all()
    )

    grouped_pens = OrderedDict()

    for pen in pens:

        key = (
            pen.district_id,
            pen.subdistrict_id,
            pen.village,
            pen.polling_center_id,
            pen.room_id,
            pen.serial_number
        )

        if key not in grouped_pens:
            grouped_pens[key] = pen

    tenant_session = get_tenant_session(tenant.db_name)

    for pen in grouped_pens.values():

        pen.account = (
            tenant_session.query(BallotPenAccount)
            .filter_by(ballot_pen_id=pen.id)
            .first()
        )

    return render_template(
        "tenant/generate_ballot_pens.html",
        ballot_pens=list(grouped_pens.values())
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


def get_polling_center_code(polling_center):
    """
    Generate English polling center code.
    """

    if not polling_center:
        return "PC"


    name = polling_center.name.strip()


    # Manual mapping (recommended)
    mappings = {
        "مدرسة مار يوسف": "MY",
        "ثانوية المتن": "MT",
        "مدرسة البوشرية الرسمية": "BR",
    }


    if name in mappings:
        return mappings[name]


    # Fallback:
    # Keep only English letters if available
    english = "".join(
        c for c in name.upper()
        if c.isalpha() and c.isascii()
    )


    if english:
        return english[:3]


    # Final fallback
    return f"PC{polling_center.id}"



def get_room_code(room):

    """
    Generate room code.
    Example:
    غرفة رقم 1 -> R1
    Room 2 -> R2
    """

    if not room:
        return "R0"


    name = room.name


    import re

    number = re.search(
        r"\d+",
        name
    )


    if number:
        return f"R{number.group()}"


    return f"R{room.id}"
@tenant_bp.route(
    "/ballot-pens/<int:ballot_pen_id>/generate",
    methods=["POST"]
)
def generate_ballot_pen_credentials(ballot_pen_id):

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(
            url_for("tenant.login")
        )


    ballot_pen = BallotPen.query.get_or_404(
        ballot_pen_id
    )


    if ballot_pen.district not in tenant.districts:
        abort(403)



    # --------------------------------
    # TENANT DATABASE SESSION
    # --------------------------------

    tenant_session = get_tenant_session(
        tenant.db_name
    )



    # --------------------------------
    # Generate stable username
    #
    # Example:
    #
    # Tenant 1
    # District 13
    # Polling Center MY
    # Room 1
    # Pen 1
    #
    # => 1A13MYR1P1
    #
    # --------------------------------

    letter = get_tenant_letter(
        tenant.id
    )


    polling_center_code = get_polling_center_code(
        ballot_pen.polling_center
    )


    room_code = get_room_code(
        ballot_pen.room
    )


    username = (
        f"{tenant.id}"
        f"{letter}"
        f"{ballot_pen.district_id}"
        f"{polling_center_code}"
        f"{room_code}"
        f"P{ballot_pen.serial_number}"
    )



    # --------------------------------
    # Tenant BallotPenAccount
    # --------------------------------

    account = (
        tenant_session.query(BallotPenAccount)
        .filter_by(
            username=username
        )
        .first()
    )


    if account is None:

        account = BallotPenAccount(
            ballot_pen_id=ballot_pen.id,
            username=username,
            password=generate_password_hash(username)
        )

        tenant_session.add(account)


    else:

        account.password = generate_password_hash(
            username
        )



    # --------------------------------
    # Master User
    # --------------------------------

    user = User.query.filter_by(
        username=username,
        role="ballot_pen"
    ).first()


    if user is None:

        user = User(
            username=username,
            password=generate_password_hash(username),
            role="ballot_pen"
        )

        db.session.add(user)

        db.session.flush()



    # --------------------------------
    # Link pens belonging to the same
    # physical ballot station
    #
    # Same:
    # District
    # Polling Center
    # Room
    # Serial Number
    # Gender
    #
    # --------------------------------

    related_pens = (
        BallotPen.query
        .filter_by(
            district_id=ballot_pen.district_id,
            polling_center_id=ballot_pen.polling_center_id,
            room_id=ballot_pen.room_id,
            serial_number=ballot_pen.serial_number,
            gender_type=ballot_pen.gender_type
        )
        .all()
    )


    for pen in related_pens:

        if pen not in user.ballot_pens:

            user.ballot_pens.append(
                pen
            )



    tenant_session.commit()

    db.session.commit()



    flash(
        f"Credentials generated for Ballot Pen {username}.",
        "success"
    )


    return redirect(
        url_for(
            "tenant.ballot_pens"
        )
    )
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


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        lists = (
            tenant_session.query(CandidateList)
            .options(
                joinedload(
                    CandidateList.candidates
                )
            )
            .order_by(
                CandidateList.name
            )
            .all()
        )


        districts = get_selected_districts(
            tenant
        )


        district_map = {
            d.id:d.name
            for d in districts
        }


        return render_template(
            "tenant/manage_lists.html",
            lists=lists,
            districts=districts,
            district_map=district_map
        )


    finally:
        tenant_session.close()
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
        return redirect(
            url_for("tenant.login")
        )


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        districts = get_selected_districts(
            tenant
        )


        if request.method == "POST":


            ####################################################
            # Read form data
            ####################################################

            district_id = request.form.get(
                "district_id",
                type=int
            )


            name = request.form.get(
                "name",
                ""
            ).strip()



            ####################################################
            # Validate district
            ####################################################

            if not district_id:

                flash(
                    "District is required.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "tenant.manage_lists"
                    )
                )



            ####################################################
            # Validate tenant owns district
            ####################################################

            if not tenant_has_district(
                tenant,
                district_id
            ):

                abort(403)



            ####################################################
            # Validate list name
            ####################################################

            if not name:

                flash(
                    "List name is required.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "tenant.manage_lists"
                    )
                )



            ####################################################
            # Check duplicate list in district
            ####################################################

            existing = (
                tenant_session.query(
                    CandidateList
                )
                .filter_by(
                    district_id=district_id,
                    name=name
                )
                .first()
            )


            if existing:

                flash(
                    "A list with this name already exists in this district.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "tenant.manage_lists"
                    )
                )



            ####################################################
            # Create candidate list
            ####################################################

            candidate_list = CandidateList(
                name=name,
                district_id=district_id
            )


            tenant_session.add(
                candidate_list
            )


            tenant_session.commit()



            flash(
                "List created successfully.",
                "success"
            )


            return redirect(
                url_for(
                    "tenant.manage_lists"
                )
            )



        ####################################################
        # GET request
        ####################################################

        return render_template(
            "tenant/create_candidate_list.html",
            districts=districts
        )



    except Exception as e:

        tenant_session.rollback()

        print(
            "CREATE LIST ERROR:",
            repr(e)
        )

        raise



    finally:

        tenant_session.close()
@tenant_bp.route(
    "/subdistricts/<int:district_id>"
)
def get_subdistricts(district_id):

    tenant = get_current_tenant()

    if tenant is None:
        abort(403)


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        subdistricts = (
            tenant_session.query(
                SubDistrict
            )
            .filter_by(
                district_id=district_id
            )
            .order_by(
                SubDistrict.name
            )
            .all()
        )


        return {
            "subdistricts": [
                {
                    "id": subdistrict.id,
                    "name": subdistrict.name
                }
                for subdistrict in subdistricts
            ]
        }


    finally:

        tenant_session.close()
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
        return redirect(
            url_for("tenant.login")
        )


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        candidate_list = (
            tenant_session.query(
                CandidateList
            )
            .filter_by(
                id=list_id
            )
            .first()
        )


        if candidate_list is None:
            abort(404)



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
                    "اسم القائمة لا يمكن أن يكون فارغاً",
                    "danger"
                )

                return redirect(
                    url_for(
                        "tenant.edit_list",
                        list_id=list_id
                    )
                )


            candidate_list.name = name


            tenant_session.commit()


            flash(
                "تم تعديل القائمة بنجاح",
                "success"
            )


            return redirect(
                url_for(
                    "tenant.manage_lists"
                )
            )



        return render_template(
            "tenant/edit_list.html",
            list=candidate_list
        )


    except Exception as e:

        tenant_session.rollback()

        print(
            "EDIT LIST ERROR:",
            repr(e)
        )

        raise


    finally:

        tenant_session.close()
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
        return redirect(
            url_for("tenant.login")
        )


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        candidate_list = (
            tenant_session.query(
                CandidateList
            )
            .filter_by(
                id=list_id
            )
            .first()
        )


        if candidate_list is None:
            abort(404)


        tenant_session.delete(
            candidate_list
        )

        tenant_session.commit()


        flash(
            "List deleted successfully.",
            "success"
        )


        return redirect(
            url_for(
                "tenant.manage_lists"
            )
        )


    except Exception as e:

        tenant_session.rollback()

        print(
            "DATABASE ERROR:",
            repr(e)
        )

        raise


    finally:

        tenant_session.close()
@tenant_bp.route(
    "/candidate/add/<int:list_id>",
    methods=["GET", "POST"]
)
def add_candidate(list_id):

    ####################################################
    # Tenant authentication
    ####################################################

    if session.get("role") != "tenant":
        abort(403)

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(
            url_for("tenant.login")
        )

    master_session = db.session

    tenant_session = get_tenant_session(
        tenant.db_name
    )

    try:

        ####################################################
        # Validate candidate list
        ####################################################

        candidate_list = (
            tenant_session.query(
                CandidateList
            )
            .filter_by(
                id=list_id
            )
            .first()
        )

        if candidate_list is None:
            abort(404)

        ####################################################
        # Display form
        ####################################################

        if request.method == "GET":

            lists = (
                tenant_session.query(
                    CandidateList
                )
                .order_by(
                    CandidateList.name
                )
                .all()
            )

            available_sects = (
                master_session.query(
                    Sect
                )
                .join(
                    SubdistrictSectSeat,
                    Sect.id == SubdistrictSectSeat.sect_id
                )
                .filter(
                    SubdistrictSectSeat.subdistrict_id ==
                    candidate_list.subdistrict_id
                )
                .order_by(
                    Sect.name
                )
                .all()
            )

            return render_template(
                "tenant/create_candidate.html",
                candidate_list=candidate_list,
                lists=lists,
                sects=available_sects
            )

        ####################################################
        # Read form
        ####################################################

        name = request.form.get(
            "name",
            ""
        ).strip()

        selected_list_id = request.form.get(
            "list_id",
            type=int
        )

        sect_id = request.form.get(
            "sect_id",
            type=int
        )

        ####################################################
        # Validate input
        ####################################################

        if not name:

            flash(
                "Candidate name is required.",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.add_candidate",
                    list_id=list_id
                )
            )

        ####################################################
        # Validate selected list
        ####################################################

        selected_list = (
            tenant_session.query(
                CandidateList
            )
            .filter_by(
                id=selected_list_id
            )
            .first()
        )

        if selected_list is None:

            flash(
                "Please select a valid candidate list.",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.add_candidate",
                    list_id=list_id
                )
            )

        ####################################################
        # Get seat rule from master database
        ####################################################

        seat_rule = (
            master_session.query(
                SubdistrictSectSeat
            )
            .filter_by(
                subdistrict_id=selected_list.subdistrict_id,
                sect_id=sect_id
            )
            .first()
        )

        if seat_rule is None:

            flash(
                "This sect is not available for the selected subdistrict.",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.add_candidate",
                    list_id=list_id
                )
            )

        ####################################################
        # Count existing candidates in this list/sect
        ####################################################

        current_candidates = (
            tenant_session.query(
                Candidate
            )
            .filter_by(
                candidate_list_id=selected_list.id,
                sect_id=sect_id
            )
            .count()
        )

        ####################################################
        # Check seat limit
        ####################################################

        if current_candidates >= seat_rule.seats:

            flash(
                f"This list already contains the maximum number of candidates "
                f"({seat_rule.seats}) for the selected sect.",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.add_candidate",
                    list_id=list_id
                )
            )

        ####################################################
        # Create candidate
        ####################################################

        candidate = Candidate(
            name=name,
            candidate_list_id=selected_list.id,
            district_id=selected_list.district_id,
            subdistrict_id=selected_list.subdistrict_id,
            sect_id=sect_id
        )

        tenant_session.add(candidate)

        tenant_session.commit()

        ####################################################
        # Success
        ####################################################

        flash(
            "Candidate added successfully.",
            "success"
        )

        return redirect(
            url_for(
                "tenant.manage_lists"
            )
        )

    except Exception as e:

        tenant_session.rollback()

        print(
            "DATABASE ERROR:",
            repr(e)
        )

        raise

    finally:

        tenant_session.close()

@tenant_bp.route(
    "/candidate/edit/<int:candidate_id>",
    methods=["GET", "POST"]
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


    tenant = get_current_tenant()

    if tenant is None:
        return redirect(
            url_for("tenant.login")
        )


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        ####################################################
        # Find candidate in tenant database
        ####################################################

        candidate = (
            tenant_session.query(
                Candidate
            )
            .filter_by(
                id=candidate_id
            )
            .first()
        )


        if candidate is None:
            abort(404)


        ####################################################
        # Delete candidate
        ####################################################

        tenant_session.delete(candidate)

        tenant_session.commit()


        flash(
            "Candidate deleted successfully.",
            "success"
        )


        return redirect(
            url_for(
                "tenant.manage_lists"
            )
        )


    except Exception as e:

        tenant_session.rollback()

        print(
            "DELETE CANDIDATE ERROR:",
            repr(e)
        )

        raise


    finally:

        tenant_session.close()
@tenant_bp.route(
    "/candidate/move/<int:candidate_id>",
    methods=["POST"]
)
def move_candidate(candidate_id):

    ####################################################
    # Get current tenant
    ####################################################

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(
            url_for("tenant.login")
        )


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        ####################################################
        # Find candidate
        ####################################################

        candidate = (
            tenant_session.query(Candidate)
            .filter(
                Candidate.id == candidate_id
            )
            .first()
        )


        if not candidate:
            abort(404)


        ####################################################
        # Destination list
        ####################################################

        new_list_id = request.form.get(
            "list_id",
            type=int
        )


        if not new_list_id:
            abort(400)


        ####################################################
        # Find destination list
        ####################################################

        destination_list = (
            tenant_session.query(CandidateList)
            .filter_by(
                id=new_list_id
            )
            .first()
        )


        if not destination_list:
            abort(404)


        ####################################################
        # Move candidate
        ####################################################

        candidate.candidate_list_id = (
            destination_list.id
        )


        ####################################################
        # Save
        ####################################################

        tenant_session.commit()


        flash(
            "Candidate moved successfully.",
            "success"
        )


        return redirect(
            url_for(
                "tenant.manage_lists"
            )
        )


    finally:

        tenant_session.close()
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
@tenant_bp.route(
    "/ballot-pens/<int:ballot_pen_id>/credentials/edit",
    methods=["GET", "POST"]
)
def edit_ballot_pen_credentials(ballot_pen_id):

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))


    ballot_pen = BallotPen.query.get_or_404(
        ballot_pen_id
    )


    if ballot_pen.district not in tenant.districts:
        abort(403)


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    account = (
        tenant_session.query(BallotPenAccount)
        .filter_by(
            ballot_pen_id=ballot_pen.id
        )
        .first()
    )


    if account is None:
        abort(404)


    if request.method == "POST":

        account.username = request.form["username"]


        new_password = request.form.get(
            "password"
        )


        if new_password:
            account.password = generate_password_hash(
                new_password
            )


        tenant_session.commit()


        flash(
            "Ballot pen credentials updated",
            "success"
        )


        return redirect(
            url_for("tenant.ballot_pens")
        )


    return render_template(
        "tenant/edit_ballot_pen_credentials.html",
        account=account,
        ballot_pen=ballot_pen
    )
@tenant_bp.route(
    "/ballot-pens/<int:ballot_pen_id>/credentials/delete",
    methods=["POST"]
)
def delete_ballot_pen_credentials(ballot_pen_id):

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(url_for("tenant.login"))


    ballot_pen = BallotPen.query.get_or_404(
        ballot_pen_id
    )


    if ballot_pen.district not in tenant.districts:
        abort(403)


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    account = (
        tenant_session.query(BallotPenAccount)
        .filter_by(
            ballot_pen_id=ballot_pen.id
        )
        .first()
    )


    if account:

        tenant_session.delete(account)

        tenant_session.commit()


    flash(
        "Ballot pen credentials deleted",
        "success"
    )


    return redirect(
        url_for("tenant.ballot_pens")
    )
@tenant_bp.route(
    "/candidate-sects/<int:list_id>"
)
def candidate_sects(list_id):

    tenant = get_current_tenant()

    tenant_session = get_tenant_session(
        tenant.db_name
    )


    candidate_list = (
        tenant_session.query(
            CandidateList
        )
        .filter_by(
            id=list_id
        )
        .first()
    )


    sects = (
        db.session.query(Sect)
        .join(SubdistrictSectSeat)
        .filter(
            SubdistrictSectSeat.subdistrict_id ==
            candidate_list.subdistrict_id
        )
        .all()
    )


    return jsonify([
        {
            "id":s.id,
            "name":s.name
        }
        for s in sects
    ])
# ==========================================================
# ADD CANDIDATE FROM MANAGE LISTS MODAL
# ==========================================================

@tenant_bp.route(
    "/candidate/add-ajax",
    methods=["POST"]
)
def add_candidate_ajax():

    if session.get("role") != "tenant":
        abort(403)


    tenant = get_current_tenant()

    if tenant is None:
        abort(403)


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        # -----------------------------
        # Read form data
        # -----------------------------

        list_id = request.form.get(
            "list_id",
            type=int
        )

        subdistrict_id = request.form.get(
    "subdistrict_id",
    type=int
)
        name = request.form.get(
            "name",
            ""
        ).strip()


        sect_id = request.form.get(
            "sect_id",
            type=int
        )



        # -----------------------------
        # Validate list
        # -----------------------------

        candidate_list = (
            tenant_session.query(
                CandidateList
            )
            .filter_by(
                id=list_id
            )
            .first()
        )


        if candidate_list is None:
            abort(404)



        # -----------------------------
        # Validate input
        # -----------------------------

        if not name or not sect_id:

            flash(
                "اسم المرشح والطائفة مطلوبان",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.manage_lists"
                )
            )



        # -----------------------------
        # Validate sect seat
        # -----------------------------

        seat_rule = (
            db.session.query(
                SubdistrictSectSeat
            )
            .filter_by(
                subdistrict_id=
                    subdistrict_id,
                sect_id=sect_id
            )
            .first()
        )


        if seat_rule is None:

            flash(
                "هذه الطائفة غير متاحة لهذا القضاء",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.manage_lists"
                )
            )



        # -----------------------------
        # Check seat limit
        # -----------------------------

        count = (
            tenant_session.query(
                Candidate
            )
            .filter_by(
                candidate_list_id=list_id,
                sect_id=sect_id
            )
            .count()
        )


        if count >= seat_rule.seats:

            flash(
                "تم الوصول إلى العدد الأقصى للمقاعد لهذه الطائفة",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.manage_lists"
                )
            )



        # -----------------------------
        # Create candidate
        # -----------------------------

        candidate = Candidate(

            name=name,

            candidate_list_id=list_id,

            district_id=
                candidate_list.district_id,

            subdistrict_id=
                subdistrict_id,

            sect_id=sect_id
        )


        tenant_session.add(candidate)

        tenant_session.commit()



        flash(
            "تمت إضافة المرشح بنجاح",
            "success"
        )


        return redirect(
            url_for(
                "tenant.manage_lists"
            )
        )


    except Exception as e:

        tenant_session.rollback()

        print(
            "ADD CANDIDATE ERROR:",
            repr(e)
        )

        raise


    finally:

        tenant_session.close()
@tenant_bp.route(
    "/candidate-subdistricts/<int:list_id>"
)
def candidate_subdistricts(list_id):

    tenant = get_current_tenant()

    tenant_session = get_tenant_session(
        tenant.db_name
    )


    candidate_list = (
        tenant_session.query(
            CandidateList
        )
        .filter_by(
            id=list_id
        )
        .first()
    )


    if candidate_list is None:
        return jsonify([])


    subdistricts = (
        tenant_session.query(
            SubDistrict
        )
        .filter_by(
            district_id=candidate_list.district_id
        )
        .order_by(
            SubDistrict.name
        )
        .all()
    )


    return jsonify([
        {
            "id": s.id,
            "name": s.name
        }
        for s in subdistricts
    ])
@tenant_bp.route(
    "/list-subdistricts/<int:list_id>"
)
def list_subdistricts(list_id):

    tenant = get_current_tenant()

    tenant_session = get_tenant_session(
        tenant.db_name
    )


    candidate_list = (
        tenant_session.query(CandidateList)
        .filter_by(id=list_id)
        .first()
    )


    if candidate_list is None:
        return jsonify([])


    subdistricts = (
        db.session.query(SubDistrict)
        .filter_by(
            district_id=candidate_list.district_id
        )
        .order_by(
            SubDistrict.name
        )
        .all()
    )


    return jsonify([
        {
            "id": s.id,
            "name": s.name
        }
        for s in subdistricts
    ])
@tenant_bp.route(
    "/subdistrict-sects/<int:subdistrict_id>"
)
def subdistrict_sects(subdistrict_id):

    sects = (
        db.session.query(Sect)
        .join(
            SubdistrictSectSeat,
            Sect.id == SubdistrictSectSeat.sect_id
        )
        .filter(
            SubdistrictSectSeat.subdistrict_id == subdistrict_id
        )
        .all()
    )


    return jsonify([
        {
            "id": s.id,
            "name": s.name
        }
        for s in sects
    ])
@tenant_bp.route(
    "/update-list",
    methods=["POST"]
)
def update_list():

    tenant = get_current_tenant()

    if tenant is None:
        abort(403)


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        list_id = request.form.get(
            "list_id",
            type=int
        )


        name = request.form.get(
            "name",
            ""
        ).strip()


        district_id = request.form.get(
            "district_id",
            type=int
        )


        candidate_list = (
            tenant_session.query(
                CandidateList
            )
            .filter_by(
                id=list_id
            )
            .first()
        )


        if candidate_list is None:
            abort(404)



        if not name:

            flash(
                "اسم القائمة لا يمكن أن يكون فارغاً",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.manage_lists"
                )
            )



        # If changing district is allowed
        if district_id:

            if not tenant_has_district(
                tenant,
                district_id
            ):

                flash(
                    "لا يمكنك نقل القائمة إلى هذه الدائرة",
                    "danger"
                )

                return redirect(
                    url_for(
                        "tenant.manage_lists"
                    )
                )


            candidate_list.district_id = district_id



        candidate_list.name = name


        tenant_session.commit()


        flash(
            "تم تعديل القائمة بنجاح",
            "success"
        )


        return redirect(
            url_for(
                "tenant.manage_lists"
            )
        )


    except Exception as e:

        tenant_session.rollback()

        print(
            "UPDATE LIST ERROR:",
            repr(e)
        )

        raise


    finally:

        tenant_session.close()
@tenant_bp.route(
    "/update-candidate",
    methods=["POST"]
)
def update_candidate():

    tenant = get_current_tenant()

    if tenant is None:
        abort(403)


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        candidate_id = request.form.get(
            "candidate_id",
            type=int
        )

        name = request.form.get(
            "name",
            ""
        ).strip()


        list_id = request.form.get(
            "list_id",
            type=int
        )


        subdistrict_id = request.form.get(
            "subdistrict_id",
            type=int
        )


        sect_id = request.form.get(
            "sect_id",
            type=int
        )



        candidate = (
            tenant_session.query(
                Candidate
            )
            .filter_by(
                id=candidate_id
            )
            .first()
        )


        if candidate is None:
            abort(404)



        if not name or not list_id or not sect_id:

            flash(
                "اسم المرشح والقائمة والطائفة مطلوبة",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.manage_lists"
                )
            )



        candidate_list = (
            tenant_session.query(
                CandidateList
            )
            .filter_by(
                id=list_id
            )
            .first()
        )


        if candidate_list is None:
            abort(404)



        # Validate sect availability

        seat_rule = (
            db.session.query(
                SubdistrictSectSeat
            )
            .filter_by(
                subdistrict_id=subdistrict_id,
                sect_id=sect_id
            )
            .first()
        )


        if seat_rule is None:

            flash(
                "هذه الطائفة غير متاحة لهذا القضاء",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.manage_lists"
                )
            )



        # Check seat limit excluding this candidate

        count = (
            tenant_session.query(
                Candidate
            )
            .filter(
                Candidate.candidate_list_id == list_id,
                Candidate.sect_id == sect_id,
                Candidate.id != candidate_id
            )
            .count()
        )


        if count >= seat_rule.seats:

            flash(
                "لا يمكن تعديل المرشح: تم تجاوز عدد المقاعد المخصصة لهذه الطائفة",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.manage_lists"
                )
            )



        # Update candidate

        candidate.name = name

        candidate.candidate_list_id = list_id

        candidate.district_id = (
            candidate_list.district_id
        )

        candidate.subdistrict_id = (
            subdistrict_id
        )

        candidate.sect_id = (
            sect_id
        )


        tenant_session.commit()


        flash(
            "تم تعديل المرشح بنجاح",
            "success"
        )


        return redirect(
            url_for(
                "tenant.manage_lists"
            )
        )


    except Exception as e:

        tenant_session.rollback()

        print(
            "UPDATE CANDIDATE ERROR:",
            repr(e)
        )

        raise


    finally:

        tenant_session.close()