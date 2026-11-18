"""Listes et fiches des concurrents, équipes, marques, véhicules et pays."""
from itertools import groupby

from flask import Blueprint, render_template, request
from sqlalchemy import func, select, tuple_, union_all
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.orm import joinedload, selectinload

from . import db
from .consultation import statut_equipage
from .modeles import (Association, Compose, Concurrent, Equipage, Equipe, Marque, Officielle,
                      Pays, Pilote, Rallye, Vehicule, VEtapePays, panache, traverse)
from .outils import CATEGORIES, Tri, categorie_demandee, paginer_lignes

bp = Blueprint("annuaire", __name__)


def texte_recherche():
    return (request.args.get("q") or "").strip()


# ---------------------------------------------------------------------
# Concurrents
# ---------------------------------------------------------------------

@bp.route("/concurrents")
def concurrents():
    q = texte_recherche()
    pays = request.args.get("pays") or None
    nb = (select(Compose.numConcurrent, func.count().label("nb"))
          .group_by(Compose.numConcurrent).subquery())
    participations = func.coalesce(nb.c.nb, 0)
    tri = Tri({"nom": Concurrent.nom, "prenom": Concurrent.prenom,
               "pays": Concurrent.nomPays, "participations": participations}, defaut="nom")

    requete = (select(Concurrent, participations.label("participations"))
               .select_from(Concurrent)
               .outerjoin(nb, nb.c.numConcurrent == Concurrent.numConcurrent))
    if q:
        filtre = Concurrent.nom.icontains(q, autoescape=True) | \
                 Concurrent.prenom.icontains(q, autoescape=True)
        if q.isdigit():
            filtre |= Concurrent.numConcurrent == int(q)
        requete = requete.where(filtre)
    if pays:
        requete = requete.where(Concurrent.nomPays == pays)
    requete = requete.order_by(tri.expression, Concurrent.nom, Concurrent.prenom)

    tous_pays = db.session.scalars(select(Pays.nomPays).order_by(Pays.nomPays)).all()
    return render_template("concurrents.html", page=paginer_lignes(requete, 25), tri=tri,
                           q=q, pays=pays, tous_pays=tous_pays)


@bp.route("/concurrents/<int:num>")
def concurrent(num):
    concurrent = db.get_or_404(Concurrent, num)
    participations = db.session.scalars(
        select(Compose).where(Compose.numConcurrent == num)
        .options(joinedload(Compose.equipage).joinedload(Equipage.pilote)
                 .joinedload(Pilote.vehicule),
                 joinedload(Compose.equipage).joinedload(Equipage.equipe),
                 joinedload(Compose.equipage).selectinload(Equipage.concurrents))
        .order_by(Compose.annee.desc(), Compose.nomRallye)
    ).unique().all()
    historique = [(p.equipage, statut_equipage(p.equipage)) for p in participations]

    # Fonction SQL nb_participations (sql/04_fonctions_triggers.sql), par rallye
    noms = sorted({p.nomRallye for p in participations})
    par_rallye = [(n, db.session.scalar(select(func.nb_participations(num, n)))) for n in noms]
    return render_template("concurrent.html", concurrent=concurrent, historique=historique,
                           par_rallye=par_rallye)


# ---------------------------------------------------------------------
# Équipes
# ---------------------------------------------------------------------

def marques_des_equipes():
    """Sous-requête (nomEquipe, nomMarque) : marque d'une équipe officielle ou
    marques panachées d'une association."""
    officielle = Officielle.__table__
    return union_all(
        select(officielle.c.nomequipe.label("nomEquipe"), officielle.c.nommarque.label("nomMarque")),
        select(panache.c.nomequipe, panache.c.nommarque),
    ).subquery()


