-- Index sur les clés étrangères et les colonnes des requêtes

-- Jointure etape -> traverse
CREATE INDEX idx_traverse_etape     ON traverse (nomRallye, annee, numEtape);

-- Participations d'un concurrent (requête 7)
CREATE INDEX idx_compose_concurrent ON compose (numConcurrent);
-- Jointure compose -> equipage (requêtes 1, 4 et 7)
CREATE INDEX idx_compose_equipage   ON compose (nomRallye, annee, numEquipage);

-- Véhicules par marque (requête 5)
CREATE INDEX idx_vehicule_marque    ON vehicule (nomMarque);
-- Jointure vehicule -> pilote (requêtes 1 et 5)
CREATE INDEX idx_pilote_vehicule    ON pilote (numeroSerie);

-- Jointure resultat -> equipage (requête 6)
CREATE INDEX idx_resultat_equipage  ON resultat (nomRallye, annee, numEquipage);

-- Autres clés étrangères
CREATE INDEX idx_concurrent_pays    ON concurrent (nomPays);
CREATE INDEX idx_equipage_equipe    ON equipage (nomEquipe);
CREATE INDEX idx_officielle_marque  ON officielle (nomMarque);
CREATE INDEX idx_panache_marque     ON panache (nomMarque);
CREATE INDEX idx_spo_rallye_sponsor ON sponsorise_rallye (nomSponsor);
CREATE INDEX idx_spo_equipe_sponsor ON sponsorise_equipe (nomSponsor);
CREATE INDEX idx_fournit_fourn      ON fournit (nomFournisseur);
