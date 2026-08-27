from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response,
    abort,
    make_response
)
from ...routes.frontend import is_logged_in
from collections import defaultdict
from sqlalchemy.orm import joinedload
from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)
from ...db.tenant_engine import get_tenant_session
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
    BallotPenAccount,
    PoliticalAllegiance,
    ElectorSubmission
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
def is_tenant_logged_in():

    return (
        session.get("tenant_id") is not None
        and
        session.get("tenant_db") is not None
    )
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

    if session.get("role") != "tenant":
        abort(403)

    tenant = get_current_tenant()

    if tenant is None:
        abort(403)

    tenant_session = get_tenant_session(
        tenant.db_name
    )

    try:

        # ==========================================
        # LOAD CANDIDATE LISTS
        # ==========================================

        lists = (
            tenant_session.query(
                CandidateList
            )
            .all()
        )

        # ==========================================
        # LOAD DISTRICTS
        # ==========================================

        districts = (
            db.session.query(
                District
            )
            .all()
        )

        district_map = {
            district.id: district.name
            for district in districts
        }

        # ==========================================
        # LOAD POLITICAL ALLEGIANCES
        # ==========================================

        allegiances = (
            tenant_session.query(
                PoliticalAllegiance
            )
            .all()
        )

        print(
            "ALLEGIANCES:",
            [
                (a.id, a.name, a.district_id)
                for a in allegiances
            ]
        )

        return render_template(
            "tenant/manage_lists.html",
            lists=lists,
            districts=districts,
            district_map=district_map,
            allegiances=allegiances
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
            "تم حذف المرشح بنجاح",
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
            "تم نقل المرشح بنجاح",
            "success"
        )


        return redirect(
            url_for(
                "tenant.manage_lists"
            )
        )


    finally:

        tenant_session.close()
from sqlalchemy import func

