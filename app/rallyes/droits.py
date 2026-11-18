"""Profils de l'application et rôles PostgreSQL correspondants (sql/07_roles.sql)."""
from functools import wraps

from flask import abort, has_request_context
from flask_login import AnonymousUserMixin, UserMixin, current_user
from sqlalchemy import event
from sqlalchemy.orm import Session

NIVEAUX = {"visiteur": 0, "organisateur": 1, "administrateur": 2}

ROLES_PG = {
    "visiteur": "rallye_lecture",
    "organisateur": "rallye_saisie",
    "administrateur": "rallye_admin",
}


class Compte(UserMixin):
    def __init__(self, login, profil):
        self.login = login
        self.profil = profil

    def get_id(self):
        return self.login

    def a_le_droit(self, profil):
        return NIVEAUX[self.profil] >= NIVEAUX[profil]


class Visiteur(AnonymousUserMixin):
    login = None
    profil = "visiteur"

    def a_le_droit(self, profil):
        return profil == "visiteur"


def role_requis(profil):
    """Réserve une vue à un profil (ou à un profil supérieur)."""
    def decorateur(vue):
        @wraps(vue)
        def verifiee(*args, **kwargs):
            from .auth import login_manager
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if not current_user.a_le_droit(profil):
                abort(403)
            return vue(*args, **kwargs)
        return verifiee
    return decorateur


@event.listens_for(Session, "after_begin")
def activer_role(session, transaction, connexion):
    # Chaque transaction d'une requête web prend le rôle du profil connecté :
    # PostgreSQL refuse alors lui-même ce que le profil n'a pas le droit de faire.
    if has_request_context():
        connexion.exec_driver_sql(f"SET LOCAL ROLE {ROLES_PG[current_user.profil]}")
