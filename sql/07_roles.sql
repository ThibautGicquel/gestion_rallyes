-- Rôles PostgreSQL des profils de l'application et comptes utilisateurs
-- À rejouer après 01_tables.sql : la suppression des tables efface les droits

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rallye_lecture') THEN
        CREATE ROLE rallye_lecture NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rallye_saisie') THEN
        CREATE ROLE rallye_saisie NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rallye_admin') THEN
        CREATE ROLE rallye_admin NOLOGIN;
    END IF;
END
$$;

-- Hiérarchie : admin hérite de saisie, qui hérite de lecture
GRANT rallye_lecture TO rallye_saisie;
GRANT rallye_saisie  TO rallye_admin;

-- Comptes de l'application (non supprimés par 01_tables.sql)
CREATE TABLE IF NOT EXISTS utilisateur (
    login           VARCHAR(30)  PRIMARY KEY,
    motDePasse      VARCHAR(255) NOT NULL,                               -- hash
    profil          VARCHAR(14)  NOT NULL
                    CHECK (profil IN ('organisateur', 'administrateur'))
);

GRANT USAGE ON SCHEMA public TO rallye_lecture;

-- Visiteur : lecture des tables et des vues, sauf les comptes
GRANT SELECT ON ALL TABLES IN SCHEMA public TO rallye_lecture;
REVOKE ALL ON utilisateur FROM rallye_lecture;

-- Organisateur : éditions, étapes, équipages et résultats
GRANT INSERT, UPDATE, DELETE ON
    rallye, sponsorise_rallye, fournit,
    etape, speciale, liaison, traverse,
    equipage, compose, pilote, resultat
TO rallye_saisie;

-- Administrateur : toutes les tables, référentiels et comptes compris
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rallye_admin;
