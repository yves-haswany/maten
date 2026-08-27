from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import re
from .. import db
from ..models.master_models import Elector, BallotPen, District, Tenant
from ..models.tenant_models import CandidateList, Candidate, Vote, BallotPenAccount, ElectorSubmission, CanceledPaper
from werkzeug.security import check_password_hash
import uuid
from ..db.tenant_base import TenantBase
from ..db.tenant_engine import get_tenant_session
import traceback

frontend_bp = Blueprint("frontend_bp", __name__)


# ----------------------------
# Utilities
# ----------------------------

def is_logged_in():
    return session.get("role") == "ballot_pen"


# ----------------------------
# LOGIN (Ballot Pen ONLY)
# ----------------------------

@frontend_bp.before_app_request
def check_single_session():
    if "ballot_pen_id" in session:
        pen = BallotPen.query.get(session["ballot_pen_id"])

        if not pen or pen.active_session_token != session.get("session_token"):
            session.clear()
            return redirect(url_for("auth.login"))


# ----------------------------
# LOGOUT
# ----------------------------

# ----------------------------
# DASHBOARD
# ----------------------------

@frontend_bp.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect(url_for("auth.login"))

    ballot_pen_ids = session.get("ballot_pen_ids", [])

    if not ballot_pen_ids:
        return redirect(url_for("auth.login"))

    ballot_pens = (
        BallotPen.query
        .filter(BallotPen.id.in_(ballot_pen_ids))
        .all()
    )

    if not ballot_pens:
        return redirect(url_for("auth.login"))

    # --------------------------------
    # Use first ballot pen for header
    # --------------------------------
    ballot_pen = ballot_pens[0]

    # Extract last 4 digits safely
    ballot_number = str(ballot_pen.serial_number).zfill(4)

    # ----------------------------
    # DISTRICT NAME MAPPING
    # ----------------------------
    district_names = {
        1: "دائرة بيروت الاولى",
        2: "دائرة بيروت الثانية",
        3: "دائرة الجنوب الاولى",
        4: "دائرة الجنوب الثانية",
        5: "دائرة الجنوب الثالثة",
        6: "دائرة البقاع الاولى",
        7: "دائرة البقاع الثانية",
        8: "دائرة البقاع الثالثة",
        9: "دائرة الشمال الاولى",
        10: "دائرة الشمال الثانية",
        11: "دائرة الشمال الثالثة",
        12: "دائرة جبل لبنان الاولى",
        13: "دائرة جبل لبنان الثانية (المتن)",
        14: "دائرة جبل لبنان الثالثة",
        15: "دائرة جبل لبنان الرابعة",
    }

    district_id = ballot_pen.district_id
    district_name = district_names.get(district_id, "غير معروف")

    return render_template(
        "frontend/dashboard.html",
        ballot_pens=ballot_pens,
        ballot_number=ballot_number,
        district_name=district_name
    )


# ----------------------------
# ENTER ELECTOR PAGE (GET ONLY)
# ----------------------------

@frontend_bp.route("/enter-electors")
def enter_electors():
    if not is_logged_in():
        return redirect(url_for("auth.login"))

    return render_template("frontend/enter_electors.html")


# ----------------------------
# SUBMIT ELECTOR
# ----------------------------

