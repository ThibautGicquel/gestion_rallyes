-- =====================================================================
--  Gestion des rallyes sportifs - 01 : tables et contraintes (PostgreSQL)
-- ---------------------------------------------------------------------
--  Adapté du script "Standard SQL" généré par DB-Main (schéma
--  GestionRallyes/Logique). Modifications par rapport au script généré :
--   * types adaptés à PostgreSQL (INTEGER, BIGINT, BOOLEAN, NUMERIC) ;
--   * compose : colonne numEquipage rétablie (clé étrangère vers EQUIPAGE) ;
--   * colonnes indicatrices de sous-types (SPECIALE/LIAISON, OFFICIELLE/
--     ASSOCIATION) remplacées par une colonne discriminante typeEtape /
--     typeEquipe, reprise dans les tables des sous-types : l'exclusivité
--     des partitions (C15) est ainsi garantie par les clés étrangères ;
--   * CHECK (exists (select ...)) supprimés : PostgreSQL n'accepte pas de
--     sous-requête dans un CHECK. Les contraintes concernées sont gérées
--     par triggers (04_triggers.sql) ou documentées dans le rapport ;
--   * CHECK métier ajoutés (contraintes C1 à C5) ;
--   * clés primaires réordonnées pour commencer par le rallye, ce qui sert
--     les requêtes filtrées par (nomRallye, annee).
--
--  Les noms non entre guillemets sont convertis en minuscules par
--  PostgreSQL : numConcurrent devient numconcurrent dans le catalogue.
--  Le script est rejouable : il supprime d'abord les tables existantes.
-- =====================================================================

DROP TABLE IF EXISTS resultat, traverse, pilote, compose, equipage,
                     speciale, liaison, etape,
                     sponsorise_rallye, sponsorise_equipe, fournit,
                     panache, officielle, association, equipe,
                     vehicule, concurrent,
                     rallye, pays, marque, sponsor, fournisseur CASCADE;


-- ---------------------------------------------------------------------
--  Tables de référence
-- ---------------------------------------------------------------------

CREATE TABLE pays (
    nomPays         VARCHAR(30)  PRIMARY KEY
);

CREATE TABLE marque (
    nomMarque       VARCHAR(50)  PRIMARY KEY
);

CREATE TABLE sponsor (
    nomSponsor      VARCHAR(50)  PRIMARY KEY
);

CREATE TABLE fournisseur (
    nomFournisseur  VARCHAR(50)  PRIMARY KEY
);

CREATE TABLE rallye (
    nomRallye       VARCHAR(50)  NOT NULL,
    annee           INTEGER      NOT NULL CHECK (annee BETWEEN 1900 AND 2100),
    PRIMARY KEY (nomRallye, annee)
);


-- ---------------------------------------------------------------------
--  Étapes et sous-types (partition SPECIALE / LIAISON)
-- ---------------------------------------------------------------------

CREATE TABLE etape (
    nomRallye       VARCHAR(50)  NOT NULL,
    annee           INTEGER      NOT NULL,
    numEtape        INTEGER      NOT NULL CHECK (numEtape > 0),
    villeDepart     VARCHAR(50)  NOT NULL,
    villeArrivee    VARCHAR(50)  NOT NULL,
    distance        NUMERIC(6,2) NOT NULL CHECK (distance > 0),          -- C3 (km)
    typeEtape       VARCHAR(8)   NOT NULL
                    CHECK (typeEtape IN ('SPECIALE', 'LIAISON')),        -- C15
    PRIMARY KEY (nomRallye, annee, numEtape),
    -- cible des clés étrangères des sous-types (exclusivité, C15)
    UNIQUE (nomRallye, annee, numEtape, typeEtape),
    FOREIGN KEY (nomRallye, annee) REFERENCES rallye (nomRallye, annee)
);

CREATE TABLE speciale (
    nomRallye       VARCHAR(50)  NOT NULL,
    annee           INTEGER      NOT NULL,
    numEtape        INTEGER      NOT NULL,
    typeEtape       VARCHAR(8)   NOT NULL DEFAULT 'SPECIALE'
                    CHECK (typeEtape = 'SPECIALE'),
    heureDebutEpoch BIGINT       NOT NULL,
    heureFinEpoch   BIGINT       NOT NULL,
    PRIMARY KEY (nomRallye, annee, numEtape),
    CHECK (heureFinEpoch > heureDebutEpoch),                             -- C4
    FOREIGN KEY (nomRallye, annee, numEtape, typeEtape)
        REFERENCES etape (nomRallye, annee, numEtape, typeEtape)
        ON DELETE CASCADE
);

