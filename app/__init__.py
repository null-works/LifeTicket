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

    app.register_blueprint(main)
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(auth)

    @app.context_processor
    def inject_globals():
        from app.version import VERSION
        return {"today": date.today(), "version": VERSION}

    with app.app_context():
        db.create_all()
        _add_missing_columns()
        _migrate_statuses()
        _ensure_admin(app)

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
