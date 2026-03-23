from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, AppSettings

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth.route("/settings")
@login_required
def settings():
    users = User.query.order_by(User.username).all()
    app_settings = AppSettings.get()
    return render_template("settings.html", users=users, app_settings=app_settings)


@auth.route("/settings/prefixes", methods=["POST"])
@login_required
def update_prefixes():
    app_settings = AppSettings.get()
    app_settings.ticket_prefix = request.form.get("ticket_prefix", "#").strip() or "#"
    app_settings.event_prefix = request.form.get("event_prefix", "EVT-").strip() or "EVT-"
    db.session.commit()
    flash("Prefixes updated successfully.", "success")
    return redirect(url_for("auth.settings"))


@auth.route("/settings/change-password", methods=["POST"])
@login_required
def change_password():
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")

    if not current_user.check_password(current_pw):
        flash("Current password is incorrect.", "error")
    elif len(new_pw) < 4:
        flash("New password must be at least 4 characters.", "error")
    elif new_pw != confirm_pw:
        flash("New passwords do not match.", "error")
    else:
        current_user.set_password(new_pw)
        db.session.commit()
        flash("Password changed successfully.", "success")

    return redirect(url_for("auth.settings"))


@auth.route("/settings/add-user", methods=["POST"])
@login_required
def add_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm_pw = request.form.get("confirm_password", "")

    if not username:
        flash("Username is required.", "error")
    elif User.query.filter_by(username=username).first():
        flash(f"Username '{username}' already exists.", "error")
    elif len(password) < 4:
        flash("Password must be at least 4 characters.", "error")
    elif password != confirm_pw:
        flash("Passwords do not match.", "error")
    else:
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f"User '{username}' created successfully.", "success")

    return redirect(url_for("auth.settings"))


@auth.route("/settings/caldav", methods=["POST"])
@login_required
def update_caldav():
    app_settings = AppSettings.get()
    app_settings.caldav_enabled = request.form.get("caldav_enabled") == "on"
    app_settings.caldav_url = request.form.get("caldav_url", "").strip()
    app_settings.caldav_username = request.form.get("caldav_username", "").strip()
    pw = request.form.get("caldav_password", "").strip()
    if pw:
        app_settings.caldav_password = pw
    db.session.commit()
    # Reset cached CalDAV client so new settings take effect
    from app.caldav_sync import _reset_client
    _reset_client()
    flash("CalDAV settings updated successfully.", "success")
    return redirect(url_for("auth.settings"))


@auth.route("/settings/delete-user/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("auth.settings"))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f"User '{user.username}' deleted.", "success")
    return redirect(url_for("auth.settings"))