@frontend_bp.route("/submit-elector", methods=["POST"])
def submit_elector():

    print("1. submit_elector() called")

    if not is_logged_in():
        print("Not logged in")
        return redirect(url_for("auth.login"))


    #################################################
    # Elector ID
    #################################################

    elector_id_input = request.form.get(
        "elector_id",
        ""
    ).strip()

    print(
        "2. Elector ID entered:",
        elector_id_input
    )

    if not elector_id_input:

        flash(
            "Elector ID required",
            "danger"
        )

        return redirect(
            url_for("frontend_bp.enter_electors")
        )


    #################################################
    # Logged-in ballot pens
    #################################################

    ballot_pen_ids = session.get(
        "ballot_pen_ids",
        []
    )

    print(
        "3. Ballot pen IDs:",
        ballot_pen_ids
    )

    if not ballot_pen_ids:

        flash(
            "No ballot pen assigned",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )


    #################################################
    # Find elector (Master DB)
    #################################################

    # Get first ballot pen only for district filtering
    first_ballot_pen = db.session.get(
        BallotPen,
        ballot_pen_ids[0]
    )


    if first_ballot_pen is None:

        flash(
            "Ballot pen not found",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )


    elector = Elector.query.filter_by(
        elector_id=elector_id_input,
        district_id=first_ballot_pen.district_id
    ).first()


    print(
        "4. Elector:",
        elector
    )


    if elector is None:

        flash(
            "Elector not found in voter list",
            "danger"
        )

        return redirect(
            url_for("frontend_bp.enter_electors")
        )


    #################################################
    # Verify elector belongs to one of user's pens
    #################################################

    valid_ballot_pen = None


    for pen_id in ballot_pen_ids:

        pen = db.session.get(
            BallotPen,
            pen_id
        )

        if not pen:
            continue


        # District check
        if pen.district_id != elector.district_id:
            continue


        # Subdistrict check
        if pen.subdistrict_id != elector.subdistrict_id:
            continue


        #################################################
        # Register range validation
        #################################################

        for pen_sect in pen.sects:

            if (
                elector.register_number is not None
                and pen_sect.register_from is not None
                and pen_sect.register_to is not None
                and
                pen_sect.register_from
                <= elector.register_number
                <= pen_sect.register_to
            ):

                valid_ballot_pen = pen
                break


        if valid_ballot_pen:

            break


    if valid_ballot_pen is None:

        flash(
            "الناخب غير مسجل ضمن نطاق قلم الاقتراع الخاص بك",
            "danger"
        )

        return redirect(
            url_for("frontend_bp.enter_electors")
        )


    print(
        "5. Valid ballot pen:",
        valid_ballot_pen.id
    )


    #################################################
    # Tenant session
    #################################################

    print(session)
    print(
        "tenant_db:",
        session.get("tenant_db")
    )


    db_name = session.get(
        "tenant_db"
    )


    if not db_name:

        flash(
            "Tenant database not found",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )


    tenant_session = get_tenant_session(
        db_name
    )


    #################################################
    # Duplicate submission?
    #################################################

    existing_submission = (
        tenant_session.query(ElectorSubmission)
        .filter_by(
            elector_id=elector.id
        )
        .first()
    )


    if existing_submission:

        flash(
            "Elector has already voted",
            "warning"
        )

        tenant_session.close()

        return redirect(
            url_for("frontend_bp.enter_electors")
        )


    #################################################
    # Save submission in tenant DB
    #################################################

    try:

        submission = ElectorSubmission(

            elector_id=elector.id,

            elector_code=elector.elector_id,

            first_name=elector.first_name,

            surname=elector.surname,


            district_id=elector.district_id,

            district_name=(
                elector.district.name
                if elector.district
                else None
            ),


            subdistrict_id=elector.subdistrict_id,

            subdistrict_name=(
                elector.subdistrict.name
                if elector.subdistrict
                else None
            ),


            municipality=elector.municipality,


            # The validated ballot pen
            ballot_pen_id=valid_ballot_pen.id,


            # Use ballot pen number, not elector
            ballot_number=valid_ballot_pen.serial_number,


            polling_center_name=(
                valid_ballot_pen.polling_center.name
                if valid_ballot_pen.polling_center
                else None
            ),


            room_name=(
                valid_ballot_pen.room.name
                if valid_ballot_pen.room
                else None
            ),


            submitted_at=datetime.utcnow()

        )


        tenant_session.add(
            submission
        )

        tenant_session.commit()


        flash(
            "Elector submitted successfully",
            "success"
        )


    except Exception:

        tenant_session.rollback()

        traceback.print_exc()

        flash(
            "Error saving elector",
            "danger"
        )


    finally:

        tenant_session.close()


    return redirect(
        url_for(
            "frontend_bp.enter_electors"
        )
    )


