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

from ..models import User


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

        user = User.query.filter_by(username=username).first()

        # unified failure (no user enumeration leak)
        if not user or not check_password_hash(user.password, password):
            flash("Invalid username or password", "danger")
            return redirect(url_for("auth.login"))

        session.clear()

        session["user_id"] = user.id
        session["role"] = user.role

        role_redirects = {
            "admin": ("admin.dashboard", {}),
            "tenant": ("tenant.dashboard", {"tenant_id": user.tenant_id}),
            "district": ("district.dashboard", {"district_id": user.district_id}),
            "ballot": ("ballot.dashboard", {"ballot_pen_id": user.ballot_pen_id}),
        }

        if user.role in role_redirects:
            endpoint, extra_session = role_redirects[user.role]

            session.update(extra_session)

            return redirect(url_for(endpoint))

        flash("Unknown account type", "danger")
        return redirect(url_for("auth.login"))

    return render_template("auth/login.html")


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