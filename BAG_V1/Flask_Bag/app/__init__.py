from flask import Flask
from .db import init_app as init_db_app
from .auth import bp as auth_bp
from .core import bp as core_bp

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev-change-me",
        DATABASE="bag.sqlite3",
    )

    init_db_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(core_bp)

    return app
