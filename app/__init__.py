from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os

db = SQLAlchemy()
migrate = Migrate()


# Initialisation de l'app Flask avec ses variables d'environnement associés
def create_app(config=None):
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)

    from . import models as _models  # noqa: F401 — enregistre les modèles dans la metadata SQLAlchemy

    from app.routes import bp as routes_bp
    from app.routes.data_gouv import bp_data
    from app.routes.ingestion import bp_ingest
    from app.routes.nlp import bp_nlp

    app.register_blueprint(routes_bp)
    app.register_blueprint(bp_data)
    app.register_blueprint(bp_ingest)
    app.register_blueprint(bp_nlp)

    return app