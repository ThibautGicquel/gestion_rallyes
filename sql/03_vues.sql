-- =====================================================================
--  Gestion des rallyes sportifs - 03 : vues (PostgreSQL)
-- ---------------------------------------------------------------------
--  Les vues regroupent les jointures récurrentes : les requêtes du sujet
--  et l'application s'écrivent ensuite plus simplement.
-- =====================================================================

-- ---------------------------------------------------------------------
--  v_participation : une ligne par concurrent et par rallye couru,
--  avec son équipage, son équipe et son véhicule.
--  Utilisée par les requêtes 1, 4, 5 et 7.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_participation AS
SELECT c.nomRallye,
       c.annee,
       c.numEquipage,
       co.numConcurrent,
       co.nom,
       co.prenom,
       co.nomPays       AS nationalite,
       e.nomEquipe,
       eq.typeEquipe,
       p.numeroOrga,
       v.numeroSerie,
       v.nomMarque,
       v.type           AS typeVehicule
FROM compose    c
JOIN concurrent co ON co.numConcurrent = c.numConcurrent
JOIN equipage   e  ON (e.nomRallye, e.annee, e.numEquipage)
                    = (c.nomRallye, c.annee, c.numEquipage)
JOIN equipe     eq ON eq.nomEquipe = e.nomEquipe
JOIN pilote     p  ON (p.nomRallye, p.annee, p.numEquipage)
                    = (e.nomRallye, e.annee, e.numEquipage)
JOIN vehicule   v  ON v.numeroSerie = p.numeroSerie;


-- ---------------------------------------------------------------------
--  v_classement_etape : classement des équipages à chaque étape.
--  Les équipages disqualifiés apparaissent sans rang (contrainte C7) et
--  ne décalent pas le classement des autres.
--  Utilisée par la requête 6.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_classement_etape AS
SELECT r.nomRallye,
       r.annee,
       r.numEtape,
       et.typeEtape,
       r.numEquipage,
       e.nomEquipe,
       p.numeroOrga,
       r.dureeHeure,
       r.disqualifiee,
       CASE WHEN NOT r.disqualifiee THEN
            RANK() OVER (PARTITION BY r.nomRallye, r.annee, r.numEtape, r.disqualifiee
                         ORDER BY r.dureeHeure)
       END AS rang
FROM resultat r
JOIN etape    et ON (et.nomRallye, et.annee, et.numEtape)
                  = (r.nomRallye, r.annee, r.numEtape)
JOIN equipage e  ON (e.nomRallye, e.annee, e.numEquipage)
                  = (r.nomRallye, r.annee, r.numEquipage)
JOIN pilote   p  ON (p.nomRallye, p.annee, p.numEquipage)
                  = (r.nomRallye, r.annee, r.numEquipage);


-- ---------------------------------------------------------------------
--  v_etape_pays : chaque étape avec la liste des pays traversés.
--  Pratique pour l'affichage dans l'application.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_etape_pays AS
SELECT et.nomRallye,
       et.annee,
       et.numEtape,
       et.typeEtape,
       et.villeDepart,
       et.villeArrivee,
       et.distance,
       string_agg(t.nomPays, ', ' ORDER BY t.nomPays) AS pays
FROM etape et
LEFT JOIN traverse t ON (t.nomRallye, t.annee, t.numEtape)
                      = (et.nomRallye, et.annee, et.numEtape)
GROUP BY et.nomRallye, et.annee, et.numEtape;


-- ---------------------------------------------------------------------
--  v_rallye_stats : chiffres clés de chaque rallye.
--  Utilisée par la requête 4.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_rallye_stats AS
SELECT r.nomRallye,
       r.annee,
       (SELECT count(*) FROM etape et
         WHERE (et.nomRallye, et.annee) = (r.nomRallye, r.annee))   AS nbEtapes,
       (SELECT count(*) FROM equipage e
         WHERE (e.nomRallye, e.annee) = (r.nomRallye, r.annee))     AS nbEquipages,
       (SELECT count(*) FROM compose c
         WHERE (c.nomRallye, c.annee) = (r.nomRallye, r.annee))     AS nbConcurrents
FROM rallye r;
