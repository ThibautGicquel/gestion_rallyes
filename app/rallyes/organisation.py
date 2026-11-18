"""Saisie réservée aux organisateurs : éditions de rallyes et étapes (suite dans saisie.py)."""
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import and_, delete, func, insert, select, update
from sqlalchemy.exc import SQLAlchemyError
from wtforms import (DateTimeLocalField, DecimalField, IntegerField, RadioField,
                     SelectMultipleField, StringField)
from wtforms.validators import (DataRequired, InputRequired, Length, NumberRange, Optional,
                                ValidationError)

from . import db
from .droits import role_requis
from .modeles import Etape, Fournisseur, Liaison, Pays, Rallye, Speciale, Sponsor
from .outils import Formulaire, message_erreur

bp = Blueprint("organisation", __name__, url_prefix="/organisation")


@bp.before_request
@role_requis("organisateur")
def verifier_profil():
    pass


def enregistrer(message):
    """Valide la transaction ; en cas de refus de la base, annule et affiche l'erreur."""
    try:
        db.session.commit()
        flash(message, "succes")
        return True
    except SQLAlchemyError as exc:
        db.session.rollback()
        flash(message_erreur(exc), "erreur")
        return False


# ---------------------------------------------------------------------
# Rallyes
# ---------------------------------------------------------------------

class FormulaireRallye(Formulaire):
    nomRallye = StringField("Nom du rallye", validators=[DataRequired(), Length(max=50)])
    annee = IntegerField("Année", validators=[InputRequired(), NumberRange(1900, 2100)])
    sponsors = SelectMultipleField("Sponsors")
    fournisseurs = SelectMultipleField("Fournisseurs")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sponsors.choices = db.session.scalars(
            select(Sponsor.nomSponsor).order_by(Sponsor.nomSponsor)).all()
        self.fournisseurs.choices = db.session.scalars(
            select(Fournisseur.nomFournisseur).order_by(Fournisseur.nomFournisseur)).all()


def appliquer_partenaires(rallye, form):
    rallye.sponsors = [db.session.get(Sponsor, n) for n in form.sponsors.data]
    rallye.fournisseurs = [db.session.get(Fournisseur, n) for n in form.fournisseurs.data]


@bp.route("/rallyes/nouveau", methods=["GET", "POST"])
def nouveau_rallye():
    form = FormulaireRallye()
    if form.validate_on_submit():
        nom = form.nomRallye.data.strip()
        if db.session.get(Rallye, (nom, form.annee.data)):
            form.annee.errors.append("Cette édition existe déjà.")
        else:
            rallye = Rallye(nomRallye=nom, annee=form.annee.data)
            db.session.add(rallye)
            appliquer_partenaires(rallye, form)
            if enregistrer(f"Rallye {rallye} créé. Ajoutez maintenant ses étapes."):
                return redirect(url_for("consultation.rallye", nom=nom, annee=form.annee.data))
    noms = db.session.scalars(select(Rallye.nomRallye).distinct().order_by(Rallye.nomRallye))
    return render_template("formulaire_rallye.html", form=form, rallye=None, noms=noms.all())


@bp.route("/rallyes/<nom>/<int:annee>/modifier", methods=["GET", "POST"])
def modifier_rallye(nom, annee):
    rallye = db.get_or_404(Rallye, (nom, annee))
    form = FormulaireRallye(obj=rallye)
    if request.method == "GET":
        form.sponsors.data = [s.nomSponsor for s in rallye.sponsors]
        form.fournisseurs.data = [f.nomFournisseur for f in rallye.fournisseurs]
    # Le nom et l'année forment la clé primaire : ils ne sont pas modifiables
    form.nomRallye.data, form.annee.data = nom, annee
    if form.validate_on_submit():
        appliquer_partenaires(rallye, form)
        if enregistrer(f"Rallye {rallye} modifié."):
            return redirect(url_for("consultation.rallye", nom=nom, annee=annee,
                                    onglet="partenaires"))
    return render_template("formulaire_rallye.html", form=form, rallye=rallye)


@bp.route("/rallyes/<nom>/<int:annee>/supprimer", methods=["POST"])
def supprimer_rallye(nom, annee):
    rallye = db.get_or_404(Rallye, (nom, annee))
    if rallye.equipages:
        flash("Ce rallye a des équipages inscrits : supprimez-les avant de supprimer le rallye.",
              "erreur")
        return redirect(url_for("consultation.rallye", nom=nom, annee=annee))
    db.session.delete(rallye)
    if enregistrer(f"Rallye {nom} {annee} supprimé avec ses étapes."):
        return redirect(url_for("consultation.rallyes"))
    return redirect(url_for("consultation.rallye", nom=nom, annee=annee))


# ---------------------------------------------------------------------
# Étapes
# ---------------------------------------------------------------------

FORMAT_HEURE = "%Y-%m-%dT%H:%M"


def vers_epoch(valeur):
    return int(valeur.replace(tzinfo=timezone.utc).timestamp())


def depuis_epoch(secondes):
    return datetime.fromtimestamp(secondes, timezone.utc).replace(tzinfo=None)


