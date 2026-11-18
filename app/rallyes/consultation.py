"""Pages de consultation, accessibles à tous les profils."""
from collections import defaultdict

from flask import Blueprint, abort, render_template, request
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from . import db
from .modeles import (Equipage, Etape, Pilote, Rallye, Resultat, VClassementEtape, VEtapePays,
                      VParticipation, VRallyeStats, Vehicule)
from .outils import Tri, categorie_demandee, ordinal

bp = Blueprint("consultation", __name__)

ONGLETS = {"etapes": "Étapes", "equipages": "Équipages", "classement": "Classement général",
           "partenaires": "Sponsors et fournisseurs"}


def du_rallye(modele, nom, annee):
    return and_(modele.nomRallye == nom, modele.annee == annee)


def jointure_vehicule(modele):
    """Jointures modele -> pilote -> vehicule pour connaître la catégorie d'un équipage."""
    return (
        (Pilote, and_(Pilote.nomRallye == modele.nomRallye, Pilote.annee == modele.annee,
                      Pilote.numEquipage == modele.numEquipage)),
        (Vehicule, Vehicule.numeroSerie == Pilote.numeroSerie),
    )


def equipiers(nom, annee):
    """numEquipage -> "Prénom Nom / Prénom Nom" pour toute une édition."""
    noms = defaultdict(list)
    lignes = db.session.execute(
        select(VParticipation.numEquipage, VParticipation.prenom, VParticipation.nom)
        .where(du_rallye(VParticipation, nom, annee))
        .order_by(VParticipation.nom)
    )
    for ligne in lignes:
        noms[ligne.numEquipage].append(f"{ligne.prenom} {ligne.nom}")
    return {num: " / ".join(liste) for num, liste in noms.items()}


# ---------------------------------------------------------------------
# Rallyes
# ---------------------------------------------------------------------

@bp.route("/rallyes")
def rallyes():
    v = VRallyeStats
    nom = request.args.get("nom") or None
    annee = request.args.get("annee", type=int)
    tri = Tri({"nom": v.nomRallye, "annee": v.annee, "etapes": v.nbEtapes,
               "equipages": v.nbEquipages, "concurrents": v.nbConcurrents},
              defaut="annee", ordre="desc")

    requete = select(v)
    if nom:
        requete = requete.where(v.nomRallye == nom)
    if annee:
        requete = requete.where(v.annee == annee)
    page = db.paginate(requete.order_by(tri.expression, v.nomRallye, v.annee.desc()),
                       per_page=20, error_out=False)

    noms = db.session.scalars(select(Rallye.nomRallye).distinct().order_by(Rallye.nomRallye))
    return render_template("rallyes.html", page=page, tri=tri, noms=noms.all(),
                           nom=nom, annee=annee)


def classement_general(nom, annee, categorie=None):
    """Équipages ayant terminé toutes les étapes sans disqualification, classés
    par catégorie selon le temps cumulé."""
    nb_etapes = db.session.scalar(
        select(func.count()).select_from(Etape).where(du_rallye(Etape, nom, annee)))
    cumul = (
        select(Resultat.numEquipage,
               func.sum(Resultat.dureeHeure).label("total"),
               func.count().label("nbEtapes"),
               func.bool_or(Resultat.disqualifiee).label("disqualifie"))
        .where(du_rallye(Resultat, nom, annee))
        .group_by(Resultat.numEquipage)
        .subquery()
    )
    par_categorie = {"partition_by": Vehicule.type}
    requete = (
        select(Equipage.numEquipage, Equipage.nomEquipe, Pilote.numeroOrga,
               Vehicule.type.label("categorie"), Vehicule.nomMarque, cumul.c.total,
               func.rank().over(order_by=cumul.c.total, **par_categorie).label("rang"),
               (cumul.c.total - func.min(cumul.c.total).over(**par_categorie)).label("ecart"))
        .join(cumul, cumul.c.numEquipage == Equipage.numEquipage)
        .join(*jointure_vehicule(Equipage)[0])
        .join(*jointure_vehicule(Equipage)[1])
        .where(du_rallye(Equipage, nom, annee),
               cumul.c.nbEtapes == nb_etapes, ~cumul.c.disqualifie)
        .order_by(Vehicule.type, "rang", Pilote.numeroOrga)
    )
    if categorie:
        requete = requete.where(Vehicule.type == categorie)
    return db.session.execute(requete).all()


def partants_par_categorie(nom, annee):
    lignes = db.session.execute(
        select(Vehicule.type, func.count())
        .select_from(Equipage)
        .join(*jointure_vehicule(Equipage)[0])
        .join(*jointure_vehicule(Equipage)[1])
        .where(du_rallye(Equipage, nom, annee))
        .group_by(Vehicule.type)
    )
    return dict(lignes.all())


