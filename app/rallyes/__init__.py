from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

from .config import Config


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)
    db.init_app(app)

    @app.template_filter("nombre")
    def nombre(valeur):
        # 12345 -> "12 345"
        return f"{valeur:,}".replace(",", " ") if valeur is not None else ""

    from .accueil import bp as accueil
    app.register_blueprint(accueil)

    return app