@bp.route("/equipes")
def equipes():
    q = texte_recherche()
    type_equipe = request.args.get("type") if request.args.get("type") in (
        "OFFICIELLE", "ASSOCIATION") else None
    marque = request.args.get("marque") or None

    mq = marques_des_equipes()
    marques = (select(mq.c.nomEquipe,
                      func.string_agg(mq.c.nomMarque, aggregate_order_by(", ", mq.c.nomMarque))
                      .label("marques"))
               .group_by(mq.c.nomEquipe).subquery())
    engagements = (select(Equipage.nomEquipe,
                          func.count().label("equipages"),
                          func.count(tuple_(Equipage.nomRallye, Equipage.annee).distinct())
                          .label("editions"))
                   .group_by(Equipage.nomEquipe).subquery())
    nb_equipages = func.coalesce(engagements.c.equipages, 0)
    tri = Tri({"nom": Equipe.nomEquipe, "type": Equipe.typeEquipe, "budget": Equipe.budget,
               "marques": marques.c.marques, "equipages": nb_equipages}, defaut="nom")

    requete = (
        select(Equipe.nomEquipe, Equipe.typeEquipe, Equipe.budget, marques.c.marques,
               nb_equipages.label("equipages"),
               func.coalesce(engagements.c.editions, 0).label("editions"))
        .select_from(Equipe)
        .outerjoin(marques, marques.c.nomEquipe == Equipe.nomEquipe)
        .outerjoin(engagements, engagements.c.nomEquipe == Equipe.nomEquipe)
    )
    if q:
        requete = requete.where(Equipe.nomEquipe.icontains(q, autoescape=True))
    if type_equipe:
        requete = requete.where(Equipe.typeEquipe == type_equipe)
    if marque:
        requete = requete.where(Equipe.nomEquipe.in_(
            select(mq.c.nomEquipe).where(mq.c.nomMarque == marque)))
    requete = requete.order_by(tri.expression, Equipe.nomEquipe)

    toutes_marques = db.session.scalars(select(Marque.nomMarque).order_by(Marque.nomMarque))
    return render_template("equipes.html", page=paginer_lignes(requete, 25), tri=tri, q=q,
                           type_equipe=type_equipe, marque=marque,
                           toutes_marques=toutes_marques.all())


@bp.route("/equipes/<nom>")
def equipe(nom):
    equipe = db.get_or_404(Equipe, nom)
    equipages = db.session.scalars(
        select(Equipage).where(Equipage.nomEquipe == nom)
        .options(joinedload(Equipage.pilote).joinedload(Pilote.vehicule),
                 selectinload(Equipage.concurrents))
        .order_by(Equipage.annee.desc(), Equipage.nomRallye, Equipage.numEquipage)
    ).all()
    editions = [(cle, list(groupe)) for cle, groupe
                in groupby(equipages, key=lambda e: (e.nomRallye, e.annee))]
    return render_template("equipe.html", equipe=equipe, editions=editions,
                           nb_equipages=len(equipages))


# ---------------------------------------------------------------------
# Marques et véhicules
# ---------------------------------------------------------------------

@bp.route("/marques")
def marques():
    vehicules = (select(Vehicule.nomMarque, func.count().label("total"),
                        *[func.count().filter(Vehicule.type == c).label(c) for c in CATEGORIES])
                 .group_by(Vehicule.nomMarque).subquery())
    officielles = (select(Officielle.nomMarque, func.count().label("nb"))
                   .group_by(Officielle.nomMarque).subquery())
    associations = (select(panache.c.nommarque.label("nomMarque"), func.count().label("nb"))
                    .group_by(panache.c.nommarque).subquery())
    colonnes = {
        "nom": Marque.nomMarque,
        "vehicules": func.coalesce(vehicules.c.total, 0),
        **{c.lower(): func.coalesce(vehicules.c[c], 0) for c in CATEGORIES},
        "officielles": func.coalesce(officielles.c.nb, 0),
        "associations": func.coalesce(associations.c.nb, 0),
    }
    tri = Tri(colonnes, defaut="nom")
    lignes = db.session.execute(
        select(*[colonne.label(cle) for cle, colonne in colonnes.items()])
        .select_from(Marque)
        .outerjoin(vehicules, vehicules.c.nomMarque == Marque.nomMarque)
        .outerjoin(officielles, officielles.c.nomMarque == Marque.nomMarque)
        .outerjoin(associations, associations.c.nomMarque == Marque.nomMarque)
        .order_by(tri.expression, Marque.nomMarque)
    ).all()
    return render_template("marques.html", lignes=lignes, tri=tri)


