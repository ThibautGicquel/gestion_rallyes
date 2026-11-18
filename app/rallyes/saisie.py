"""Saisie réservée aux organisateurs (suite) : inscription des équipages et
résultats des étapes. Les routes appartiennent au blueprint organisation."""
import re

from flask import flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from wtforms import IntegerField, SelectField, StringField
from wtforms.validators import DataRequired, NumberRange, ValidationError

from . import db
from .consultation import du_rallye, jointure_vehicule
from .modeles import (Compose, Concurrent, Equipage, Equipe, Etape, Pilote, Rallye, Resultat,
                      Vehicule)
from .organisation import bp, enregistrer
from .outils import Formulaire, categorie_demandee, duree, lire_duree


# ---------------------------------------------------------------------
# Inscription d'un équipage
# ---------------------------------------------------------------------

def numero_saisi(texte):
    """ "1234 — Prénom Nom (Pays)" -> 1234"""
    m = re.match(r"\s*(\d+)", texte or "")
    return int(m.group(1)) if m else None


def marques_equipe(nom_equipe):
    equipe = db.session.get(Equipe, nom_equipe)
    return {m.nomMarque for m in equipe.marques} if equipe else set()


def vehicules_disponibles(nom, annee, nom_equipe):
    """Véhicules des marques de l'équipe (C14) pas encore engagés dans l'édition (C9)."""
    engages = select(Pilote.numeroSerie).where(du_rallye(Pilote, nom, annee))
    return db.session.scalars(
        select(Vehicule)
        .where(Vehicule.nomMarque.in_(marques_equipe(nom_equipe)),
               Vehicule.numeroSerie.not_in(engages))
        .order_by(Vehicule.type, Vehicule.nomMarque, Vehicule.numeroSerie)
    ).all()


def libelle_vehicule(v):
    return f"{v.numeroSerie} · {v.nomMarque} · {v.type} · {v.cylindree} cm³"