@tenant_bp.route("/results")
def tenant_results():

    # ==========================================
    # GET TENANT DATABASE
    # ==========================================

    db_name = session.get(
        "tenant_db"
    )

    if not db_name:

        flash(
            "Tenant database not found",
            "danger"
        )

        return redirect(
            url_for("tenant.dashboard")
        )


    # ==========================================
    # GET CURRENT TENANT
    # ==========================================

    tenant_id = session.get(
        "tenant_id"
    )


    # ==========================================
    # OPEN TENANT DATABASE
    # ==========================================

    tenant_session = get_tenant_session(
        db_name
    )


    try:

        # ==========================================
        # GROUP VOTES
        # ==========================================

        vote_rows = (

            tenant_session.query(

                Vote.ballot_pen_id,

                Vote.district_id,

                Vote.subdistrict_id,

                Vote.list_id,

                Vote.candidate_id,

                func.count(
                    Vote.id
                ).label(
                    "votes"
                )

            )

            .group_by(

                Vote.ballot_pen_id,

                Vote.district_id,

                Vote.subdistrict_id,

                Vote.list_id,

                Vote.candidate_id

            )

            .all()

        )


        # ==========================================
        # BUILD RESULTS
        # ==========================================

        results = []


        for row in vote_rows:


            # ======================================
            # GET BALLOT PEN FROM MASTER DB
            # ======================================

            ballot_pen = db.session.get(
                BallotPen,
                row.ballot_pen_id
            )


            # ======================================
            # DEFAULT VALUES
            # ======================================

            ballot_pen_code = ""

            village_name = ""

            polling_center_name = ""

            room_name = ""


            # ======================================
            # BALLOT PEN INFORMATION
            # ======================================

            if ballot_pen:

                # ----------------------------------
                # BALLOT PEN CODE
                # ----------------------------------

                ballot_pen_code = (
                    ballot_pen.code
                    or ""
                )


                # ----------------------------------
                # VILLAGE
                # ----------------------------------

                village_name = (
                    ballot_pen.village
                    or ""
                )


                # ----------------------------------
                # POLLING CENTER
                # ----------------------------------

                if ballot_pen.polling_center:

                    polling_center_name = (
                        ballot_pen
                        .polling_center
                        .name
                        or ""
                    )


                # ----------------------------------
                # ROOM
                # ----------------------------------

                if ballot_pen.room:

                    room_name = (
                        ballot_pen
                        .room
                        .name
                        or ""
                    )


            # ======================================
            # GET LIST NAME
            # ======================================

            list_name = None


            if row.list_id:

                candidate_list = (

                    tenant_session.query(
                        CandidateList
                    )

                    .filter_by(
                        id=row.list_id
                    )

                    .first()

                )


                if candidate_list:

                    list_name = (
                        candidate_list.name
                    )


            # ======================================
            # GET CANDIDATE NAME
            # ======================================

            candidate_name = None


            if row.candidate_id:

                candidate = (

                    tenant_session.query(
                        Candidate
                    )

                    .filter_by(
                        id=row.candidate_id
                    )

                    .first()

                )


                if candidate:

                    candidate_name = (
                        candidate.name
                    )


            # ======================================
            # ADD RESULT
            # ======================================

            results.append({

                # -------------------------------
                # TENANT
                # -------------------------------

                "tenant_id":
                    tenant_id,


                # -------------------------------
                # DISTRICT
                # -------------------------------

                "district_id":
                    row.district_id,


                # -------------------------------
                # SUBDISTRICT
                # -------------------------------

                "subdistrict_id":
                    row.subdistrict_id,


                # -------------------------------
                # VILLAGE
                # IMPORTANT:
                # template expects r.village
                # -------------------------------

                "village":
                    village_name,


                # -------------------------------
                # POLLING CENTER
                # -------------------------------

                "polling_center_name":
                    polling_center_name,


                # -------------------------------
                # ROOM
                # -------------------------------

                "room_name":
                    room_name,


                # -------------------------------
                # BALLOT PEN CODE
                # IMPORTANT:
                # template expects r.ballot_pen_code
                # -------------------------------

                "ballot_pen_code":
                    ballot_pen_code,


                # -------------------------------
                # LIST
                # -------------------------------

                "list_name":
                    list_name,


                # -------------------------------
                # CANDIDATE
                # -------------------------------

                "candidate_name":
                    candidate_name,


                # -------------------------------
                # VOTES
                # -------------------------------

                "votes":
                    row.votes

            })


        # ==========================================
        # TOTAL VALID/BLANK VOTES
        # ==========================================

        vote_count = (

            tenant_session.query(
                Vote
            )

            .count()

        )


        # ==========================================
        # RENDER
        # ==========================================

        return render_template(

            "tenant/results.html",

            results=results,

            vote_count=vote_count

        )


    finally:

        tenant_session.close()
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
# ==========================================================
# VIEW SUBMITTED ELECTORS
# ==========================================================

# ==========================================================
# VIEW SUBMITTED ELECTORS
# ==========================================================