CREATE TABLE liaison (
    nomRallye       VARCHAR(50)  NOT NULL,
    annee           INTEGER      NOT NULL,
    numEtape        INTEGER      NOT NULL,
    typeEtape       VARCHAR(8)   NOT NULL DEFAULT 'LIAISON'
                    CHECK (typeEtape = 'LIAISON'),
    PRIMARY KEY (nomRallye, annee, numEtape),
    FOREIGN KEY (nomRallye, annee, numEtape, typeEtape)
        REFERENCES etape (nomRallye, annee, numEtape, typeEtape)
        ON DELETE CASCADE
);

CREATE TABLE traverse (
    nomPays         VARCHAR(30)  NOT NULL REFERENCES pays (nomPays),
    nomRallye       VARCHAR(50)  NOT NULL,
    annee           INTEGER      NOT NULL,
    numEtape        INTEGER      NOT NULL,
    -- nomPays en tête : sert directement les requêtes 2 et 3
    PRIMARY KEY (nomPays, nomRallye, annee, numEtape),
    FOREIGN KEY (nomRallye, annee, numEtape)
        REFERENCES etape (nomRallye, annee, numEtape) ON DELETE CASCADE
);


-- ---------------------------------------------------------------------
--  Équipes et sous-types (partition OFFICIELLE / ASSOCIATION)
-- ---------------------------------------------------------------------

CREATE TABLE equipe (
    nomEquipe       VARCHAR(50)   PRIMARY KEY,
    budget          NUMERIC(12,2) NOT NULL CHECK (budget >= 0),          -- C3
    typeEquipe      VARCHAR(11)   NOT NULL
                    CHECK (typeEquipe IN ('OFFICIELLE', 'ASSOCIATION')), -- C15
    UNIQUE (nomEquipe, typeEquipe)
);

CREATE TABLE officielle (
    nomEquipe       VARCHAR(50)  PRIMARY KEY,
    typeEquipe      VARCHAR(11)  NOT NULL DEFAULT 'OFFICIELLE'
                    CHECK (typeEquipe = 'OFFICIELLE'),
    nomMarque       VARCHAR(50)  NOT NULL REFERENCES marque (nomMarque),  -- represente
    FOREIGN KEY (nomEquipe, typeEquipe)
        REFERENCES equipe (nomEquipe, typeEquipe) ON DELETE CASCADE
);

CREATE TABLE association (
    nomEquipe       VARCHAR(50)  PRIMARY KEY,
    typeEquipe      VARCHAR(11)  NOT NULL DEFAULT 'ASSOCIATION'
                    CHECK (typeEquipe = 'ASSOCIATION'),
    FOREIGN KEY (nomEquipe, typeEquipe)
        REFERENCES equipe (nomEquipe, typeEquipe) ON DELETE CASCADE
);

CREATE TABLE panache (
    nomEquipe       VARCHAR(50)  NOT NULL
                    REFERENCES association (nomEquipe) ON DELETE CASCADE,
    nomMarque       VARCHAR(50)  NOT NULL REFERENCES marque (nomMarque),
    PRIMARY KEY (nomEquipe, nomMarque)
);


-- ---------------------------------------------------------------------
--  Concurrents et véhicules
-- ---------------------------------------------------------------------

CREATE TABLE concurrent (
    numConcurrent   INTEGER      PRIMARY KEY,
    nom             VARCHAR(50)  NOT NULL,
    prenom          VARCHAR(50)  NOT NULL,
    adresse         VARCHAR(100) NOT NULL,
    nomPays         VARCHAR(30)  NOT NULL REFERENCES pays (nomPays)      -- a_nationalite
);

CREATE TABLE vehicule (
    numeroSerie     VARCHAR(50)  PRIMARY KEY,
    cylindree       INTEGER      NOT NULL CHECK (cylindree > 0),         -- C3 (cm3)
    type            VARCHAR(6)   NOT NULL
                    CHECK (type IN ('Auto', 'Camion', 'Moto')),          -- C1
    nomMarque       VARCHAR(50)  NOT NULL REFERENCES marque (nomMarque)  -- fabrique
);


-- ---------------------------------------------------------------------
--  Équipages
-- ---------------------------------------------------------------------

