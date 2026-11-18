"""Mapping SQLAlchemy des tables et vues créées par sql/01_tables.sql et sql/03_vues.sql.

Les tables sont créées par les scripts SQL, jamais par l'ORM (pas de create_all).
PostgreSQL stocke les noms en minuscules : les attributs gardent la casse du
modèle (nomRallye) et pointent vers la colonne en minuscules (nomrallye).
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (BigInteger, Boolean, Column, ForeignKey, ForeignKeyConstraint, Integer,
                        Numeric, String, Table)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import db


def col(nom, *args, **kwargs):
    return mapped_column(nom.lower(), *args, **kwargs)


def fk(colonnes, table, cibles=None, **kwargs):
    """Clé étrangère composée : fk(["nomRallye", "annee"], "rallye")."""
    locales = [c.lower() for c in colonnes]
    return ForeignKeyConstraint(locales, [f"{table}.{c}" for c in (cibles or locales)], **kwargs)


# ---------------------------------------------------------------------
# Tables d'association sans attribut propre
# ---------------------------------------------------------------------

traverse = Table(
    "traverse", db.metadata,
    Column("nompays", String(30), ForeignKey("pays.nompays"), primary_key=True),
    Column("nomrallye", String(50), primary_key=True),
    Column("annee", Integer, primary_key=True),
    Column("numetape", Integer, primary_key=True),
    fk(["nomRallye", "annee", "numEtape"], "etape", ondelete="CASCADE"),
)

panache = Table(
    "panache", db.metadata,
    Column("nomequipe", String(50), ForeignKey("association.nomequipe", ondelete="CASCADE"),
           primary_key=True),
    Column("nommarque", String(50), ForeignKey("marque.nommarque"), primary_key=True),
)

sponsorise_rallye = Table(
    "sponsorise_rallye", db.metadata,
    Column("nomrallye", String(50), primary_key=True),
    Column("annee", Integer, primary_key=True),
    Column("nomsponsor", String(50), ForeignKey("sponsor.nomsponsor"), primary_key=True),
    fk(["nomRallye", "annee"], "rallye", ondelete="CASCADE"),
)

sponsorise_equipe = Table(
    "sponsorise_equipe", db.metadata,
    Column("nomequipe", String(50), ForeignKey("equipe.nomequipe", ondelete="CASCADE"),
           primary_key=True),
    Column("nomsponsor", String(50), ForeignKey("sponsor.nomsponsor"), primary_key=True),
)

fournit = Table(
    "fournit", db.metadata,
    Column("nomrallye", String(50), primary_key=True),
    Column("annee", Integer, primary_key=True),
    Column("nomfournisseur", String(50), ForeignKey("fournisseur.nomfournisseur"),
           primary_key=True),
    fk(["nomRallye", "annee"], "rallye", ondelete="CASCADE"),
)


# ---------------------------------------------------------------------
# Tables de référence
# ---------------------------------------------------------------------

class Pays(db.Model):
    __tablename__ = "pays"
    nomPays: Mapped[str] = col("nomPays", String(30), primary_key=True)

    concurrents = relationship("Concurrent", back_populates="pays")
    etapes = relationship("Etape", secondary=traverse, back_populates="pays")


class Marque(db.Model):
    __tablename__ = "marque"
    nomMarque: Mapped[str] = col("nomMarque", String(50), primary_key=True)

    vehicules = relationship("Vehicule", back_populates="marque")


class Sponsor(db.Model):
    __tablename__ = "sponsor"
    nomSponsor: Mapped[str] = col("nomSponsor", String(50), primary_key=True)

    rallyes = relationship("Rallye", secondary=sponsorise_rallye, back_populates="sponsors")
    equipes = relationship("Equipe", secondary=sponsorise_equipe, back_populates="sponsors")


class Fournisseur(db.Model):
    __tablename__ = "fournisseur"
    nomFournisseur: Mapped[str] = col("nomFournisseur", String(50), primary_key=True)

    rallyes = relationship("Rallye", secondary=fournit, back_populates="fournisseurs")


class Rallye(db.Model):
    __tablename__ = "rallye"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)

    etapes = relationship("Etape", back_populates="rallye", order_by="Etape.numEtape",
                          cascade="all, delete-orphan")
    equipages = relationship("Equipage", back_populates="rallye",
                             order_by="Equipage.numEquipage", cascade="all, delete-orphan")
    sponsors = relationship("Sponsor", secondary=sponsorise_rallye, back_populates="rallyes",
                            order_by="Sponsor.nomSponsor")
    fournisseurs = relationship("Fournisseur", secondary=fournit, back_populates="rallyes",
                                order_by="Fournisseur.nomFournisseur")

    def __str__(self):
        return f"{self.nomRallye} {self.annee}"


# ---------------------------------------------------------------------
# Étapes : héritage SPECIALE / LIAISON (une table par sous-type)
# ---------------------------------------------------------------------

class Etape(db.Model):
    __tablename__ = "etape"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)
    numEtape: Mapped[int] = col("numEtape", Integer, primary_key=True)
    villeDepart: Mapped[str] = col("villeDepart", String(50))
    villeArrivee: Mapped[str] = col("villeArrivee", String(50))
    distance: Mapped[Decimal] = col("distance", Numeric(6, 2))
    typeEtape: Mapped[str] = col("typeEtape", String(8))

    __table_args__ = (fk(["nomRallye", "annee"], "rallye"),)
    __mapper_args__ = {"polymorphic_on": "typeEtape"}

    rallye = relationship("Rallye", back_populates="etapes")
    pays = relationship("Pays", secondary=traverse, back_populates="etapes",
                        order_by="Pays.nomPays")
    # passive_deletes : les résultats sont supprimés par la base (ON DELETE CASCADE)
    resultats = relationship("Resultat", back_populates="etape", cascade="all, delete-orphan",
                             passive_deletes=True, overlaps="resultats")

    @property
    def est_speciale(self):
        return self.typeEtape == "SPECIALE"

    def __str__(self):
        return f"Étape {self.numEtape} : {self.villeDepart} → {self.villeArrivee}"


def _epoch(secondes):
    return datetime.fromtimestamp(secondes, timezone.utc) if secondes is not None else None


class Speciale(Etape):
    __tablename__ = "speciale"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)
    numEtape: Mapped[int] = col("numEtape", Integer, primary_key=True)
    typeEtape: Mapped[str] = col("typeEtape", String(8))
    heureDebutEpoch: Mapped[int] = col("heureDebutEpoch", BigInteger)
    heureFinEpoch: Mapped[int] = col("heureFinEpoch", BigInteger)

    __table_args__ = (fk(["nomRallye", "annee", "numEtape", "typeEtape"], "etape",
                         ondelete="CASCADE"),)
    __mapper_args__ = {"polymorphic_identity": "SPECIALE"}

    @property
    def heureDebut(self):
        return _epoch(self.heureDebutEpoch)

    @property
    def heureFin(self):
        return _epoch(self.heureFinEpoch)


class Liaison(Etape):
    __tablename__ = "liaison"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)
    numEtape: Mapped[int] = col("numEtape", Integer, primary_key=True)
    typeEtape: Mapped[str] = col("typeEtape", String(8))

    __table_args__ = (fk(["nomRallye", "annee", "numEtape", "typeEtape"], "etape",
                         ondelete="CASCADE"),)
    __mapper_args__ = {"polymorphic_identity": "LIAISON"}


# ---------------------------------------------------------------------
# Équipes : héritage OFFICIELLE / ASSOCIATION
# ---------------------------------------------------------------------

class Equipe(db.Model):
    __tablename__ = "equipe"
    nomEquipe: Mapped[str] = col("nomEquipe", String(50), primary_key=True)
    budget: Mapped[Decimal] = col("budget", Numeric(12, 2))
    typeEquipe: Mapped[str] = col("typeEquipe", String(11))

    __mapper_args__ = {"polymorphic_on": "typeEquipe"}

    equipages = relationship("Equipage", back_populates="equipe")
    sponsors = relationship("Sponsor", secondary=sponsorise_equipe, back_populates="equipes",
                            order_by="Sponsor.nomSponsor")

    def __str__(self):
        return self.nomEquipe


class Officielle(Equipe):
    __tablename__ = "officielle"
    nomEquipe: Mapped[str] = col("nomEquipe", String(50), primary_key=True)
    typeEquipe: Mapped[str] = col("typeEquipe", String(11))
    nomMarque: Mapped[str] = col("nomMarque", String(50), ForeignKey("marque.nommarque"))

    __table_args__ = (fk(["nomEquipe", "typeEquipe"], "equipe", ondelete="CASCADE"),)
    __mapper_args__ = {"polymorphic_identity": "OFFICIELLE"}

    marque = relationship("Marque")

    @property
    def marques(self):
        return [self.marque]


class Association(Equipe):
    __tablename__ = "association"
    nomEquipe: Mapped[str] = col("nomEquipe", String(50), primary_key=True)
    typeEquipe: Mapped[str] = col("typeEquipe", String(11))

    __table_args__ = (fk(["nomEquipe", "typeEquipe"], "equipe", ondelete="CASCADE"),)
    __mapper_args__ = {"polymorphic_identity": "ASSOCIATION"}

    marques = relationship("Marque", secondary=panache, order_by="Marque.nomMarque")


# ---------------------------------------------------------------------
# Concurrents et véhicules
# ---------------------------------------------------------------------

class Concurrent(db.Model):
    __tablename__ = "concurrent"
    numConcurrent: Mapped[int] = col("numConcurrent", Integer, primary_key=True)
    nom: Mapped[str] = col("nom", String(50))
    prenom: Mapped[str] = col("prenom", String(50))
    adresse: Mapped[str] = col("adresse", String(100))
    nomPays: Mapped[str] = col("nomPays", String(30), ForeignKey("pays.nompays"))

    pays = relationship("Pays", back_populates="concurrents")
    participations = relationship("Compose", back_populates="concurrent")

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Vehicule(db.Model):
    __tablename__ = "vehicule"
    numeroSerie: Mapped[str] = col("numeroSerie", String(50), primary_key=True)
    cylindree: Mapped[int] = col("cylindree", Integer)
    type: Mapped[str] = col("type", String(6))
    nomMarque: Mapped[str] = col("nomMarque", String(50), ForeignKey("marque.nommarque"))

    marque = relationship("Marque", back_populates="vehicules")
    pilotages = relationship("Pilote", back_populates="vehicule")


# ---------------------------------------------------------------------
# Équipages
# ---------------------------------------------------------------------

class Equipage(db.Model):
    __tablename__ = "equipage"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)
    numEquipage: Mapped[int] = col("numEquipage", Integer, primary_key=True)
    nomEquipe: Mapped[str] = col("nomEquipe", String(50), ForeignKey("equipe.nomequipe"))

    __table_args__ = (fk(["nomRallye", "annee"], "rallye"),)

    rallye = relationship("Rallye", back_populates="equipages")
    equipe = relationship("Equipe", back_populates="equipages")
    membres = relationship("Compose", back_populates="equipage", cascade="all, delete-orphan")
    concurrents = relationship("Concurrent", secondary="compose", viewonly=True,
                               order_by="Concurrent.nom")
    pilote = relationship("Pilote", back_populates="equipage", uselist=False,
                          cascade="all, delete-orphan")
    resultats = relationship("Resultat", back_populates="equipage",
                             cascade="all, delete-orphan", passive_deletes=True,
                             overlaps="resultats")

    def __str__(self):
        return f"Équipage {self.numEquipage}"


class Compose(db.Model):
    """Appartenance d'un concurrent à un équipage (un seul par rallye : C8)."""
    __tablename__ = "compose"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)
    numConcurrent: Mapped[int] = col("numConcurrent", Integer,
                                     ForeignKey("concurrent.numconcurrent"), primary_key=True)
    numEquipage: Mapped[int] = col("numEquipage", Integer)

    __table_args__ = (fk(["nomRallye", "annee", "numEquipage"], "equipage", ondelete="CASCADE"),)

    equipage = relationship("Equipage", back_populates="membres")
    concurrent = relationship("Concurrent", back_populates="participations")


