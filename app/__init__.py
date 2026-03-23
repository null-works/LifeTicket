from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from datetime import date
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app():
    app = Flask(__name__)

    db_path = os.environ.get("DATABASE_URL", "sqlite:///lifeticket.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_path
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes import main, api
    from app.auth import auth
    from app.dav_proxy import dav

    app.register_blueprint(main)
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(auth)
    app.register_blueprint(dav, url_prefix="/dav")

    @app.context_processor
    def inject_globals():
        from app.version import VERSION
        from app.models import AppSettings
        settings = AppSettings.get()
        return {
            "today": date.today(),
            "version": VERSION,
            "ticket_prefix": settings.ticket_prefix,
            "event_prefix": settings.event_prefix,
        }

    with app.app_context():
        db.create_all()
        _add_missing_columns()
        _seed_statuses()
        _migrate_statuses()
        _ensure_admin(app)
        from app.caldav_sync import init_calendar
        init_calendar()

    return app


def _add_missing_columns():
    """Add new columns that db.create_all() won't add to existing tables."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    columns = [c["name"] for c in inspector.get_columns("ticket")]
    if "emoji" not in columns:
        db.session.execute(text("ALTER TABLE ticket ADD COLUMN emoji VARCHAR(10) DEFAULT ''"))
        db.session.commit()
        print("[LifeTicket] Added 'emoji' column to ticket table")

    if "resolution_notes" not in columns:
        db.session.execute(text("ALTER TABLE ticket ADD COLUMN resolution_notes TEXT DEFAULT ''"))
        db.session.commit()
        print("[LifeTicket] Added 'resolution_notes' column to ticket table")
    if "resolved_at" not in columns:
        db.session.execute(text("ALTER TABLE ticket ADD COLUMN resolved_at DATETIME"))
        db.session.commit()
        print("[LifeTicket] Added 'resolved_at' column to ticket table")

    if "job_application" in inspector.get_table_names():
        job_cols = [c["name"] for c in inspector.get_columns("job_application")]
        if "resume_filename" not in job_cols:
            db.session.execute(text("ALTER TABLE job_application ADD COLUMN resume_filename VARCHAR(255) DEFAULT ''"))
            db.session.execute(text("ALTER TABLE job_application ADD COLUMN resume_original_name VARCHAR(255) DEFAULT ''"))
            db.session.commit()
            print("[LifeTicket] Added resume columns to job_application table")

    if "app_settings" in inspector.get_table_names():
        settings_cols = [c["name"] for c in inspector.get_columns("app_settings")]
        if "caldav_enabled" not in settings_cols:
            db.session.execute(text("ALTER TABLE app_settings ADD COLUMN caldav_enabled BOOLEAN DEFAULT 0"))
            db.session.execute(text("ALTER TABLE app_settings ADD COLUMN caldav_url VARCHAR(500) DEFAULT 'http://radicale:5232'"))
            db.session.execute(text("ALTER TABLE app_settings ADD COLUMN caldav_username VARCHAR(200) DEFAULT 'lifeticket'"))
            db.session.execute(text("ALTER TABLE app_settings ADD COLUMN caldav_password VARCHAR(500) DEFAULT 'lifeticket'"))
            db.session.commit()
            print("[LifeTicket] Added CalDAV columns to app_settings table")


def _seed_statuses():
    """Ensure default statuses exist in the Status table."""
    from app.models import Status

    defaults = [
        ("new", "New", "#a855f7", False, 0),
        ("action_required", "Action Required", "#3b82f6", False, 1),
        ("awaiting_reply", "Awaiting Reply", "#eab308", False, 2),
        ("on_hold", "On Hold", "#6b7280", False, 3),
        ("done", "Done", "#22c55e", True, 4),
        ("cancelled", "Cancelled", "#ef4444", True, 5),
    ]
    for name, label, color, is_closed, position in defaults:
        if not Status.query.filter_by(name=name).first():
            db.session.add(Status(name=name, label=label, color=color, is_closed=is_closed, position=position))
    db.session.commit()


def _migrate_statuses():
    """Remap old ticket statuses to the new set."""
    from app.models import Ticket

    mapping = {"todo": "action_required", "in_progress": "action_required"}
    changed = 0
    for old, new in mapping.items():
        rows = Ticket.query.filter_by(status=old).all()
        for t in rows:
            t.status = new
            changed += 1
    if changed:
        db.session.commit()
        print(f"[LifeTicket] Migrated {changed} ticket(s) to new statuses")


def _ensure_admin(app):
    """Create or update the admin user from environment variables."""
    from app.models import User

    username = os.environ.get("ADMIN_USERNAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        print("[LifeTicket] WARNING: ADMIN_PASSWORD not set — no admin user created")
        return

    try:
        user = User.query.filter_by(username=username).first()
        if user:
            user.set_password(password)
            db.session.commit()
            print(f"[LifeTicket] Admin user '{username}' password updated")
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            print(f"[LifeTicket] Admin user '{username}' created")
    except Exception as e:
        db.session.rollback()
        print(f"[LifeTicket] ERROR creating admin user: {e}")
