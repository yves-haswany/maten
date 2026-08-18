from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from werkzeug.security import check_password_hash

from ..models.master_models import User, BallotPen,Tenant


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth"
)


# ----------------------------------
# LOGIN
# ----------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        ####################################################
        # Authenticate
        ####################################################

        user = User.query.filter_by(
            username=username
        ).first()

        if (
            not user
            or not check_password_hash(
                user.password,
                password
            )
        ):

            flash(
                "Invalid username or password",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        ####################################################
        # Clear old session
        ####################################################

        session.clear()

        session["user_id"] = user.id
        session["role"] = user.role

        ####################################################
        # Ballot pen users
        ####################################################

        if user.role == "ballot_pen":

            ballot_pen_ids = [
                pen.id
                for pen in user.ballot_pens
            ]

            session["ballot_pen_ids"] = ballot_pen_ids

            if not ballot_pen_ids:

                flash(
                    "No ballot pens assigned to this account",
                    "danger"
                )

                return redirect(
                    url_for("auth.login")
                )

            ################################################
            # Get first ballot pen
            ################################################

            ballot_pen = user.ballot_pens[0]

            ################################################
            # Find tenant that participates
            # in this district
            ################################################

            tenant = (
                Tenant.query
                .filter(
                    Tenant.districts.any(
                        id=ballot_pen.district_id
                    )
                )
                .first()
            )

            if tenant is None:

                flash(
                    "No tenant found for this ballot pen",
                    "danger"
                )

                return redirect(
                    url_for("auth.login")
                )

            ################################################
            # Save tenant information
            ################################################

            session["tenant_id"] = tenant.id
            session["tenant_db"] = tenant.db_name

            return redirect(
                url_for(
                    "frontend_bp.dashboard"
                )
            )

        ####################################################
        # Tenant users
        ####################################################

        if user.role == "tenant":

            session["tenant_id"] = user.tenant_id

            tenant = Tenant.query.get(
                user.tenant_id
            )

            if tenant:

                session["tenant_db"] = tenant.db_name

            return redirect(
                url_for(
                    "tenant.dashboard"
                )
            )

        ####################################################
        # District users
        ####################################################

        if user.role == "district":

            session["district_id"] = user.district_id

            return redirect(
                url_for(
                    "district.dashboard"
                )
            )

        ####################################################
        # Admin users
        ####################################################

        if user.role == "admin":

            return redirect(
                url_for(
                    "admin.dashboard"
                )
            )

        ####################################################
        # Unknown role
        ####################################################

        flash(
            "Unknown account type",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template(
        "auth/login.html"
    )


# ----------------------------------
# LOGOUT
# ----------------------------------

@auth_bp.route("/logout")
def logout():

    session.clear()

    return redirect(

        url_for(
            "auth.login"
        )

    )