class Pilote(db.Model):
    """Affectation d'un véhicule et d'un numéro d'organisation à un équipage."""
    __tablename__ = "pilote"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)
    numEquipage: Mapped[int] = col("numEquipage", Integer, primary_key=True)
    numeroOrga: Mapped[int] = col("numeroOrga", Integer)
    numeroSerie: Mapped[str] = col("numeroSerie", String(50), ForeignKey("vehicule.numeroserie"))

    __table_args__ = (fk(["nomRallye", "annee", "numEquipage"], "equipage", ondelete="CASCADE"),)

    equipage = relationship("Equipage", back_populates="pilote")
    vehicule = relationship("Vehicule", back_populates="pilotages")


class Resultat(db.Model):
    __tablename__ = "resultat"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)
    numEtape: Mapped[int] = col("numEtape", Integer, primary_key=True)
    numEquipage: Mapped[int] = col("numEquipage", Integer, primary_key=True)
    dureeHeure: Mapped[Decimal | None] = col("dureeHeure", Numeric(8, 4))
    disqualifiee: Mapped[bool] = col("disqualifiee", Boolean, default=False)

    __table_args__ = (
        fk(["nomRallye", "annee", "numEtape"], "etape", ondelete="CASCADE"),
        fk(["nomRallye", "annee", "numEquipage"], "equipage", ondelete="CASCADE"),
    )

    # nomRallye et annee sont communs aux deux clés étrangères (C11)
    etape = relationship("Etape", back_populates="resultats", overlaps="equipage,resultats")
    equipage = relationship("Equipage", back_populates="resultats", overlaps="etape,resultats")


