from flask import Blueprint, render_template
from sqlalchemy import func, select

from . import db
from .modeles import Concurrent, Equipe, Etape, Rallye, Resultat, Vehicule, VRallyeStats

bp = Blueprint("accueil", __name__)


def compter(modele):
    return db.session.scalar(select(func.count()).select_from(modele))


@bp.route("/")
def index():
    chiffres = {
        "editions": compter(Rallye),
        "etapes": compter(Etape),
        "concurrents": compter(Concurrent),
        "equipes": compter(Equipe),
        "vehicules": compter(Vehicule),
        "resultats": compter(Resultat),
    }
    dernieres = db.session.scalars(
        select(VRallyeStats)
        .order_by(VRallyeStats.annee.desc(), VRallyeStats.nomRallye)
        .limit(10)
    ).all()
    return render_template("accueil.html", chiffres=chiffres, dernieres=dernieres)
