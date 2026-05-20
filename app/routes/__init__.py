from flask import Blueprint

bp = Blueprint("main", __name__)

from app.routes import main  # noqa: E402, F401
from app.routes.data_gouv import bp_data  # noqa: E402, F401
