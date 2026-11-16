-- Une ligne par concurrent et par rallye (requêtes 1, 4, 5, 7)
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


-- Classement par étape, sans rang pour les disqualifiés (C7, requête 6)
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


-- Étapes avec la liste des pays traversés
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


-- Nombre d'étapes, d'équipages et de concurrents par rallye (requête 4)
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
