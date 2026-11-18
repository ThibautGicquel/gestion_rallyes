"""Les 7 requêtes du sujet, lues dans sql/05_requetes.sql et exécutées avec des
paramètres modifiables à la place des valeurs de l'énoncé."""
import csv
import io
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from flask import Blueprint, Response, abort, render_template, request, url_for
from flask_sqlalchemy.pagination import Pagination
from sqlalchemy import select, text

from . import db
from .modeles import Marque, Pays, Rallye
from .outils import CATEGORIES, duree, nombre

bp = Blueprint("requetes", __name__)

SQL_DIR = Path(os.environ.get("SQL_DIR", Path(__file__).resolve().parents[2] / "sql"))


@dataclass
class Parametre:
    nom: str
    libelle: str
    genre: str      # rallye, annee, categorie, pays, marque ou entier
    avant: str      # texte de la requête contenant la valeur de l'énoncé
    apres: str      # même texte avec le paramètre
    defaut: object


def rallye(avant, apres="nomRallye = :rallye"):
    return Parametre("rallye", "Rallye", "rallye", avant, apres, "Paris-Dakar")


def annee(avant, valeur):
    return Parametre("annee", "Année", "annee", avant, "annee = :annee", valeur)


PARAMETRES = {
    1: [rallye("nomRallye = 'Paris-Dakar'"), annee("annee = 2000", 2000),
        Parametre("categorie", "Catégorie", "categorie", "typeVehicule = 'Moto'",
                  "typeVehicule = :categorie", "Moto")],
    2: [Parametre("pays", "Pays", "pays", "nomPays = 'Sénégal'", "nomPays = :pays", "Sénégal")],
    3: [Parametre("pays", "Pays", "pays", "t.nomPays = 'Sénégal'", "t.nomPays = :pays",
                  "Sénégal")],
    4: [rallye("nomRallye = 'Paris-Dakar'"), annee("annee = 2002", 2002)],
    5: [Parametre("marque", "Marque", "marque", "v.nomMarque = 'Toyota'",
                  "v.nomMarque = :marque", "Toyota"),
        rallye("p.nomRallye = 'Paris-Dakar'", "p.nomRallye = :rallye"),
        Parametre("nbAnnees", "Nombre d'années", "entier", "CURRENT_DATE) - 10",
                  "CURRENT_DATE) - :nbAnnees", 10)],
    6: [rallye("nomRallye = 'Paris-Dakar'"), annee("annee = 2002", 2002)],
    7: [rallye("nomRallye = 'Paris-Dakar'")],
}

LIBELLES = {
    "nom": "Nom", "prenom": "Prénom", "nbetapes": "Nombre d'étapes", "nomrallye": "Rallye",
    "annee": "Année", "numetape": "Étape", "villedepart": "Départ", "villearrivee": "Arrivée",
    "nbconcurrents": "Concurrents", "nbvehicules": "Véhicules", "typeetape": "Type",
    "rang": "Rang", "numequipage": "Équipage", "numeroorga": "N° orga", "nomequipe": "Équipe",
    "dureeheure": "Durée", "disqualifiee": "Disqualifié", "numconcurrent": "N° concurrent",
    "nbparticipations": "Participations",
}


def lire_requetes():
    """Découpe 05_requetes.sql en blocs commençant par '-- N)' (comme le notebook)."""
    texte = (SQL_DIR / "05_requetes.sql").read_text(encoding="utf-8")
    requetes = []
    for bloc in re.split(r"(?m)^(?=-- \d\))", texte)[1:]:
        lignes = bloc.strip().splitlines()
        titre = " ".join(l.lstrip("- ").strip() for l in lignes if l.startswith("--"))
        sql = "\n".join(l for l in lignes if not l.startswith("--")).strip().rstrip(";")
        requetes.append((titre, sql))
    return requetes


def requete_parametree(numero):
    requetes = lire_requetes()
    if not 1 <= numero <= len(requetes):
        abort(404)
    titre, sql = requetes[numero - 1]
    for p in PARAMETRES.get(numero, []):
        if sql.count(p.avant) != 1:
            raise RuntimeError(f"Requête {numero} : « {p.avant} » introuvable dans 05_requetes.sql")
        sql = sql.replace(p.avant, p.apres)
    return titre, sql