# ---------------------------------------------------------------------
# Comptes de l'application (sql/07_roles.sql)
# ---------------------------------------------------------------------

class Utilisateur(db.Model):
    __tablename__ = "utilisateur"
    login: Mapped[str] = col("login", String(30), primary_key=True)
    motDePasse: Mapped[str] = col("motDePasse", String(255))
    profil: Mapped[str] = col("profil", String(14))


# ---------------------------------------------------------------------
# Vues (lecture seule)
# ---------------------------------------------------------------------

class VParticipation(db.Model):
    __tablename__ = "v_participation"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)
    numConcurrent: Mapped[int] = col("numConcurrent", Integer, primary_key=True)
    numEquipage: Mapped[int] = col("numEquipage", Integer)
    nom: Mapped[str] = col("nom", String(50))
    prenom: Mapped[str] = col("prenom", String(50))
    nationalite: Mapped[str] = col("nationalite", String(30))
    nomEquipe: Mapped[str] = col("nomEquipe", String(50))
    typeEquipe: Mapped[str] = col("typeEquipe", String(11))
    numeroOrga: Mapped[int] = col("numeroOrga", Integer)
    numeroSerie: Mapped[str] = col("numeroSerie", String(50))
    nomMarque: Mapped[str] = col("nomMarque", String(50))
    typeVehicule: Mapped[str] = col("typeVehicule", String(6))


