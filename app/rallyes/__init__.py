from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase

from .config import Config


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
csrf = CSRFProtect()


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)
    db.init_app(app)
    csrf.init_app(app)

    from . import droits  # noqa: F401  (active les rôles PostgreSQL par transaction)
    from .auth import creer_comptes_demo, login_manager
    login_manager.init_app(app)

    from . import outils
    outils.enregistrer(app)

    @app.errorhandler(403)
    def interdit(_):
        return render_template("erreur.html", code=403,
                               message="Votre profil ne permet pas d'accéder à cette page."), 403

    @app.errorhandler(404)
    def introuvable(_):
        return render_template("erreur.html", code=404,
                               message="Cette page n'existe pas."), 404

    from .accueil import bp as accueil
    from .auth import bp as auth
    from .annuaire import bp as annuaire
    from .consultation import bp as consultation
    from .organisation import bp as organisation
    from .requetes import bp as requetes
    app.register_blueprint(accueil)
    app.register_blueprint(auth)
    app.register_blueprint(consultation)
    app.register_blueprint(annuaire)
    app.register_blueprint(requetes)
    app.register_blueprint(organisation)

    if app.config["COMPTES_DEMO"]:
        creer_comptes_demo(app)

    return app