# ----------------------------
# CANCEL ELECTOR ENTRY
# ----------------------------

@frontend_bp.route("/cancel-elector", methods=["POST"])
def cancel_elector():
    if not is_logged_in():
        return redirect(url_for("auth.login"))

    flash("Elector entry cancelled")
    return redirect(url_for("frontend_bp.enter_electors"))


# ----------------------------
# VIEW ELECTORS
# ----------------------------

@frontend_bp.route("/view-electors")
def view_electors():

    if not is_logged_in():
        return redirect(url_for("auth.login"))

    ballot_pen_ids = session.get(
        "ballot_pen_ids",
        []
    )

    if not ballot_pen_ids:
        flash(
            "No ballot pens assigned to this account",
            "danger"
        )
        return redirect(
            url_for("auth.login")
        )


    #################################################
    # Tenant session
    #################################################

    db_name = session.get("tenant_db")

    if not db_name:

        flash(
            "Tenant database not found",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )


    tenant_session = get_tenant_session(
        db_name
    )


    try:

        submissions = (
            tenant_session.query(ElectorSubmission)
            .filter(
                ElectorSubmission.ballot_pen_id.in_(
                    ballot_pen_ids
                )
            )
            .order_by(
                ElectorSubmission.submitted_at.desc()
            )
            .all()
        )


        #################################################
        # Master DB - ballot pen information
        #################################################

        ballot_pen = db.session.get(
            BallotPen,
            ballot_pen_ids[0]
        )


        district_name = (
            ballot_pen.district.name
            if ballot_pen and ballot_pen.district
            else ""
        )


        ballot_number = (
            str(ballot_pen.serial_number).zfill(4)
            if ballot_pen
            else ""
        )


        return render_template(
            "frontend/view_electors.html",
            electors=submissions,
            district_name=district_name,
            ballot_number=ballot_number
        )


    finally:

        tenant_session.close()


# ----------------------------
# CAST VOTE PAGE
# ----------------------------

@frontend_bp.route("/cast-vote")
def cast_vote():

    if not is_logged_in():
        return redirect(
            url_for("auth.login")
        )


    # ---------------------------------
    # Get logged-in ballot pen
    # ---------------------------------

    ballot_pen_ids = session.get(
        "ballot_pen_ids",
        []
    )

    if not ballot_pen_ids:

        flash(
            "No ballot pens assigned",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )


    ballot_pen_id = ballot_pen_ids[0]


    # ---------------------------------
    # Get ballot pen from master DB
    # ---------------------------------

    ballot_pen = db.session.get(
        BallotPen,
        ballot_pen_id
    )

    if not ballot_pen:

        flash(
            "Ballot pen not found",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )


    # ---------------------------------
    # Find tenant
    # ---------------------------------

    tenant = None

    for t in ballot_pen.district.tenants:

        tenant = t
        break


    if tenant is None:

        flash(
            "Tenant not found",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )


    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        # =================================
        # TOTAL ELECTORS
        # =================================

        elector_count = (
            tenant_session
            .query(ElectorSubmission)
            .filter_by(
                ballot_pen_id=ballot_pen_id
            )
            .count()
        )


        # =================================
        # VALID PAPERS
        # =================================

        valid_vote_count = (
            tenant_session
            .query(Vote)
            .filter(
                Vote.ballot_pen_id == ballot_pen_id,
                Vote.list_id.isnot(None)
            )
            .count()
        )


        # =================================
        # BLANK PAPERS
        # =================================

        blank_vote_count = (
            tenant_session
            .query(Vote)
            .filter(
                Vote.ballot_pen_id == ballot_pen_id,
                Vote.list_id.is_(None),
                Vote.candidate_id.is_(None)
            )
            .count()
        )


        # =================================
        # CANCELED PAPERS
        # =================================

        canceled_vote_count = (
            tenant_session
            .query(CanceledPaper)
            .filter_by(
                ballot_pen_id=ballot_pen_id
            )
            .count()
        )


        # =================================
        # TOTAL PROCESSED
        # =================================

        vote_count = (
            valid_vote_count
            + blank_vote_count
            + canceled_vote_count
        )


        # =================================
        # REMAINING
        # =================================

        remaining_count = (
            elector_count
            - vote_count
        )


        print(
            "=============================="
        )

        print(
            "Electors:",
            elector_count
        )

        print(
            "Valid:",
            valid_vote_count
        )

        print(
            "Blank:",
            blank_vote_count
        )

        print(
            "Canceled:",
            canceled_vote_count
        )

        print(
            "Processed:",
            vote_count
        )

        print(
            "Remaining:",
            remaining_count
        )

        print(
            "=============================="
        )


        # =================================
        # PREVENT EXTRA VOTES
        # =================================

        if vote_count >= elector_count:

            flash(
                "لا يمكن تسجيل اقتراع جديد. تم تسجيل الاقتراع لجميع الناخبين المدخلين.",
                "warning"
            )

            return redirect(
                url_for(
                    "frontend_bp.dashboard"
                )
            )


        # =================================
        # LOAD LISTS
        # =================================

        lists = (
            tenant_session
            .query(CandidateList)
            .filter_by(
                district_id=ballot_pen.district_id
            )
            .all()
        )


        return render_template(
            "frontend/vote.html",

            lists=lists,

            elector_count=elector_count,

            valid_vote_count=valid_vote_count,

            blank_vote_count=blank_vote_count,

            canceled_vote_count=canceled_vote_count,

            remaining_count=remaining_count
        )


    finally:

        tenant_session.close()