@bp.route("/marques/<nom>")
def marque(nom):
    marque = db.get_or_404(Marque, nom)
    categorie = categorie_demandee()
    officielles = db.session.scalars(
        select(Officielle).where(Officielle.nomMarque == nom).order_by(Officielle.nomEquipe)).all()
    associations = db.session.scalars(
        select(Association).join(panache).where(panache.c.nommarque == nom)
        .order_by(Association.nomEquipe)).all()

    tri = Tri({"serie": Vehicule.numeroSerie, "type": Vehicule.type,
               "cylindree": Vehicule.cylindree, "participations": func.count(Pilote.numeroSerie),
               "derniere": func.max(Pilote.annee)}, defaut="serie")
    requete = (
        select(Vehicule, func.count(Pilote.numeroSerie).label("participations"),
               func.max(Pilote.annee).label("derniere"))
        .outerjoin(Pilote, Pilote.numeroSerie == Vehicule.numeroSerie)
        .where(Vehicule.nomMarque == nom)
        .group_by(Vehicule.numeroSerie)
        .order_by(tri.expression, Vehicule.numeroSerie)
    )
    if categorie:
        requete = requete.where(Vehicule.type == categorie)
    return render_template("marque.html", marque=marque, officielles=officielles,
                           associations=associations, page=paginer_lignes(requete, 25),
                           tri=tri, categorie=categorie)


@bp.route("/vehicules/<serie>")
def vehicule(serie):
    vehicule = db.get_or_404(Vehicule, serie)
    pilotages = db.session.scalars(
        select(Pilote).where(Pilote.numeroSerie == serie)
        .options(joinedload(Pilote.equipage).joinedload(Equipage.equipe),
                 joinedload(Pilote.equipage).selectinload(Equipage.concurrents))
        .order_by(Pilote.annee.desc(), Pilote.nomRallye)
    ).all()
    return render_template("vehicule.html", vehicule=vehicule, pilotages=pilotages)


# ---------------------------------------------------------------------
# Pays
# ---------------------------------------------------------------------

@bp.route("/pays")
def pays_liste():
    etapes = (select(traverse.c.nompays.label("nomPays"), func.count().label("nb"))
              .group_by(traverse.c.nompays).subquery())
    nationaux = (select(Concurrent.nomPays, func.count().label("nb"))
                 .group_by(Concurrent.nomPays).subquery())
    colonnes = {"nom": Pays.nomPays, "etapes": func.coalesce(etapes.c.nb, 0),
                "concurrents": func.coalesce(nationaux.c.nb, 0)}
    tri = Tri(colonnes, defaut="nom")
    lignes = db.session.execute(
        select(*[colonne.label(cle) for cle, colonne in colonnes.items()])
        .select_from(Pays)
        .outerjoin(etapes, etapes.c.nomPays == Pays.nomPays)
        .outerjoin(nationaux, nationaux.c.nomPays == Pays.nomPays)
        .order_by(tri.expression, Pays.nomPays)
    ).all()
    return render_template("pays_liste.html", lignes=lignes, tri=tri)


@bp.route("/pays/<nom>")
def pays(nom):
    pays = db.get_or_404(Pays, nom)
    rallye = request.args.get("rallye") or None
    v = VEtapePays
    requete = (
        select(v)
        .join(traverse, (traverse.c.nomrallye == v.nomRallye) & (traverse.c.annee == v.annee)
              & (traverse.c.numetape == v.numEtape))
        .where(traverse.c.nompays == nom)
        .order_by(v.annee.desc(), v.nomRallye, v.numEtape)
    )
    if rallye:
        requete = requete.where(v.nomRallye == rallye)
    nb_concurrents = db.session.scalar(
        select(func.count()).select_from(Concurrent).where(Concurrent.nomPays == nom))
    noms = db.session.scalars(select(Rallye.nomRallye).distinct().order_by(Rallye.nomRallye))
    return render_template("pays.html", pays=pays, page=db.paginate(requete, per_page=25,
                                                                     error_out=False),
                           rallye=rallye, noms=noms.all(), nb_concurrents=nb_concurrents)
