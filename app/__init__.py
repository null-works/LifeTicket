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
        _ensure_admin(app)

    return app


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
