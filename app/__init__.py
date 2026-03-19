from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import date
import os

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    db_path = os.environ.get("DATABASE_URL", "sqlite:///lifeticket.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_path
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")

    db.init_app(app)
    migrate.init_app(app, db)

    from app import models  # noqa: F401
    from app.routes import main, api

    app.register_blueprint(main)
    app.register_blueprint(api, url_prefix="/api")

    @app.context_processor
    def inject_today():
        return {"today": date.today()}

    with app.app_context():
        db.create_all()

    return app
