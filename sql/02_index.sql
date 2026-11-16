-- =====================================================================
--  Gestion des rallyes sportifs - 02 : index (PostgreSQL)
-- ---------------------------------------------------------------------
--  PostgreSQL crée automatiquement un index pour chaque PRIMARY KEY et
--  chaque UNIQUE, mais PAS pour les clés étrangères. Les index uniques
--  générés par DB-Main (ID_..._IND) sont donc inutiles et ne sont pas repris.
--
--  On indexe ici :
--   * les clés étrangères qui ne sont pas déjà le début (préfixe) d'une
--     clé primaire ou d'un UNIQUE : elles servent aux jointures et évitent
--     un parcours complet de la table lors d'un DELETE sur la table cible ;
--   * les colonnes filtrées par les 7 requêtes du sujet.
-- =====================================================================

-- Étapes par pays (requêtes 2 et 3) : couvert par la clé primaire de
-- traverse, qui commence par nomPays. Index ci-dessous pour la jointure
-- inverse, de l'étape vers ses pays.
CREATE INDEX idx_traverse_etape     ON traverse (nomRallye, annee, numEtape);

-- Participations d'un concurrent (requête 7)
CREATE INDEX idx_compose_concurrent ON compose (numConcurrent);
-- Jointure compose -> equipage (requêtes 1, 4 et 7)
CREATE INDEX idx_compose_equipage   ON compose (nomRallye, annee, numEquipage);

-- Véhicules par marque (requête 5)
CREATE INDEX idx_vehicule_marque    ON vehicule (nomMarque);
-- Jointure vehicule -> pilote (requêtes 1 et 5)
CREATE INDEX idx_pilote_vehicule    ON pilote (numeroSerie);

-- Jointure resultat -> equipage, et résultats d'un équipage.
-- Le classement d'une édition ou d'une étape (requête 6) est servi par
-- cet index et par la clé primaire de resultat, qui commencent tous deux
-- par (nomRallye, annee). Un index partiel dédié au classement a été
-- testé : l'optimiseur ne l'utilisait jamais, il a donc été retiré.
CREATE INDEX idx_resultat_equipage  ON resultat (nomRallye, annee, numEquipage);

-- Autres clés étrangères
CREATE INDEX idx_concurrent_pays    ON concurrent (nomPays);
CREATE INDEX idx_equipage_equipe    ON equipage (nomEquipe);
CREATE INDEX idx_officielle_marque  ON officielle (nomMarque);
CREATE INDEX idx_panache_marque     ON panache (nomMarque);
CREATE INDEX idx_spo_rallye_sponsor ON sponsorise_rallye (nomSponsor);
CREATE INDEX idx_spo_equipe_sponsor ON sponsorise_equipe (nomSponsor);
CREATE INDEX idx_fournit_fourn      ON fournit (nomFournisseur);

-- Remarque : vehicule.type n'est pas indexé. Il n'a que 3 valeurs
-- possibles, un index serait trop peu sélectif pour être utilisé.
