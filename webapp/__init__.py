from __future__ import annotations

from flask import Flask

from app.db import init_db
from webapp.routes import api_bp, web_bp


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("Database initialisation skipped: %s", exc)

    return app