CREATE TABLE equipage (
    nomRallye       VARCHAR(50)  NOT NULL,
    annee           INTEGER      NOT NULL,
    numEquipage     INTEGER      NOT NULL CHECK (numEquipage > 0),
    nomEquipe       VARCHAR(50)  NOT NULL REFERENCES equipe (nomEquipe), -- appartient
    PRIMARY KEY (nomRallye, annee, numEquipage),
    FOREIGN KEY (nomRallye, annee) REFERENCES rallye (nomRallye, annee)  -- participe
);

CREATE TABLE compose (
    nomRallye       VARCHAR(50)  NOT NULL,
    annee           INTEGER      NOT NULL,
    numConcurrent   INTEGER      NOT NULL REFERENCES concurrent (numConcurrent),
    numEquipage     INTEGER      NOT NULL,
    -- C8 : un concurrent n'a qu'un seul équipage par rallye
    PRIMARY KEY (nomRallye, annee, numConcurrent),
    FOREIGN KEY (nomRallye, annee, numEquipage)
        REFERENCES equipage (nomRallye, annee, numEquipage) ON DELETE CASCADE
);

CREATE TABLE pilote (
    nomRallye       VARCHAR(50)  NOT NULL,
    annee           INTEGER      NOT NULL,
    numEquipage     INTEGER      NOT NULL,
    numeroOrga      INTEGER      NOT NULL CHECK (numeroOrga > 0),
    numeroSerie     VARCHAR(50)  NOT NULL REFERENCES vehicule (numeroSerie),
    PRIMARY KEY (nomRallye, annee, numEquipage),
    UNIQUE (nomRallye, annee, numeroSerie),                              -- C9
    UNIQUE (nomRallye, annee, numeroOrga),                               -- C10
    FOREIGN KEY (nomRallye, annee, numEquipage)
        REFERENCES equipage (nomRallye, annee, numEquipage) ON DELETE CASCADE
);


-- ---------------------------------------------------------------------
--  Résultats
-- ---------------------------------------------------------------------

CREATE TABLE resultat (
    nomRallye       VARCHAR(50)  NOT NULL,
    annee           INTEGER      NOT NULL,
    numEtape        INTEGER      NOT NULL,
    numEquipage     INTEGER      NOT NULL,
    dureeHeure      NUMERIC(8,4) CHECK (dureeHeure > 0),                 -- C3 (heures)
    disqualifiee    BOOLEAN      NOT NULL DEFAULT FALSE,                 -- C2
    -- C5 : un équipage non disqualifié a obligatoirement une durée
    CHECK (disqualifiee OR dureeHeure IS NOT NULL),
    PRIMARY KEY (nomRallye, annee, numEtape, numEquipage),
    -- C11 : nomRallye et annee sont partagés par les deux clés étrangères,
    -- l'étape et l'équipage appartiennent donc forcément au même rallye
    FOREIGN KEY (nomRallye, annee, numEtape)
        REFERENCES etape (nomRallye, annee, numEtape) ON DELETE CASCADE,
    FOREIGN KEY (nomRallye, annee, numEquipage)
        REFERENCES equipage (nomRallye, annee, numEquipage) ON DELETE CASCADE
);


-- ---------------------------------------------------------------------
--  Sponsoring et fourniture
-- ---------------------------------------------------------------------

CREATE TABLE sponsorise_rallye (
    nomRallye       VARCHAR(50)  NOT NULL,
    annee           INTEGER      NOT NULL,
    nomSponsor      VARCHAR(50)  NOT NULL REFERENCES sponsor (nomSponsor),
    PRIMARY KEY (nomRallye, annee, nomSponsor),
    FOREIGN KEY (nomRallye, annee)
        REFERENCES rallye (nomRallye, annee) ON DELETE CASCADE
);

CREATE TABLE sponsorise_equipe (
    nomEquipe       VARCHAR(50)  NOT NULL
                    REFERENCES equipe (nomEquipe) ON DELETE CASCADE,
    nomSponsor      VARCHAR(50)  NOT NULL REFERENCES sponsor (nomSponsor),
    PRIMARY KEY (nomEquipe, nomSponsor)
);

CREATE TABLE fournit (
    nomRallye       VARCHAR(50)  NOT NULL,
    annee           INTEGER      NOT NULL,
    nomFournisseur  VARCHAR(50)  NOT NULL REFERENCES fournisseur (nomFournisseur),
    PRIMARY KEY (nomRallye, annee, nomFournisseur),
    FOREIGN KEY (nomRallye, annee)
        REFERENCES rallye (nomRallye, annee) ON DELETE CASCADE
);