class VClassementEtape(db.Model):
    __tablename__ = "v_classement_etape"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)
    numEtape: Mapped[int] = col("numEtape", Integer, primary_key=True)
    numEquipage: Mapped[int] = col("numEquipage", Integer, primary_key=True)
    typeEtape: Mapped[str] = col("typeEtape", String(8))
    nomEquipe: Mapped[str] = col("nomEquipe", String(50))
    numeroOrga: Mapped[int] = col("numeroOrga", Integer)
    dureeHeure: Mapped[Decimal | None] = col("dureeHeure", Numeric(8, 4))
    disqualifiee: Mapped[bool] = col("disqualifiee", Boolean)
    rang: Mapped[int | None] = col("rang", BigInteger)


class VEtapePays(db.Model):
    __tablename__ = "v_etape_pays"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)
    numEtape: Mapped[int] = col("numEtape", Integer, primary_key=True)
    typeEtape: Mapped[str] = col("typeEtape", String(8))
    villeDepart: Mapped[str] = col("villeDepart", String(50))
    villeArrivee: Mapped[str] = col("villeArrivee", String(50))
    distance: Mapped[Decimal] = col("distance", Numeric(6, 2))
    pays: Mapped[str | None] = col("pays", String)


class VRallyeStats(db.Model):
    __tablename__ = "v_rallye_stats"
    nomRallye: Mapped[str] = col("nomRallye", String(50), primary_key=True)
    annee: Mapped[int] = col("annee", Integer, primary_key=True)
    nbEtapes: Mapped[int] = col("nbEtapes", BigInteger)
    nbEquipages: Mapped[int] = col("nbEquipages", BigInteger)
    nbConcurrents: Mapped[int] = col("nbConcurrents", BigInteger)