class FormulaireEquipage(Formulaire):
    nomEquipe = SelectField("Équipe", validators=[DataRequired()])
    concurrent1 = StringField("Premier concurrent", validators=[DataRequired()])
    concurrent2 = StringField("Second concurrent", validators=[DataRequired()])
    numeroSerie = SelectField("Véhicule", validators=[DataRequired()], validate_choice=False)
    numeroOrga = IntegerField("Numéro attribué par l'organisation",
                              validators=[DataRequired(), NumberRange(1, 99999)])

    def __init__(self, nom, annee, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nom, self.annee = nom, annee
        equipes = db.session.execute(
            select(Equipe.nomEquipe, Equipe.typeEquipe).order_by(Equipe.nomEquipe)).all()
        self.nomEquipe.choices = [("", "Choisir une équipe…")] + [
            (e.nomEquipe, f"{e.nomEquipe} ({e.typeEquipe.lower()})") for e in equipes]
        equipe = self.nomEquipe.data
        self.numeroSerie.choices = [("", "Choisir d'abord une équipe…")] + (
            [(v.numeroSerie, libelle_vehicule(v))
             for v in vehicules_disponibles(nom, annee, equipe)] if equipe else [])

    def _concurrent(self, champ):
        num = numero_saisi(champ.data)
        if num is None or not db.session.get(Concurrent, num):
            raise ValidationError("Concurrent introuvable : choisissez-le dans la liste.")
        deja = db.session.get(Compose, (self.nom, self.annee, num))
        if deja:
            raise ValidationError(f"Ce concurrent court déjà dans l'équipage "
                                  f"{deja.numEquipage} de ce rallye (C8).")
        return num

    def validate_concurrent1(self, champ):
        self._concurrent(champ)

    def validate_concurrent2(self, champ):
        if self._concurrent(champ) == numero_saisi(self.concurrent1.data):
            raise ValidationError("Les deux concurrents doivent être différents.")

    def validate_numeroSerie(self, champ):
        vehicule = db.session.get(Vehicule, champ.data)
        if not vehicule:
            raise ValidationError("Véhicule introuvable.")
        if vehicule.nomMarque not in marques_equipe(self.nomEquipe.data):
            raise ValidationError(f"{vehicule.nomMarque} ne fait pas partie des marques "
                                  f"de l'équipe (C14).")
        if db.session.scalar(select(func.count()).select_from(Pilote).where(
                du_rallye(Pilote, self.nom, self.annee), Pilote.numeroSerie == champ.data)):
            raise ValidationError("Ce véhicule est déjà engagé dans ce rallye (C9).")

    def validate_numeroOrga(self, champ):
        if db.session.scalar(select(func.count()).select_from(Pilote).where(
                du_rallye(Pilote, self.nom, self.annee), Pilote.numeroOrga == champ.data)):
            raise ValidationError("Ce numéro est déjà attribué dans ce rallye (C10).")


@bp.route("/rallyes/<nom>/<int:annee>/equipages/nouveau", methods=["GET", "POST"])
def nouvel_equipage(nom, annee):
    rallye = db.get_or_404(Rallye, (nom, annee))
    form = FormulaireEquipage(nom, annee)
    if request.method == "GET":
        form.numeroOrga.data = (db.session.scalar(
            select(func.max(Pilote.numeroOrga)).where(du_rallye(Pilote, nom, annee))) or 0) + 1

    if form.validate_on_submit():
        numero = (db.session.scalar(select(func.max(Equipage.numEquipage))
                                    .where(du_rallye(Equipage, nom, annee))) or 0) + 1
        # Équipage, ses 2 concurrents et son véhicule dans une même transaction :
        # le trigger différé C12 vérifie l'ensemble au COMMIT.
        with db.session.no_autoflush:
            equipage = Equipage(nomRallye=nom, annee=annee, numEquipage=numero,
                                nomEquipe=form.nomEquipe.data)
            db.session.add(equipage)
            equipage.membres = [Compose(nomRallye=nom, annee=annee, numConcurrent=numero_saisi(c.data))
                                for c in (form.concurrent1, form.concurrent2)]
            equipage.pilote = Pilote(nomRallye=nom, annee=annee, numeroOrga=form.numeroOrga.data,
                                     numeroSerie=form.numeroSerie.data)
        if enregistrer(f"Équipage n° {form.numeroOrga.data} inscrit au rallye {rallye}."):
            return redirect(url_for("consultation.equipage", nom=nom, annee=annee, num=numero))
    return render_template("formulaire_equipage.html", form=form, rallye=rallye)


@bp.route("/rallyes/<nom>/<int:annee>/equipages/<int:num>/supprimer", methods=["POST"])
def supprimer_equipage(nom, annee, num):
    equipage = db.get_or_404(Equipage, (nom, annee, num))
    numero_orga = equipage.pilote.numeroOrga
    db.session.delete(equipage)
    if enregistrer(f"Équipage n° {numero_orga} désinscrit, avec ses résultats."):
        return redirect(url_for("consultation.rallye", nom=nom, annee=annee, onglet="equipages"))
    return redirect(url_for("consultation.equipage", nom=nom, annee=annee, num=num))


# Recherches utilisées par le formulaire d'inscription (JavaScript)

@bp.route("/rallyes/<nom>/<int:annee>/concurrents-disponibles")
def concurrents_disponibles(nom, annee):
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify([])
    filtre = or_(Concurrent.nom.icontains(q, autoescape=True),
                 Concurrent.prenom.icontains(q, autoescape=True))
    if q.isdigit():
        filtre = or_(filtre, Concurrent.numConcurrent == int(q))
    inscrits = select(Compose.numConcurrent).where(du_rallye(Compose, nom, annee))
    concurrents = db.session.scalars(
        select(Concurrent).where(filtre, Concurrent.numConcurrent.not_in(inscrits))
        .order_by(Concurrent.nom, Concurrent.prenom).limit(15)).all()
    return jsonify([f"{c.numConcurrent} — {c.prenom} {c.nom} ({c.nomPays})" for c in concurrents])


@bp.route("/rallyes/<nom>/<int:annee>/vehicules-disponibles")
def vehicules_disponibles_json(nom, annee):
    equipe = request.args.get("equipe") or ""
    return jsonify([{"valeur": v.numeroSerie, "libelle": libelle_vehicule(v)}
                    for v in vehicules_disponibles(nom, annee, equipe)])


# ---------------------------------------------------------------------
# Résultats d'une étape
# ---------------------------------------------------------------------

def situation_avant(nom, annee, num):
    """numEquipage -> texte si l'équipage n'est plus en course avant cette étape."""
    lignes = db.session.execute(
        select(Resultat.numEquipage, func.max(Resultat.numEtape).label("derniere"),
               func.min(case((Resultat.disqualifiee, Resultat.numEtape))).label("disq"))
        .where(du_rallye(Resultat, nom, annee), Resultat.numEtape < num)
        .group_by(Resultat.numEquipage)
    ).all()
    situation = {}
    for l in lignes:
        if l.disq:
            situation[l.numEquipage] = f"disqualifié à l'étape {l.disq}"
        elif l.derniere < num - 1:
            situation[l.numEquipage] = f"abandon après l'étape {l.derniere}"
    return situation, {l.numEquipage for l in lignes}


@bp.route("/rallyes/<nom>/<int:annee>/etapes/<int:num>/resultats", methods=["GET", "POST"])
def resultats_etape(nom, annee, num):
    etape = db.get_or_404(Etape, (nom, annee, num))
    categorie = categorie_demandee()
    requete = (
        select(Equipage.numEquipage, Equipage.nomEquipe, Pilote.numeroOrga,
               Vehicule.type.label("categorie"), Vehicule.nomMarque)
        .join(*jointure_vehicule(Equipage)[0]).join(*jointure_vehicule(Equipage)[1])
        .where(du_rallye(Equipage, nom, annee))
        .order_by(Pilote.numeroOrga)
    )
    if categorie:
        requete = requete.where(Vehicule.type == categorie)
    equipages = db.session.execute(requete).all()
    existants = {r.numEquipage: r for r in db.session.scalars(
        select(Resultat).where(du_rallye(Resultat, nom, annee), Resultat.numEtape == num))}
    situation, ont_couru = situation_avant(nom, annee, num)
    for n in {e.numEquipage for e in equipages}:
        if num > 1 and n not in ont_couru:
            situation[n] = "aucun résultat aux étapes précédentes"

    limite = ((etape.heureFinEpoch - etape.heureDebutEpoch) / 3600
              if etape.est_speciale else None)
    saisie, erreurs = {}, {}

    if request.method == "POST":
        affiches = {e.numEquipage for e in equipages}
        ecritures, suppressions, hors_delai = [], [], 0
        for n in affiches:
            texte = (request.form.get(f"duree-{n}") or "").strip()
            disq = request.form.get(f"disq-{n}") == "1"
            saisie[n] = (texte, disq)
            valeur = None
            if texte:
                try:
                    valeur = lire_duree(texte)
                except ValueError as exc:
                    erreurs[n] = str(exc)
                    continue
                # Spéciale : terminer après la tranche horaire entraîne la disqualification
                if limite is not None and valeur > limite and not disq:
                    disq, hors_delai = True, hors_delai + 1
            if valeur is not None or disq:
                ecritures.append({"nomrallye": nom, "annee": annee, "numetape": num,
                                  "numequipage": n, "dureeheure": valeur, "disqualifiee": disq})
            elif n in existants:
                suppressions.append(n)

        if erreurs:
            flash(f"{len(erreurs)} durée(s) invalide(s) : rien n'a été enregistré.", "erreur")
        else:
            table = Resultat.__table__
            if ecritures:
                instruction = insert(table)
                db.session.execute(instruction.on_conflict_do_update(
                    index_elements=[table.c.nomrallye, table.c.annee, table.c.numetape,
                                    table.c.numequipage],
                    set_={"dureeheure": instruction.excluded.dureeheure,
                          "disqualifiee": instruction.excluded.disqualifiee}), ecritures)
            if suppressions:
                db.session.execute(delete(table).where(
                    table.c.nomrallye == nom, table.c.annee == annee,
                    table.c.numetape == num, table.c.numequipage.in_(suppressions)))
            message = (f"Étape {num} : {len(ecritures)} résultat(s) enregistré(s), "
                       f"{len(suppressions)} supprimé(s)")
            if hors_delai:
                message += f", {hors_delai} équipage(s) disqualifié(s) hors délai"
            if enregistrer(message + "."):
                return redirect(url_for("consultation.etape", nom=nom, annee=annee, num=num,
                                        categorie=categorie))

    lignes = []
    for e in equipages:
        if e.numEquipage in saisie:
            texte, disq = saisie[e.numEquipage]
        else:
            r = existants.get(e.numEquipage)
            texte, disq = (duree(r.dureeHeure), r.disqualifiee) if r else ("", False)
        lignes.append((e, texte, disq, situation.get(e.numEquipage), erreurs.get(e.numEquipage)))
    return render_template("resultats_etape.html", etape=etape, rallye=etape.rallye,
                           lignes=lignes, categorie=categorie, limite=limite,
                           nb_saisis=sum(1 for e in equipages if e.numEquipage in existants))