@bp.route("/rallyes/<nom>/<int:annee>")
def rallye(nom, annee):
    rallye = db.get_or_404(Rallye, (nom, annee))
    onglet = request.args.get("onglet", "etapes")
    if onglet not in ONGLETS:
        abort(404)
    stats = db.session.get(VRallyeStats, (nom, annee))
    categorie = categorie_demandee()
    contexte = {}

    if onglet == "etapes":
        contexte["etapes"] = db.session.scalars(
            select(VEtapePays).where(du_rallye(VEtapePays, nom, annee))
            .order_by(VEtapePays.numEtape)).all()

    elif onglet == "equipages":
        tri = Tri({"numero": Pilote.numeroOrga, "equipe": Equipage.nomEquipe,
                   "marque": Vehicule.nomMarque, "categorie": Vehicule.type}, defaut="numero")
        requete = (
            select(Equipage)
            .join(Equipage.pilote).join(Pilote.vehicule)
            .where(du_rallye(Equipage, nom, annee))
            .options(contains_eager(Equipage.pilote).contains_eager(Pilote.vehicule),
                     selectinload(Equipage.concurrents), joinedload(Equipage.equipe))
            .order_by(tri.expression, Pilote.numeroOrga)
        )
        if categorie:
            requete = requete.where(Vehicule.type == categorie)
        contexte["page"] = db.paginate(requete, per_page=50, error_out=False)
        contexte["tri"] = tri

    elif onglet == "classement":
        contexte["classement"] = classement_general(nom, annee, categorie)
        contexte["noms"] = equipiers(nom, annee)
        contexte["partants"] = partants_par_categorie(nom, annee)

    return render_template("rallye.html", rallye=rallye, stats=stats, onglet=onglet,
                           onglets=ONGLETS, categorie=categorie, **contexte)


# ---------------------------------------------------------------------
# Étapes et équipages
# ---------------------------------------------------------------------

@bp.route("/rallyes/<nom>/<int:annee>/etapes/<int:num>")
def etape(nom, annee, num):
    etape = db.get_or_404(Etape, (nom, annee, num))
    categorie = categorie_demandee()
    v = VClassementEtape
    classe = ~v.disqualifiee
    par_categorie = {"partition_by": (Vehicule.type, v.disqualifiee)}
    requete = (
        select(v.numEquipage, v.numeroOrga, v.nomEquipe, v.dureeHeure, v.disqualifiee, v.rang,
               Vehicule.type.label("categorie"), Vehicule.nomMarque,
               case((classe, func.rank().over(order_by=v.dureeHeure, **par_categorie)))
               .label("rangCategorie"),
               case((classe, v.dureeHeure - func.min(v.dureeHeure).over(**par_categorie)))
               .label("ecart"))
        .join(*jointure_vehicule(v)[0])
        .join(*jointure_vehicule(v)[1])
        .where(du_rallye(v, nom, annee), v.numEtape == num)
    )
    if categorie:
        requete = requete.where(Vehicule.type == categorie)
        requete = requete.order_by(v.disqualifiee, "rangCategorie", v.numeroOrga)
    else:
        requete = requete.order_by(v.disqualifiee, v.rang, v.numeroOrga)

    nb_etapes = db.session.scalar(
        select(func.max(Etape.numEtape)).where(du_rallye(Etape, nom, annee)))
    return render_template("etape.html", etape=etape, r=etape.rallye, categorie=categorie,
                           classement=db.session.execute(requete).all(),
                           noms=equipiers(nom, annee), nb_etapes=nb_etapes)


@bp.route("/rallyes/<nom>/<int:annee>/equipages/<int:num>")
def equipage(nom, annee, num):
    equipage = db.get_or_404(Equipage, (nom, annee, num))
    v = VClassementEtape
    lignes = db.session.execute(
        select(Etape, v.dureeHeure, v.disqualifiee, v.rang)
        .join(v, and_(v.nomRallye == Etape.nomRallye, v.annee == Etape.annee,
                      v.numEtape == Etape.numEtape))
        .where(du_rallye(Etape, nom, annee), v.numEquipage == num)
        .order_by(Etape.numEtape)
    ).all()

    resultats, cumul = [], 0
    for ligne in lignes:
        cumul += ligne.dureeHeure or 0
        resultats.append((ligne, cumul))

    return render_template("equipage.html", equipage=equipage, r=equipage.rallye,
                           v=equipage.pilote.vehicule, resultats=resultats,
                           statut=statut_equipage(equipage),
                           nb_etapes=len(equipage.rallye.etapes))


def statut_equipage(equipage):
    """(couleur, texte) : classé avec son rang, disqualifié ou abandon."""
    nom, annee, num = equipage.nomRallye, equipage.annee, equipage.numEquipage
    nb_resultats, disqualification, derniere = db.session.execute(
        select(func.count(),
               func.min(case((Resultat.disqualifiee, Resultat.numEtape))),
               func.max(Resultat.numEtape))
        .where(du_rallye(Resultat, nom, annee), Resultat.numEquipage == num)
    ).one()
    nb_etapes = db.session.scalar(
        select(func.count()).select_from(Etape).where(du_rallye(Etape, nom, annee)))
    if disqualification:
        return "danger", f"Disqualifié à l'étape {disqualification}"
    if nb_resultats < nb_etapes:
        return "secondary", f"Abandon après l'étape {derniere or 0}"
    categorie = equipage.pilote.vehicule.type
    rang = next((c.rang for c in classement_general(nom, annee, categorie)
                 if c.numEquipage == num), None)
    return "success", f"Classé {ordinal(rang)} en {categorie.lower()}"