class FormulaireEtape(Formulaire):
    typeEtape = RadioField("Type", choices=[("SPECIALE", "Spéciale (tranche horaire imposée)"),
                                            ("LIAISON", "Liaison (sans limite de temps)")],
                           validators=[DataRequired()], default="SPECIALE")
    villeDepart = StringField("Ville de départ", validators=[DataRequired(), Length(max=50)])
    villeArrivee = StringField("Ville d'arrivée", validators=[DataRequired(), Length(max=50)])
    distance = DecimalField("Distance (km)", places=2,
                            validators=[InputRequired(), NumberRange(min=0.01, max=9999.99)])
    pays = SelectMultipleField("Pays traversés")
    debut = DateTimeLocalField("Début de la tranche horaire (UTC)", format=FORMAT_HEURE,
                               validators=[Optional()])
    fin = DateTimeLocalField("Fin de la tranche horaire (UTC)", format=FORMAT_HEURE,
                             validators=[Optional()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pays.choices = db.session.scalars(select(Pays.nomPays).order_by(Pays.nomPays)).all()

    def validate_pays(self, champ):
        if not champ.data:
            raise ValidationError("Une étape traverse au moins un pays.")

    def validate_fin(self, champ):
        if self.typeEtape.data != "SPECIALE":
            return
        if not self.debut.data or not champ.data:
            raise ValidationError("Une spéciale a une tranche horaire (début et fin).")
        if champ.data <= self.debut.data:
            raise ValidationError("La fin doit être postérieure au début (C4).")


def appliquer_etape(etape, form):
    etape.villeDepart = form.villeDepart.data.strip()
    etape.villeArrivee = form.villeArrivee.data.strip()
    etape.distance = form.distance.data
    etape.pays = [db.session.get(Pays, n) for n in form.pays.data]


def derniere_etape(nom, annee):
    return db.session.scalar(select(func.max(Etape.numEtape))
                             .where(Etape.nomRallye == nom, Etape.annee == annee)) or 0


@bp.route("/rallyes/<nom>/<int:annee>/etapes/nouvelle", methods=["GET", "POST"])
def nouvelle_etape(nom, annee):
    rallye = db.get_or_404(Rallye, (nom, annee))
    numero = derniere_etape(nom, annee) + 1     # numérotation continue (C16)
    form = FormulaireEtape()
    if request.method == "GET" and numero > 1:
        precedente = db.session.get(Etape, (nom, annee, numero - 1))
        form.villeDepart.data = precedente.villeArrivee
        form.pays.data = [p.nomPays for p in precedente.pays]

    if form.validate_on_submit():
        cle = dict(nomRallye=nom, annee=annee, numEtape=numero)
        if form.typeEtape.data == "SPECIALE":
            etape = Speciale(**cle, heureDebutEpoch=vers_epoch(form.debut.data),
                             heureFinEpoch=vers_epoch(form.fin.data))
        else:
            etape = Liaison(**cle)
        appliquer_etape(etape, form)
        db.session.add(etape)
        if enregistrer(f"Étape {numero} ajoutée au rallye {rallye}."):
            return redirect(url_for("consultation.rallye", nom=nom, annee=annee))
    return render_template("formulaire_etape.html", form=form, rallye=rallye, numero=numero,
                           etape=None)


def changer_type(etape, nouveau_type, debut, fin):
    """Passe une étape de spéciale à liaison (ou l'inverse) : la ligne de sous-type
    est remplacée et typeEtape mis à jour dans la même transaction (C15)."""
    cle = {"nomrallye": etape.nomRallye, "annee": etape.annee, "numetape": etape.numEtape}
    ancienne, nouvelle = ((Speciale, Liaison) if nouveau_type == "LIAISON"
                          else (Liaison, Speciale))
    condition = and_(*(ancienne.__table__.c[k] == v for k, v in cle.items()))
    db.session.flush()
    db.session.execute(delete(ancienne.__table__).where(condition))
    db.session.execute(update(Etape.__table__)
                       .where(and_(*(Etape.__table__.c[k] == v for k, v in cle.items())))
                       .values(typeetape=nouveau_type))
    valeurs = dict(cle, typeetape=nouveau_type)
    if nouveau_type == "SPECIALE":
        valeurs.update(heuredebutepoch=vers_epoch(debut), heurefinepoch=vers_epoch(fin))
    db.session.execute(insert(nouvelle.__table__).values(**valeurs))


@bp.route("/rallyes/<nom>/<int:annee>/etapes/<int:num>/modifier", methods=["GET", "POST"])
def modifier_etape(nom, annee, num):
    etape = db.get_or_404(Etape, (nom, annee, num))
    form = FormulaireEtape(obj=etape)
    if request.method == "GET":
        form.pays.data = [p.nomPays for p in etape.pays]
        if etape.est_speciale:
            form.debut.data = depuis_epoch(etape.heureDebutEpoch)
            form.fin.data = depuis_epoch(etape.heureFinEpoch)

    if form.validate_on_submit():
        appliquer_etape(etape, form)
        if form.typeEtape.data != etape.typeEtape:
            changer_type(etape, form.typeEtape.data, form.debut.data, form.fin.data)
        elif etape.est_speciale:
            etape.heureDebutEpoch = vers_epoch(form.debut.data)
            etape.heureFinEpoch = vers_epoch(form.fin.data)
        if enregistrer(f"Étape {num} modifiée."):
            return redirect(url_for("consultation.etape", nom=nom, annee=annee, num=num))
    return render_template("formulaire_etape.html", form=form, rallye=etape.rallye, numero=num,
                           etape=etape)


@bp.route("/rallyes/<nom>/<int:annee>/etapes/<int:num>/supprimer", methods=["POST"])
def supprimer_etape(nom, annee, num):
    etape = db.get_or_404(Etape, (nom, annee, num))
    if num != derniere_etape(nom, annee):
        flash("Seule la dernière étape peut être supprimée (numérotation continue des étapes).",
              "erreur")
        return redirect(url_for("consultation.etape", nom=nom, annee=annee, num=num))
    db.session.delete(etape)
    enregistrer(f"Étape {num} supprimée avec ses résultats.")
    return redirect(url_for("consultation.rallye", nom=nom, annee=annee))


# Inscription des équipages et saisie des résultats (mêmes droits, même blueprint)
from . import saisie  # noqa: E402,F401