# ----------------------------
# GET CANDIDATES (AJAX)
# ----------------------------

@frontend_bp.route("/get-candidates/<int:list_id>")
def get_candidates(list_id):
    if not is_logged_in():
        return {"error": "Not authorized", "candidates": []}, 401

    ballot_pen_ids = session.get("ballot_pen_ids", [])

    if not ballot_pen_ids:
        return {"error": "No ballot pen assigned", "candidates": []}, 400

    # Get ballot pen
    ballot_pen = BallotPen.query.get(ballot_pen_ids[0])

    if not ballot_pen:
        return {"error": "Ballot pen not found", "candidates": []}, 400

    # Find tenant from district
    tenant = None
    for t in ballot_pen.district.tenants:
        tenant = t
        break

    if not tenant:
        return {"error": "Tenant not found", "candidates": []}, 400

    tenant_session = get_tenant_session(tenant.db_name)

    try:
        candidates = tenant_session.query(Candidate).filter_by(
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

    except Exception as e:
        print("GET CANDIDATES ERROR:", repr(e))
        return {"error": str(e), "candidates": []}, 500

    finally:
        tenant_session.close()


# ----------------------------
# SUBMIT VOTE
# ----------------------------

@frontend_bp.route(
    "/submit-vote",
    methods=["POST"]
)
def submit_vote():

    # =============================================
    # AUTHORIZATION
    # =============================================

    if not is_logged_in():

        return {
            "error": "Not authorized"
        }, 401


    # =============================================
    # GET SUBMITTED VALUES
    # =============================================

    vote_type = request.form.get(
        "vote_type"
    )

    list_id = (
        request.form.get(
            "list_id"
        )
        or None
    )

    candidate_id = (
        request.form.get(
            "candidate_id"
        )
        or None
    )


    # =============================================
    # VALIDATE VOTE TYPE
    # =============================================

    if vote_type not in [
        "normal",
        "blank",
        "canceled"
    ]:

        return {
            "error":
            "يرجى اختيار نوع الورقة"
        }, 400


    # =============================================
    # GET LOGGED-IN BALLOT PEN
    # =============================================

    ballot_pen_ids = session.get(
        "ballot_pen_ids",
        []
    )

    if not ballot_pen_ids:

        return {
            "error":
            "No ballot pen assigned"
        }, 400


    ballot_pen_id = ballot_pen_ids[0]


    # =============================================
    # GET BALLOT PEN FROM MASTER DATABASE
    # =============================================

    ballot_pen = db.session.get(
        BallotPen,
        ballot_pen_id
    )

    if not ballot_pen:

        return {
            "error":
            "Ballot pen not found"
        }, 400


    # =============================================
    # FIND TENANT
    # =============================================

    tenant = None

    for t in ballot_pen.district.tenants:

        tenant = t
        break


    if not tenant:

        return {
            "error":
            "Tenant not found"
        }, 400


    # =============================================
    # OPEN TENANT DATABASE
    # =============================================

    tenant_session = get_tenant_session(
        tenant.db_name
    )


    try:

        # =============================================
        # COUNT ELECTORS
        #
        # عدد المقترعين
        # =============================================

        elector_count = (

            tenant_session
            .query(ElectorSubmission)
            .filter_by(
                ballot_pen_id=ballot_pen_id
            )
            .count()

        )


        # =============================================
        # COUNT VALID PAPERS
        #
        # عدد الأوراق الصحيحة
        #
        # List only OR list + candidate
        # =============================================

        valid_vote_count = (

            tenant_session
            .query(Vote)
            .filter(
                Vote.ballot_pen_id == ballot_pen_id,
                Vote.list_id.isnot(None)
            )
            .count()

        )


        # =============================================
        # COUNT BLANK PAPERS
        #
        # أوراق بيضاء
        # =============================================

        blank_vote_count = (

            tenant_session
            .query(Vote)
            .filter(
                Vote.ballot_pen_id == ballot_pen_id,
                Vote.list_id.is_(None),
                Vote.candidate_id.is_(None)
            )
            .count()

        )


        # =============================================
        # COUNT CANCELED PAPERS
        #
        # أوراق ملغاة
        # =============================================

        canceled_vote_count = (

            tenant_session
            .query(CanceledPaper)
            .filter_by(
                ballot_pen_id=ballot_pen_id
            )
            .count()

        )


        # =============================================
        # TOTAL PROCESSED PAPERS
        # =============================================

        processed_count = (

            valid_vote_count
            + blank_vote_count
            + canceled_vote_count

        )


        # =============================================
        # PREVENT EXTRA PAPERS
        # =============================================

        if processed_count >= elector_count:

            return {
                "error":
                "لا يمكن تسجيل اقتراع جديد. تم الوصول إلى الحد الأقصى لعدد الناخبين."
            }, 400


        # ==================================================
        # NORMAL VOTE
        # ==================================================

        if vote_type == "normal":

            # ----------------------------------------------
            # LIST REQUIRED
            # ----------------------------------------------

            if not list_id:

                return {
                    "error":
                    "يرجى اختيار اللائحة"
                }, 400


            # ----------------------------------------------
            # VALIDATE LIST ID
            # ----------------------------------------------

            try:

                list_id_int = int(
                    list_id
                )

            except ValueError:

                return {
                    "error":
                    "رقم اللائحة غير صالح"
                }, 400


            # ----------------------------------------------
            # GET LIST
            # ----------------------------------------------

            candidate_list = (

                tenant_session
                .query(CandidateList)
                .filter_by(
                    id=list_id_int
                )
                .first()

            )


            if not candidate_list:

                return {
                    "error":
                    "اللائحة غير موجودة"
                }, 400


            # ----------------------------------------------
            # MAKE SURE LIST BELONGS TO DISTRICT
            # ----------------------------------------------

            if (
                candidate_list.district_id
                != ballot_pen.district_id
            ):

                return {
                    "error":
                    "هذه اللائحة لا تنتمي إلى الدائرة الحالية"
                }, 400


            # ----------------------------------------------
            # CANDIDATE IS OPTIONAL
            # ----------------------------------------------

            candidate_id_int = None


            if candidate_id:

                try:

                    candidate_id_int = int(
                        candidate_id
                    )

                except ValueError:

                    return {
                        "error":
                        "رقم المرشح غير صالح"
                    }, 400


                candidate = (

                    tenant_session
                    .query(Candidate)
                    .filter_by(
                        id=candidate_id_int
                    )
                    .first()

                )


                if not candidate:

                    return {
                        "error":
                        "المرشح غير موجود"
                    }, 400


                # ------------------------------------------
                # CANDIDATE MUST BELONG TO SELECTED LIST
                # ------------------------------------------

                if (
                    candidate.candidate_list_id
                    != list_id_int
                ):

                    return {
                        "error":
                        "المرشح لا ينتمي إلى اللائحة المختارة"
                    }, 400


            # ----------------------------------------------
            # CREATE VALID VOTE
            # ----------------------------------------------

            vote = Vote(

                ballot_pen_id=ballot_pen_id,

                district_id=(
                    ballot_pen.district_id
                ),

                subdistrict_id=(
                    ballot_pen.subdistrict_id
                ),

                list_id=list_id_int,

                candidate_id=candidate_id_int

            )


            tenant_session.add(
                vote
            )

            tenant_session.commit()


            # ----------------------------------------------
            # RESPONSE
            # ----------------------------------------------

            if candidate_id_int is not None:

                return {
                    "success": True,
                    "type": "candidate"
                }


            return {
                "success": True,
                "type": "list"
            }


        # ==================================================
        # BLANK PAPER
        # ==================================================

        elif vote_type == "blank":

            # ----------------------------------------------
            # BLANK PAPER CANNOT HAVE A LIST OR CANDIDATE
            # ----------------------------------------------

            if list_id or candidate_id:

                return {
                    "error":
                    "الورقة البيضاء لا يمكن أن تحتوي على لائحة أو مرشح"
                }, 400


            # ----------------------------------------------
            # CREATE BLANK VOTE
            # ----------------------------------------------

            vote = Vote(

                ballot_pen_id=ballot_pen_id,

                district_id=(
                    ballot_pen.district_id
                ),

                subdistrict_id=(
                    ballot_pen.subdistrict_id
                ),

                list_id=None,

                candidate_id=None

            )


            tenant_session.add(
                vote
            )

            tenant_session.commit()


            return {
                "success": True,
                "type": "blank"
            }


        # ==================================================
        # CANCELED PAPER
        # ==================================================

        elif vote_type == "canceled":

            # ----------------------------------------------
            # CANCELED PAPER CANNOT HAVE A LIST OR CANDIDATE
            # ----------------------------------------------

            if list_id or candidate_id:

                return {
                    "error":
                    "الورقة الملغاة لا يمكن أن تحتوي على لائحة أو مرشح"
                }, 400


            # ----------------------------------------------
            # CREATE CANCELED PAPER
            # ----------------------------------------------

            canceled_paper = CanceledPaper(

                ballot_pen_id=ballot_pen_id,

                district_id=(
                    ballot_pen.district_id
                )

            )


            tenant_session.add(
                canceled_paper
            )

            tenant_session.commit()


            return {
                "success": True,
                "type": "canceled"
            }


    except Exception as e:

        tenant_session.rollback()

        print(
            "SUBMIT VOTE ERROR:",
            repr(e)
        )

        return {
            "error": str(e)
        }, 500


    finally:

        tenant_session.close()

# ----------------------------
# RESULTS VIEW
# ----------------------------

@frontend_bp.route("/sorted-votes")
def sorted_votes():
    if not is_logged_in():
        return redirect(url_for("auth.login"))

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
@frontend_bp.route("/ballot-pen-electors")
def ballot_pen_electors():

    if not is_logged_in():
        return redirect(url_for("auth.login"))

    ballot_pen_ids = session.get("ballot_pen_ids", [])

    if not ballot_pen_ids:
        flash("No ballot pen assigned", "danger")
        return redirect(url_for("auth.login"))

    electors = (
        Elector.query
        .filter(
            Elector.ballot_pen_id.in_(ballot_pen_ids)
        )
        .order_by(Elector.elector_id)
        .all()
    )

    return render_template(
        "frontend/ballot_pen_electors.html",
        electors=electors
    )