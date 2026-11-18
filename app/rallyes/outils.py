"""Tri, pagination et formats d'affichage communs aux pages."""
from flask import request, url_for
from flask_sqlalchemy.pagination import SelectPagination
from flask_wtf import FlaskForm

CATEGORIES = ["Auto", "Moto", "Camion"]


class Formulaire(FlaskForm):
    """Formulaire avec protection CSRF et messages de validation en français."""

    class Meta:
        locales = ["fr_FR", "fr"]


class PaginationLignes(SelectPagination):
    """Comme db.paginate, mais renvoie des lignes complètes (plusieurs colonnes)
    au lieu de la seule première colonne."""

    def _query_items(self):
        requete = self._query_args["select"].limit(self.per_page).offset(self._query_offset)
        return list(self._query_args["session"].execute(requete))


def paginer_lignes(requete, par_page):
    from . import db
    return PaginationLignes(select=requete, session=db.session, per_page=par_page,
                            error_out=False)


class Tri:
    """Tri demandé dans l'URL (?tri=cle&ordre=asc|desc), limité aux colonnes prévues."""

    def __init__(self, colonnes, defaut, ordre="asc"):
        cle = request.args.get("tri")
        self.cle = cle if cle in colonnes else defaut
        ordre_demande = request.args.get("ordre")
        self.ordre = ordre_demande if ordre_demande in ("asc", "desc") else ordre
        colonne = colonnes[self.cle]
        self.expression = (colonne.desc() if self.ordre == "desc" else colonne.asc()).nulls_last()


MESSAGES_SQLSTATE = {
    "23505": "Cet enregistrement existe déjà.",
    "23503": "Opération impossible : des données liées existent (ou manquent).",
    "23514": "Une contrainte de la base n'est pas respectée.",
    "23502": "Une valeur obligatoire est manquante.",
    "42501": "Votre profil n'a pas le droit d'effectuer cette opération.",
}


def message_erreur(exc):
    """Message lisible pour une erreur renvoyée par PostgreSQL. Les erreurs levées
    par les triggers (RAISE EXCEPTION, code P0001) sont affichées telles quelles."""
    origine = getattr(exc, "orig", None)
    code = getattr(origine, "sqlstate", None)
    detail = getattr(getattr(origine, "diag", None), "message_primary", None) or str(exc)
    if code == "P0001":
        return detail
    return f"{MESSAGES_SQLSTATE.get(code, 'Erreur de la base de données.')} ({detail})"


def categorie_demandee():
    categorie = request.args.get("categorie")
    return categorie if categorie in CATEGORIES else None


def url_avec(**changements):
    """URL de la page courante en modifiant certains paramètres (None = retirer)."""
    parametres = request.args.to_dict()
    parametres.update(request.view_args or {})
    for cle, valeur in changements.items():
        if valeur is None:
            parametres.pop(cle, None)
        else:
            parametres[cle] = valeur
    return url_for(request.endpoint, **parametres)


def nombre(valeur):
    # 12345 -> "12 345"
    return f"{valeur:,}".replace(",", " ") if valeur is not None else ""


def duree(heures, signe=False):
    """Durée en heures décimales -> "h:mm:ss"."""
    if heures is None:
        return ""
    secondes = round(float(heures) * 3600)
    h, reste = divmod(abs(secondes), 3600)
    texte = f"{h}:{reste // 60:02d}:{reste % 60:02d}"
    return ("+" if secondes >= 0 else "-") + texte if signe else texte


def date_heure(valeur):
    return valeur.strftime("%d/%m/%Y %H:%M") if valeur else ""


def kilometres(valeur):
    return f"{nombre(round(valeur))} km" if valeur is not None else ""


def euros(valeur):
    return f"{nombre(round(valeur))} €" if valeur is not None else ""


def ordinal(rang):
    return "" if rang is None else ("1er" if rang == 1 else f"{rang}e")


def enregistrer(app):
    app.jinja_env.globals.update(url_avec=url_avec, CATEGORIES=CATEGORIES)
    app.jinja_env.filters.update(nombre=nombre, duree=duree, date_heure=date_heure,
                                 km=kilometres, ordinal=ordinal,
                                 euros=euros)
