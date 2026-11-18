"""Administration : référentiels (pays, marques, sponsors, fournisseurs), concurrents,
véhicules, équipes et comptes utilisateurs. Réservée au profil administrateur."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import delete, func, select
from werkzeug.security import generate_password_hash
from wtforms import (DecimalField, IntegerField, PasswordField, RadioField, SelectField,
                     SelectMultipleField, StringField)
from wtforms.validators import (DataRequired, EqualTo, InputRequired, Length, NumberRange,
                                Optional, Regexp, ValidationError)

from . import db
from .droits import role_requis
from .modeles import (Association, Concurrent, Equipage, Equipe, Fournisseur, Marque,
                      Officielle, Pays, Pilote, Sponsor, Utilisateur, Vehicule, fournit, panache,
                      sponsorise_equipe, sponsorise_rallye, traverse)
from .organisation import enregistrer
from .outils import CATEGORIES, Formulaire

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@role_requis("administrateur")
def verifier_profil():
    pass


def noms(colonne):
    return db.session.scalars(select(colonne).order_by(colonne)).all()


def compter(*conditions, depuis):
    return db.session.scalar(select(func.count()).select_from(depuis).where(*conditions))


def page_formulaire(form, titre, retour, chemin, aide=None, lecture_seule=()):
    """Formulaire générique : un champ par ligne, rendu selon son type."""
    return render_template("formulaire.html", form=form, titre=titre, retour=retour,
                           chemin=chemin, aide=aide, lecture_seule=lecture_seule)


@bp.route("/")
def index():
    chiffres = {cle: compter(depuis=modele) for cle, modele in [
        ("pays", Pays), ("marques", Marque), ("sponsors", Sponsor),
        ("fournisseurs", Fournisseur), ("concurrents", Concurrent), ("vehicules", Vehicule),
        ("equipes", Equipe), ("comptes", Utilisateur)]}
    return render_template("admin.html", chiffres=chiffres)


# ---------------------------------------------------------------------
# Référentiels à une seule colonne
# ---------------------------------------------------------------------

REFERENTIELS = {
    # cle: (modèle, attribut, titre, longueur, colonnes qui y font référence)
    "pays": (Pays, "nomPays", "Pays", 30,
             [Concurrent.__table__.c.nompays, traverse.c.nompays]),
    "marques": (Marque, "nomMarque", "Marques", 50,
                [Vehicule.__table__.c.nommarque, Officielle.__table__.c.nommarque,
                 panache.c.nommarque]),
    "sponsors": (Sponsor, "nomSponsor", "Sponsors", 50,
                 [sponsorise_rallye.c.nomsponsor, sponsorise_equipe.c.nomsponsor]),
    "fournisseurs": (Fournisseur, "nomFournisseur", "Fournisseurs", 50,
                     [fournit.c.nomfournisseur]),
}


class FormulaireValeur(Formulaire):
    valeur = StringField("Nouvelle valeur", validators=[DataRequired()])


def compter_usages(references, valeur=None):
    """valeur -> nombre de lignes qui la référencent (toutes tables confondues)."""
    usages = {}
    for colonne in references:
        requete = select(colonne, func.count()).group_by(colonne)
        if valeur is not None:
            requete = requete.where(colonne == valeur)
        for v, nb in db.session.execute(requete):
            usages[v] = usages.get(v, 0) + nb
    return usages


@bp.route("/referentiels/<cle>", methods=["GET", "POST"])
def referentiel(cle):
    if cle not in REFERENTIELS:
        abort(404)
    modele, attribut, titre, longueur, references = REFERENTIELS[cle]
    form = FormulaireValeur()
    if form.validate_on_submit():
        valeur = form.valeur.data.strip()
        if len(valeur) > longueur:
            form.valeur.errors.append(f"{longueur} caractères au maximum.")
        elif db.session.get(modele, valeur):
            form.valeur.errors.append("Cette valeur existe déjà.")
        else:
            db.session.add(modele(**{attribut: valeur}))
            if enregistrer(f"« {valeur} » ajouté."):
                return redirect(url_for("admin.referentiel", cle=cle))

    usages = compter_usages(references)
    valeurs = [(v, usages.get(v, 0)) for v in noms(getattr(modele, attribut))]
    return render_template("referentiel.html", cle=cle, titre=titre, form=form, valeurs=valeurs)


@bp.route("/referentiels/<cle>/supprimer", methods=["POST"])
def supprimer_referentiel(cle):
    if cle not in REFERENTIELS:
        abort(404)
    modele, attribut, _, _, references = REFERENTIELS[cle]
    valeur = request.form.get("valeur", "")
    db.get_or_404(modele, valeur)
    if compter_usages(references, valeur):
        flash(f"« {valeur} » est utilisé ailleurs : il ne peut pas être supprimé.", "erreur")
    else:
        # DELETE direct : l'ORM ne touche pas aux lignes liées, la base reste seule juge
        # (une clé étrangère l'empêcherait si une référence était apparue entre-temps).
        db.session.execute(delete(modele).where(getattr(modele, attribut) == valeur))
        enregistrer(f"« {valeur} » supprimé.")
    return redirect(url_for("admin.referentiel", cle=cle))


# ---------------------------------------------------------------------
# Concurrents
# ---------------------------------------------------------------------

class FormulaireConcurrent(Formulaire):
    nom = StringField("Nom", validators=[DataRequired(), Length(max=50)])
    prenom = StringField("Prénom", validators=[DataRequired(), Length(max=50)])
    adresse = StringField("Adresse", validators=[DataRequired(), Length(max=100)])
    nomPays = SelectField("Nationalité", validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nomPays.choices = noms(Pays.nomPays)


@bp.route("/concurrents/nouveau", methods=["GET", "POST"])
def nouveau_concurrent():
    form = FormulaireConcurrent()
    if form.validate_on_submit():
        numero = (db.session.scalar(select(func.max(Concurrent.numConcurrent))) or 0) + 1
        concurrent = Concurrent(numConcurrent=numero)
        form.populate_obj(concurrent)
        db.session.add(concurrent)
        if enregistrer(f"Concurrent {concurrent} créé (n° {numero})."):
            return redirect(url_for("annuaire.concurrent", num=numero))
    return page_formulaire(form, "Nouveau concurrent", url_for("annuaire.concurrents"),
                           [("Concurrents", url_for("annuaire.concurrents"))])


@bp.route("/concurrents/<int:num>/modifier", methods=["GET", "POST"])
def modifier_concurrent(num):
    concurrent = db.get_or_404(Concurrent, num)
    form = FormulaireConcurrent(obj=concurrent)
    if form.validate_on_submit():
        form.populate_obj(concurrent)
        if enregistrer(f"Concurrent {concurrent} modifié."):
            return redirect(url_for("annuaire.concurrent", num=num))
    fiche = url_for("annuaire.concurrent", num=num)
    return page_formulaire(form, f"Modifier {concurrent}", fiche,
                           [("Concurrents", url_for("annuaire.concurrents")), (str(concurrent), fiche)])


@bp.route("/concurrents/<int:num>/supprimer", methods=["POST"])
def supprimer_concurrent(num):
    concurrent = db.get_or_404(Concurrent, num)
    if concurrent.participations:
        flash("Ce concurrent a participé à des rallyes : il ne peut pas être supprimé.", "erreur")
        return redirect(url_for("annuaire.concurrent", num=num))
    db.session.delete(concurrent)
    if enregistrer(f"Concurrent {concurrent} supprimé."):
        return redirect(url_for("annuaire.concurrents"))
    return redirect(url_for("annuaire.concurrent", num=num))


# ---------------------------------------------------------------------
# Véhicules
# ---------------------------------------------------------------------

class FormulaireVehicule(Formulaire):
    numeroSerie = StringField("Numéro de série", validators=[DataRequired(), Length(max=50)])
    nomMarque = SelectField("Marque", validators=[DataRequired()])
    type = SelectField("Catégorie", choices=CATEGORIES, validators=[DataRequired()])
    cylindree = IntegerField("Cylindrée (cm³)", validators=[InputRequired(), NumberRange(1, 100000)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nomMarque.choices = noms(Marque.nomMarque)


@bp.route("/vehicules/nouveau", methods=["GET", "POST"])
def nouveau_vehicule():
    form = FormulaireVehicule()
    if request.method == "GET" and request.args.get("marque"):
        form.nomMarque.data = request.args["marque"]
    if form.validate_on_submit():
        serie = form.numeroSerie.data.strip()
        if db.session.get(Vehicule, serie):
            form.numeroSerie.errors.append("Ce numéro de série existe déjà.")
        else:
            vehicule = Vehicule()
            form.populate_obj(vehicule)
            vehicule.numeroSerie = serie
            db.session.add(vehicule)
            if enregistrer(f"Véhicule {serie} créé."):
                return redirect(url_for("annuaire.vehicule", serie=serie))
    return page_formulaire(form, "Nouveau véhicule", url_for("annuaire.marques"),
                           [("Marques", url_for("annuaire.marques"))])


@bp.route("/vehicules/<serie>/modifier", methods=["GET", "POST"])
def modifier_vehicule(serie):
    vehicule = db.get_or_404(Vehicule, serie)
    a_couru = bool(vehicule.pilotages)
    form = FormulaireVehicule(obj=vehicule)
    # Clé primaire non modifiable ; marque et catégorie figées si le véhicule a couru (C14)
    figes = ["numeroSerie"] + (["nomMarque", "type"] if a_couru else [])
    for nom in figes:
        getattr(form, nom).data = getattr(vehicule, nom)
    if form.validate_on_submit():
        vehicule.cylindree = form.cylindree.data
        if not a_couru:
            vehicule.nomMarque, vehicule.type = form.nomMarque.data, form.type.data
        if enregistrer(f"Véhicule {serie} modifié."):
            return redirect(url_for("annuaire.vehicule", serie=serie))
    fiche = url_for("annuaire.vehicule", serie=serie)
    aide = ("Ce véhicule a déjà couru : sa marque et sa catégorie ne sont plus modifiables, "
            "pour rester cohérentes avec les équipes de ses équipages (C14).") if a_couru else None
    return page_formulaire(form, f"Modifier le véhicule {serie}", fiche,
                           [("Marques", url_for("annuaire.marques")),
                            (vehicule.nomMarque, url_for("annuaire.marque", nom=vehicule.nomMarque)),
                            (serie, fiche)], aide=aide, lecture_seule=figes)


@bp.route("/vehicules/<serie>/supprimer", methods=["POST"])
def supprimer_vehicule(serie):
    vehicule = db.get_or_404(Vehicule, serie)
    marque = vehicule.nomMarque
    if vehicule.pilotages:
        flash("Ce véhicule a couru des rallyes : il ne peut pas être supprimé.", "erreur")
        return redirect(url_for("annuaire.vehicule", serie=serie))
    db.session.delete(vehicule)
    if enregistrer(f"Véhicule {serie} supprimé."):
        return redirect(url_for("annuaire.marque", nom=marque))
    return redirect(url_for("annuaire.vehicule", serie=serie))


# ---------------------------------------------------------------------
# Équipes (officielle : une marque ; association : au moins deux, C13)
# ---------------------------------------------------------------------

class FormulaireEquipe(Formulaire):
    nomEquipe = StringField("Nom de l'équipe", validators=[DataRequired(), Length(max=50)])
    typeEquipe = RadioField("Type", choices=[("OFFICIELLE", "Officielle (une seule marque)"),
                                             ("ASSOCIATION", "Association (panachage de marques)")],
                            default="OFFICIELLE", validators=[DataRequired()])
    budget = DecimalField("Budget (€)", places=2,
                          validators=[InputRequired(), NumberRange(0, 9_999_999_999.99)])
    marques = SelectMultipleField("Marques")
    sponsors = SelectMultipleField("Sponsors")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.marques.choices = noms(Marque.nomMarque)
        self.sponsors.choices = noms(Sponsor.nomSponsor)
        self.marques_engagees = set()

    def validate_marques(self, champ):
        if self.typeEquipe.data == "OFFICIELLE" and len(champ.data) != 1:
            raise ValidationError("Une équipe officielle représente exactement une marque.")
        if self.typeEquipe.data == "ASSOCIATION" and len(champ.data) < 2:
            raise ValidationError("Une association panache au moins deux marques (C13).")
        manquantes = self.marques_engagees - set(champ.data)
        if manquantes:
            raise ValidationError("Des équipages de l'équipe ont couru sur "
                                  f"{', '.join(sorted(manquantes))} : ces marques doivent rester (C14).")


def appliquer_equipe(equipe, form):
    equipe.budget = form.budget.data
    equipe.sponsors = [db.session.get(Sponsor, n) for n in form.sponsors.data]
    if isinstance(equipe, Officielle):
        equipe.nomMarque = form.marques.data[0]
    else:
        equipe.marques = [db.session.get(Marque, n) for n in form.marques.data]


@bp.route("/equipes/nouvelle", methods=["GET", "POST"])
def nouvelle_equipe():
    form = FormulaireEquipe()
    if form.validate_on_submit():
        nom = form.nomEquipe.data.strip()
        if db.session.get(Equipe, nom):
            form.nomEquipe.errors.append("Cette équipe existe déjà.")
        else:
            equipe = (Officielle if form.typeEquipe.data == "OFFICIELLE" else Association)(nomEquipe=nom)
            db.session.add(equipe)
            appliquer_equipe(equipe, form)
            if enregistrer(f"Équipe {nom} créée."):
                return redirect(url_for("annuaire.equipe", nom=nom))
    return page_formulaire(form, "Nouvelle équipe", url_for("annuaire.equipes"),
                           [("Équipes", url_for("annuaire.equipes"))])


@bp.route("/equipes/<nom>/modifier", methods=["GET", "POST"])
def modifier_equipe(nom):
    equipe = db.get_or_404(Equipe, nom)
    form = FormulaireEquipe(obj=equipe)
    if request.method == "GET":
        form.marques.data = [m.nomMarque for m in equipe.marques]
        form.sponsors.data = [s.nomSponsor for s in equipe.sponsors]
    # Nom (clé primaire) et type (sous-type) non modifiables
    form.nomEquipe.data, form.typeEquipe.data = equipe.nomEquipe, equipe.typeEquipe
    form.marques_engagees = set(db.session.scalars(
        select(Vehicule.nomMarque).distinct()
        .join(Pilote, Pilote.numeroSerie == Vehicule.numeroSerie)
        .join(Equipage, (Equipage.nomRallye == Pilote.nomRallye) & (Equipage.annee == Pilote.annee)
              & (Equipage.numEquipage == Pilote.numEquipage))
        .where(Equipage.nomEquipe == nom)))
    if form.validate_on_submit():
        appliquer_equipe(equipe, form)
        if enregistrer(f"Équipe {nom} modifiée."):
            return redirect(url_for("annuaire.equipe", nom=nom))
    fiche = url_for("annuaire.equipe", nom=nom)
    return page_formulaire(form, f"Modifier l'équipe {nom}", fiche,
                           [("Équipes", url_for("annuaire.equipes")), (nom, fiche)],
                           lecture_seule=["nomEquipe", "typeEquipe"])


@bp.route("/equipes/<nom>/supprimer", methods=["POST"])
def supprimer_equipe(nom):
    equipe = db.get_or_404(Equipe, nom)
    if equipe.equipages:
        flash("Cette équipe a engagé des équipages : elle ne peut pas être supprimée.", "erreur")
        return redirect(url_for("annuaire.equipe", nom=nom))
    db.session.delete(equipe)
    if enregistrer(f"Équipe {nom} supprimée."):
        return redirect(url_for("annuaire.equipes"))
    return redirect(url_for("annuaire.equipe", nom=nom))


# ---------------------------------------------------------------------
# Comptes utilisateurs
# ---------------------------------------------------------------------

PROFILS = [("organisateur", "Organisateur"), ("administrateur", "Administrateur")]


class FormulaireCompte(Formulaire):
    login = StringField("Identifiant", validators=[
        DataRequired(), Length(max=30),
        Regexp(r"^[A-Za-z0-9_.-]+$", message="Lettres, chiffres, « _ », « . » et « - » uniquement.")])
    profil = SelectField("Profil", choices=PROFILS, validators=[DataRequired()])
    motDePasse = PasswordField("Mot de passe", validators=[Optional(), Length(min=6, max=100)])
    confirmation = PasswordField("Confirmation", validators=[
        EqualTo("motDePasse", message="Les deux mots de passe sont différents.")])


class FormulaireNouveauCompte(FormulaireCompte):
    motDePasse = PasswordField("Mot de passe", validators=[DataRequired(), Length(min=6, max=100)])


@bp.route("/comptes")
def comptes():
    return render_template("comptes.html", comptes=db.session.scalars(
        select(Utilisateur).order_by(Utilisateur.profil, Utilisateur.login)).all())


@bp.route("/comptes/nouveau", methods=["GET", "POST"])
def nouveau_compte():
    form = FormulaireNouveauCompte()
    if form.validate_on_submit():
        if db.session.get(Utilisateur, form.login.data):
            form.login.errors.append("Cet identifiant existe déjà.")
        else:
            db.session.add(Utilisateur(login=form.login.data, profil=form.profil.data,
                                       motDePasse=generate_password_hash(form.motDePasse.data)))
            if enregistrer(f"Compte {form.login.data} créé."):
                return redirect(url_for("admin.comptes"))
    return page_formulaire(form, "Nouveau compte", url_for("admin.comptes"),
                           [("Administration", url_for("admin.index")),
                            ("Comptes", url_for("admin.comptes"))])


@bp.route("/comptes/<login>/modifier", methods=["GET", "POST"])
def modifier_compte(login):
    compte = db.get_or_404(Utilisateur, login)
    form = FormulaireCompte(obj=compte)
    form.login.data = login
    soi_meme = login == current_user.login
    if soi_meme:
        form.profil.data = compte.profil      # on ne retire pas ses propres droits
    if form.validate_on_submit():
        compte.profil = form.profil.data
        if form.motDePasse.data:
            compte.motDePasse = generate_password_hash(form.motDePasse.data)
        if enregistrer(f"Compte {login} modifié."):
            return redirect(url_for("admin.comptes"))
    return page_formulaire(form, f"Modifier le compte {login}", url_for("admin.comptes"),
                           [("Administration", url_for("admin.index")),
                            ("Comptes", url_for("admin.comptes"))],
                           aide="Laisser le mot de passe vide pour le conserver.",
                           lecture_seule=["login"] + (["profil"] if soi_meme else []))


@bp.route("/comptes/<login>/supprimer", methods=["POST"])
def supprimer_compte(login):
    compte = db.get_or_404(Utilisateur, login)
    if login == current_user.login:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "erreur")
    else:
        db.session.delete(compte)
        enregistrer(f"Compte {login} supprimé.")
    return redirect(url_for("admin.comptes"))
