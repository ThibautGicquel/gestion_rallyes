from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, login_user, logout_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired

from . import db
from .droits import Compte, Visiteur
from .modeles import Utilisateur

bp = Blueprint("auth", __name__)

login_manager = LoginManager()
login_manager.login_view = "auth.connexion"
login_manager.login_message = "Connectez-vous pour accéder à cette page."
login_manager.login_message_category = "info"
login_manager.anonymous_user = Visiteur

COMPTES_DEMO = [("admin", "admin", "administrateur"),
                ("organisateur", "organisateur", "organisateur")]


# Les comptes sont lus avec le compte de connexion de l'application, hors des
# transactions de l'ORM : les rôles des profils n'ont aucun droit sur utilisateur.
def lire_compte(login):
    with db.engine.connect() as connexion:
        return connexion.execute(
            select(Utilisateur.login, Utilisateur.motDePasse.label("motDePasse"),
                   Utilisateur.profil)
            .where(Utilisateur.login == login)
        ).first()


@login_manager.user_loader
def charger_compte(login):
    ligne = lire_compte(login)
    return Compte(ligne.login, ligne.profil) if ligne else None


def creer_comptes_demo(app):
    try:
        with app.app_context(), db.engine.begin() as connexion:
            for login, mot_de_passe, profil in COMPTES_DEMO:
                connexion.execute(
                    insert(Utilisateur)
                    .values(login=login, motDePasse=generate_password_hash(mot_de_passe),
                            profil=profil)
                    .on_conflict_do_nothing()
                )
    except SQLAlchemyError as exc:
        app.logger.warning("Comptes de démonstration non créés : %s", exc)


class FormulaireConnexion(FlaskForm):
    login = StringField("Identifiant", validators=[DataRequired()])
    motDePasse = PasswordField("Mot de passe", validators=[DataRequired()])


def adresse_locale(adresse):
    parties = urlsplit(adresse or "")
    return adresse if adresse and not parties.scheme and not parties.netloc \
        and adresse.startswith("/") else None


@bp.route("/connexion", methods=["GET", "POST"])
def connexion():
    form = FormulaireConnexion()
    if form.validate_on_submit():
        ligne = lire_compte(form.login.data)
        if ligne and check_password_hash(ligne.motDePasse, form.motDePasse.data):
            login_user(Compte(ligne.login, ligne.profil))
            flash(f"Connecté en tant que {ligne.login} ({ligne.profil}).", "succes")
            return redirect(adresse_locale(request.args.get("next"))
                            or url_for("accueil.index"))
        flash("Identifiant ou mot de passe incorrect.", "erreur")
    return render_template("connexion.html", form=form)


@bp.route("/deconnexion", methods=["POST"])
def deconnexion():
    logout_user()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("accueil.index"))