def valeurs_demandees(numero):
    valeurs = {}
    for p in PARAMETRES.get(numero, []):
        brut = (request.args.get(p.nom) or "").strip()
        if p.genre in ("annee", "entier"):
            try:
                valeur = int(brut)
            except ValueError:
                valeur = p.defaut
            bornes = (1900, 2100) if p.genre == "annee" else (1, 200)
            valeurs[p.nom] = min(max(valeur, bornes[0]), bornes[1])
        else:
            valeurs[p.nom] = brut or p.defaut
    return valeurs


class PaginationTexte(Pagination):
    """Pagination d'une requête SQL textuelle (LIMIT / OFFSET ajoutés à la fin)."""

    def _query_items(self):
        a = self._query_args
        resultat = db.session.execute(
            text(f"{a['sql']}\nLIMIT {int(self.per_page)} OFFSET {int(self._query_offset)}"),
            a["valeurs"])
        self.colonnes = list(resultat.keys())
        return resultat.all()

    def _query_count(self):
        a = self._query_args
        return db.session.scalar(text(f"SELECT count(*) FROM ({a['sql']}) AS r"), a["valeurs"])


def formater(colonne, valeur):
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return "oui" if valeur else ""
    if colonne == "dureeheure":
        return duree(valeur)
    if colonne.startswith("nb") and isinstance(valeur, (int, Decimal)):
        return nombre(valeur)
    return str(valeur)


def lien(colonne, ligne, valeurs):
    """Lien vers la fiche correspondante quand le résultat le permet."""
    d = ligne._mapping
    nom, annee_ = d.get("nomrallye", valeurs.get("rallye")), d.get("annee", valeurs.get("annee"))
    if colonne == "nomrallye" and "annee" in d:
        return url_for("consultation.rallye", nom=nom, annee=annee_)
    if colonne == "numetape" and nom and annee_:
        return url_for("consultation.etape", nom=nom, annee=annee_, num=d["numetape"])
    if colonne in ("numequipage", "numeroorga") and "numequipage" in d and nom and annee_:
        return url_for("consultation.equipage", nom=nom, annee=annee_, num=d["numequipage"])
    if colonne in ("numconcurrent", "nom", "prenom") and "numconcurrent" in d:
        return url_for("annuaire.concurrent", num=d["numconcurrent"])
    if colonne == "nomequipe":
        return url_for("annuaire.equipe", nom=d["nomequipe"])
    return None


def choix():
    """Valeurs proposées dans les listes déroulantes."""
    return {
        "rallye": db.session.scalars(select(Rallye.nomRallye).distinct()
                                     .order_by(Rallye.nomRallye)).all(),
        "pays": db.session.scalars(select(Pays.nomPays).order_by(Pays.nomPays)).all(),
        "marque": db.session.scalars(select(Marque.nomMarque).order_by(Marque.nomMarque)).all(),
        "categorie": CATEGORIES,
    }


@bp.route("/requetes")
def index():
    requetes = [(n, titre, PARAMETRES.get(n, []))
                for n, (titre, _) in enumerate(lire_requetes(), start=1)]
    return render_template("requetes.html", requetes=requetes)


@bp.route("/requetes/<int:numero>")
def requete(numero):
    titre, sql = requete_parametree(numero)
    valeurs = valeurs_demandees(numero)
    page = PaginationTexte(sql=sql, valeurs=valeurs, per_page=50, error_out=False)
    lignes = [[(formater(c, ligne[i]), lien(c, ligne, valeurs))
               for i, c in enumerate(page.colonnes)] for ligne in page.items]

    plan = None
    if request.args.get("plan"):
        plan = db.session.execute(text("EXPLAIN (ANALYZE, BUFFERS) " + sql), valeurs).scalars().all()

    return render_template("requete.html", numero=numero, titre=titre, sql=sql,
                           parametres=PARAMETRES.get(numero, []), valeurs=valeurs,
                           choix=choix(), page=page, lignes=lignes,
                           entetes=[LIBELLES.get(c, c) for c in page.colonnes], plan=plan,
                           nb_requetes=len(PARAMETRES))


@bp.route("/requetes/<int:numero>/csv")
def export_csv(numero):
    _, sql = requete_parametree(numero)
    resultat = db.session.execute(text(sql), valeurs_demandees(numero))
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";")
    ecrivain.writerow(resultat.keys())
    ecrivain.writerows(resultat)
    return Response("﻿" + sortie.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=requete_{numero}.csv"})