@tenant_bp.route("/view-submitted-electors")
def view_submitted_electors():

    # ============================================
    # CHECK TENANT LOGIN
    # ============================================

    tenant_id = session.get("tenant_id")
    db_name = session.get("tenant_db")

    if not tenant_id or not db_name:

        flash(
            "يرجى تسجيل الدخول أولاً.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )

    # ============================================
    # GET TENANT
    # ============================================

    tenant = Tenant.query.get(tenant_id)

    if tenant is None:

        flash(
            "لم يتم العثور على الزبون.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )

    # ============================================
    # OPEN TENANT DATABASE
    # ============================================

    tenant_session = get_tenant_session(db_name)

    try:

        # ========================================
        # GET SUBMITTED ELECTORS
        # ========================================

        submissions = (
            tenant_session
            .query(ElectorSubmission)
            .filter(
                ElectorSubmission.submitted_at.isnot(None)
            )
            .order_by(
                ElectorSubmission.submitted_at.desc()
            )
            .all()
        )

        # ========================================
        # GET BALLOT PEN IDs
        # ========================================

        ballot_pen_ids = {
            submission.ballot_pen_id
            for submission in submissions
            if submission.ballot_pen_id is not None
        }

        # ========================================
        # GET BALLOT PENS FROM MASTER DATABASE
        # ========================================

        ballot_pens = {}

        if ballot_pen_ids:

            pens = (
                BallotPen.query
                .filter(
                    BallotPen.id.in_(ballot_pen_ids)
                )
                .all()
            )

            ballot_pens = {
                pen.id: pen
                for pen in pens
            }

        # ========================================
        # GROUP BY DISTRICT
        # ========================================

        electors = {}

        for submission in submissions:

            district_id = submission.district_id

            if district_id not in electors:
                electors[district_id] = []

            electors[district_id].append(
                submission
            )

        # ========================================
        # DISPLAY
        # ========================================

        return render_template(
            "tenant/electors.html",
            electors=electors,
            tenant=tenant,
            ballot_pens=ballot_pens
        )

    finally:

        tenant_session.close()
# ==========================================================
# DOWNLOAD ELECTORS CSV
# ==========================================================

@tenant_bp.route(
    "/electors/download/<int:district_id>"
)
def download_electors(district_id):

    # ======================================================
    # GET CURRENT TENANT
    # ======================================================

    tenant = get_current_tenant()

    if tenant is None:

        return redirect(
            url_for("auth.login")
        )

    # ======================================================
    # SECURITY CHECK
    # ======================================================

    if not tenant_has_district(
        tenant,
        district_id
    ):

        abort(403)

    # ======================================================
    # GET TENANT DATABASE
    # ======================================================

    db_name = session.get(
        "tenant_db"
    )

    if not db_name:

        flash(
            "لم يتم العثور على قاعدة بيانات الزبون.",
            "danger"
        )

        return redirect(
            url_for("tenant.dashboard")
        )

    # ======================================================
    # OPEN TENANT DATABASE SESSION
    # ======================================================

    tenant_session = get_tenant_session(
        db_name
    )

    try:

        # ==================================================
        # GET ELECTOR SUBMISSIONS
        # IMPORTANT:
        # This queries ElectorSubmission, NOT Elector
        # ==================================================

        submissions = (

            tenant_session.query(
                ElectorSubmission
            )

            .filter(
                ElectorSubmission.district_id
                == district_id
            )

            .filter(
                ElectorSubmission.submitted_at.isnot(None)
            )

            .order_by(
                ElectorSubmission.submitted_at.desc()
            )

            .all()
        )

        # ==================================================
        # CREATE CSV
        # ==================================================

        output = StringIO()

        writer = csv.writer(
            output
        )

        # ==================================================
        # CSV HEADERS
        # ==================================================

        writer.writerow([

            "Tenant ID",

            "District ID",

            "Ballot Pen Code",

            "Elector ID",

            "Elector Submission Time"

        ])

        # ==================================================
        # WRITE SUBMISSIONS
        # ==================================================

        for submission in submissions:

            # ----------------------------------------------
            # DEFAULT BALLOT PEN CODE
            # ----------------------------------------------

            ballot_pen_code = ""

            # ----------------------------------------------
            # GET BALLOT PEN FROM MASTER DATABASE
            # ----------------------------------------------

            if submission.ballot_pen_id is not None:

                ballot_pen = db.session.get(

                    BallotPen,

                    submission.ballot_pen_id

                )

                if ballot_pen is not None:

                    ballot_pen_code = ballot_pen.code

            # ----------------------------------------------
            # WRITE CSV ROW
            # ----------------------------------------------

            writer.writerow([

    # Tenant ID
    tenant.id,

    # District ID
    submission.district_id,

    # Ballot Pen Code
    ballot_pen_code,

    # Elector ID
    submission.elector_code,

    # Submission Time
    submission.submitted_at.strftime(
        "%Y-%m-%d %H:%M"
    )
    if submission.submitted_at
    else ""

])

    finally:

        # ==================================================
        # CLOSE TENANT DATABASE SESSION
        # ==================================================

        tenant_session.close()

    # ======================================================
    # RETURN CSV FILE
    # ======================================================

    output.seek(0)

    filename = (
        f"submitted_electors_district_"
        f"{district_id}.csv"
    )

    response = make_response(
        output.getvalue()
    )

    response.headers[
        "Content-Disposition"
    ] = (
        f"attachment; filename={filename}"
    )

    response.headers[
        "Content-Type"
    ] = (
        "text/csv; charset=utf-8"
    )

    return response

    # ======================================================
    # RESPONSE
    # ======================================================

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )

    response.headers[
        "Content-Disposition"
    ] = (
        "attachment; "
        f"filename=electors_district_{district_id}.csv"
    )

    return response
@tenant_bp.route("/results/download")
def download_all_results():

    # ==================================================
    # CHECK LOGGED-IN TENANT
    # ==================================================

    tenant = get_current_tenant()

    if tenant is None:
        return redirect(
            url_for("auth.login")
        )


    # ==================================================
    # GET TENANT DATABASE
    # ==================================================

    db_name = session.get(
        "tenant_db"
    )

    if not db_name:
        return Response(
            "Tenant database not found.",
            mimetype="text/plain",
            status=400
        )


    # ==================================================
    # OPEN TENANT DATABASE SESSION
    # ==================================================

    tenant_session = get_tenant_session(
        db_name
    )


    try:

        # ==================================================
        # GROUP VOTES
        #
        # BLANK:
        #   list_id      = NULL
        #   candidate_id = NULL
        #
        # LIST ONLY:
        #   list_id      = ID
        #   candidate_id = NULL
        #
        # LIST + CANDIDATE:
        #   list_id      = ID
        #   candidate_id = ID
        #
        # CANCELED PAPERS:
        #   Stored in CanceledPaper
        #   Therefore NOT included here.
        # ==================================================

        vote_rows = (

            tenant_session

            .query(

                Vote.ballot_pen_id.label(
                    "ballot_pen_id"
                ),

                Vote.list_id.label(
                    "list_id"
                ),

                Vote.candidate_id.label(
                    "candidate_id"
                ),

                func.count(
                    Vote.id
                ).label(
                    "vote_count"
                )

            )

            .group_by(

                Vote.ballot_pen_id,

                Vote.list_id,

                Vote.candidate_id

            )

            .all()
        )


        # ==================================================
        # CREATE CSV
        # ==================================================

        output = StringIO()

        writer = csv.writer(
            output
        )


        # ==================================================
        # CSV HEADER
        # ==================================================

        writer.writerow([

            "Tenant ID",

            "District ID",

            "Ballot Pen Code",

            "List Name",

            "Candidate Name",

            "Number of Votes"

        ])


        # ==================================================
        # BUILD CSV
        # ==================================================

        for row in vote_rows:


            # ==============================================
            # GET BALLOT PEN FROM MASTER DATABASE
            # ==============================================

            ballot_pen = db.session.get(
                BallotPen,
                row.ballot_pen_id
            )


            if not ballot_pen:
                continue


            # ==================================================
            # DEFAULT
            #
            # IMPORTANT:
            #
            # Start with the literal STRING "None".
            #
            # This guarantees that "None" is written into
            # the CSV instead of leaving the cell empty.
            # ==================================================

            list_name = "None"

            candidate_name = "None"


            # ==================================================
            # BLANK VOTE
            #
            # list_id      = None
            # candidate_id = None
            #
            # CSV:
            #
            # List Name      = None
            # Candidate Name = None
            # ==================================================

            if (
                row.list_id is None
                and
                row.candidate_id is None
            ):

                list_name = "None"

                candidate_name = "None"


            # ==================================================
            # LIST ONLY
            #
            # list_id      = ID
            # candidate_id = None
            #
            # CSV:
            #
            # List Name      = actual list name
            # Candidate Name = None
            # ==================================================

            elif (
                row.list_id is not None
                and
                row.candidate_id is None
            ):

                candidate_list = (

                    tenant_session

                    .query(
                        CandidateList
                    )

                    .filter_by(
                        id=row.list_id
                    )

                    .first()
                )


                if candidate_list:

                    list_name = (
                        candidate_list.name
                    )

                else:

                    list_name = "None"


                candidate_name = "None"


            # ==================================================
            # LIST + CANDIDATE
            #
            # list_id      = ID
            # candidate_id = ID
            #
            # CSV:
            #
            # List Name      = actual list name
            # Candidate Name = actual candidate name
            # ==================================================

            elif (
                row.list_id is not None
                and
                row.candidate_id is not None
            ):

                # ----------------------------------------------
                # GET LIST
                # ----------------------------------------------

                candidate_list = (

                    tenant_session

                    .query(
                        CandidateList
                    )

                    .filter_by(
                        id=row.list_id
                    )

                    .first()
                )


                if candidate_list:

                    list_name = (
                        candidate_list.name
                    )

                else:

                    list_name = "None"


                # ----------------------------------------------
                # GET CANDIDATE
                # ----------------------------------------------

                candidate = (

                    tenant_session

                    .query(
                        Candidate
                    )

                    .filter_by(
                        id=row.candidate_id
                    )

                    .first()
                )


                if candidate:

                    candidate_name = (
                        candidate.name
                    )

                else:

                    candidate_name = "None"


            # ==================================================
            # WRITE CSV ROW
            # ==================================================

            writer.writerow([

                tenant.id,

                ballot_pen.district_id,

                ballot_pen.code,

                list_name,

                candidate_name,

                row.vote_count

            ])


        # ==================================================
        # RETURN CSV
        # ==================================================

        response = Response(

            output.getvalue(),

            mimetype="text/csv"

        )


        response.headers[
            "Content-Disposition"
        ] = (

            "attachment; "
            "filename=tenant_results.csv"

        )


        return response


    finally:

        tenant_session.close()
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

        political_allegiance_id = request.form.get(
            "political_allegiance_id",
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

        if (
            not name
            or not sect_id
            or not political_allegiance_id
        ):
            flash(
                "اسم المرشح والطائفة والانتماء السياسي مطلوبان",
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

        allegiance = (
            tenant_session.query(
                PoliticalAllegiance
            )
            .filter_by(
                id=political_allegiance_id,
                district_id=candidate_list.district_id
            )
            .first()
        )

        if allegiance is None:
            flash(
                "الانتماء السياسي غير صالح لهذه الدائرة",
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
            district_id=candidate_list.district_id,
            subdistrict_id=subdistrict_id,
            sect_id=sect_id,
            political_allegiance_id=political_allegiance_id
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

    try:

        sects = (
            db.session.query(Sect)
            .join(
                SubdistrictSectSeat,
                Sect.id == SubdistrictSectSeat.sect_id
            )
            .filter(
                SubdistrictSectSeat.subdistrict_id == subdistrict_id
            )
            .order_by(
                Sect.name
            )
            .all()
        )

        print(
            "SUBDISTRICT ID:",
            subdistrict_id
        )

        print(
            "SECTS FOUND:",
            [
                (s.id, s.name)
                for s in sects
            ]
        )

        return jsonify([
            {
                "id": s.id,
                "name": s.name
            }
            for s in sects
        ])

    except Exception as e:

        print(
            "SUBDISTRICT SECTS ERROR:",
            repr(e)
        )

        raise
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
@tenant_bp.route(
    "/manage-allegiances"
)
def manage_allegiances():

    if not is_tenant_logged_in():
        return redirect(
            url_for("tenant_bp.login")
        )


    db_name = session.get(
        "tenant_db"
    )


    if not db_name:

        flash(
            "Tenant database not found.",
            "danger"
        )

        return redirect(
            url_for("tenant_bp.login")
        )


    tenant_session = get_tenant_session(
        db_name
    )


    try:

        tenant = (
            db.session.query(Tenant)
            .filter_by(
                db_name=db_name
            )
            .first()
        )


        if not tenant:

            flash(
                "Tenant not found.",
                "danger"
            )

            return redirect(
                url_for("tenant_bp.login")
            )


        districts = (
            tenant.districts
        )


        district_ids = [
            district.id
            for district in districts
        ]


        allegiances = (
            tenant_session
            .query(PoliticalAllegiance)
            .filter(
                PoliticalAllegiance.district_id.in_(
                    district_ids
                )
            )
            .order_by(
                PoliticalAllegiance.district_id,
                PoliticalAllegiance.name
            )
            .all()
        )


        district_map = {

            district.id: district.name

            for district in districts

        }


        return render_template(

            "tenant/manage_allegiances.html",

            allegiances=allegiances,

            districts=districts,

            district_map=district_map

        )


    finally:

        tenant_session.close()
@tenant_bp.route(
    "/create-allegiance",
    methods=["POST"]
)
def create_allegiance():

    if not is_tenant_logged_in():
        return redirect(
            url_for("tenant_bp.login")
        )


    db_name = session.get(
        "tenant_db"
    )


    if not db_name:

        flash(
            "Tenant database not found.",
            "danger"
        )

        return redirect(
            url_for("tenant_bp.login")
        )


    name = request.form.get(
        "name",
        ""
    ).strip()


    district_id = request.form.get(
        "district_id",
        type=int
    )


    if not name:

        flash(
            "يرجى إدخال اسم الانتماء السياسي.",
            "danger"
        )

        return redirect(
            url_for(
                "tenant_bp.manage_allegiances"
            )
        )


    if not district_id:

        flash(
            "يرجى اختيار الدائرة.",
            "danger"
        )

        return redirect(
            url_for(
                "tenant_bp.manage_allegiances"
            )
        )


    # -----------------------------------------
    # Verify that this district belongs
    # to the logged-in tenant
    # -----------------------------------------

    tenant = (
        db.session.query(Tenant)
        .filter_by(
            db_name=db_name
        )
        .first()
    )


    allowed_district_ids = [

        district.id

        for district in tenant.districts

    ]


    if district_id not in allowed_district_ids:

        flash(
            "هذه الدائرة غير مسموح بها لهذا المستخدم.",
            "danger"
        )

        return redirect(
            url_for(
                "tenant.manage_allegiances"
            )
        )


    tenant_session = get_tenant_session(
        db_name
    )


    try:

        existing = (

            tenant_session
            .query(PoliticalAllegiance)
            .filter_by(
                district_id=district_id,
                name=name
            )
            .first()

        )


        if existing:

            flash(
                "هذا الانتماء السياسي موجود مسبقاً في هذه الدائرة.",
                "warning"
            )

            return redirect(
                url_for(
                    "tenant_bp.manage_allegiances"
                )
            )


        allegiance = PoliticalAllegiance(

            district_id=district_id,

            name=name

        )


        tenant_session.add(
            allegiance
        )


        tenant_session.commit()


        flash(
            "تم إنشاء الانتماء السياسي بنجاح.",
            "success"
        )


    except Exception as error:

        tenant_session.rollback()

        print(
            "CREATE ALLEGIANCE ERROR:",
            repr(error)
        )


        flash(
            "حدث خطأ أثناء إنشاء الانتماء السياسي.",
            "danger"
        )


    finally:

        tenant_session.close()


    return redirect(
        url_for(
            "tenant.manage_allegiances"
        )
    )
@tenant_bp.route(
    "/delete-allegiance/<int:allegiance_id>",
    methods=["POST"]
)
def delete_allegiance(
    allegiance_id
):

    if not is_tenant_logged_in():
        return redirect(
            url_for("tenant_bp.login")
        )


    db_name = session.get(
        "tenant_db"
    )


    if not db_name:

        return redirect(
            url_for("tenant_bp.login")
        )


    tenant_session = get_tenant_session(
        db_name
    )


    try:

        allegiance = (

            tenant_session
            .query(PoliticalAllegiance)
            .filter_by(
                id=allegiance_id
            )
            .first()

        )


        if not allegiance:

            flash(
                "الانتماء السياسي غير موجود.",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant_bp.manage_allegiances"
                )
            )


        # ---------------------------------
        # Security check:
        # Ensure this allegiance belongs
        # to one of the tenant's districts
        # ---------------------------------

        tenant = (
            db.session.query(Tenant)
            .filter_by(
                db_name=db_name
            )
            .first()
        )


        allowed_district_ids = [

            district.id

            for district in tenant.districts

        ]


        if allegiance.district_id not in allowed_district_ids:

            flash(
                "غير مسموح بحذف هذا الانتماء.",
                "danger"
            )

            return redirect(
                url_for(
                    "tenant.manage_allegiances"
                )
            )


        # ---------------------------------
        # Check candidates
        # ---------------------------------

        candidate_count = (

            tenant_session
            .query(Candidate)
            .filter_by(
                political_allegiance_id=allegiance.id
            )
            .count()

        )


        if candidate_count > 0:

            flash(
                "لا يمكن حذف هذا الانتماء لأنه مرتبط بمرشحين.",
                "warning"
            )

            return redirect(
                url_for(
                    "tenant.manage_allegiances"
                )
            )


        tenant_session.delete(
            allegiance
        )


        tenant_session.commit()


        flash(
            "تم حذف الانتماء السياسي بنجاح.",
            "success"
        )


    except Exception as error:

        tenant_session.rollback()

        print(
            "DELETE ALLEGIANCE ERROR:",
            repr(error)
        )


        flash(
            "حدث خطأ أثناء حذف الانتماء السياسي.",
            "danger"
        )


    finally:

        tenant_session.close()


    return redirect(
        url_for(
            "tenant.manage_allegiances"
        )
    )