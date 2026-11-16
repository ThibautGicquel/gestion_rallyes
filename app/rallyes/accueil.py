from flask import Blueprint, render_template
from sqlalchemy import text

from . import db

bp = Blueprint("accueil", __name__)


@bp.route("/")
def index():
    chiffres = db.session.execute(text("""
        SELECT (SELECT count(*) FROM rallye)     AS editions,
               (SELECT count(*) FROM etape)      AS etapes,
               (SELECT count(*) FROM concurrent) AS concurrents,
               (SELECT count(*) FROM equipe)     AS equipes,
               (SELECT count(*) FROM vehicule)   AS vehicules,
               (SELECT count(*) FROM resultat)   AS resultats
    """)).mappings().one()
    dernieres = db.session.execute(text("""
        SELECT nomRallye, annee, nbEtapes, nbEquipages, nbConcurrents
        FROM v_rallye_stats
        ORDER BY annee DESC, nomRallye
        LIMIT 10
    """)).mappings().all()
    return render_template("accueil.html", chiffres=chiffres, dernieres=dernieres)
