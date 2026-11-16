-- 1) Participants du rallye Paris-Dakar 2000 en catégorie moto,
--    par ordre alphabétique
SELECT nom, prenom
FROM v_participation
WHERE nomRallye = 'Paris-Dakar' AND annee = 2000
  AND typeVehicule = 'Moto'
ORDER BY nom, prenom;

-- 2) Nombre d'étapes se déroulant au Sénégal
SELECT count(*) AS nbEtapes
FROM traverse
WHERE nomPays = 'Sénégal';

-- 3) Étapes se déroulant au Sénégal
SELECT et.nomRallye, et.annee, et.numEtape, et.villeDepart, et.villeArrivee
FROM traverse t
JOIN etape et ON (et.nomRallye, et.annee, et.numEtape)
               = (t.nomRallye, t.annee, t.numEtape)
WHERE t.nomPays = 'Sénégal'
ORDER BY et.nomRallye, et.annee, et.numEtape;

-- 4) Rallyes ayant au moins autant de concurrents que le Paris-Dakar 2002
SELECT nomRallye, annee, nbConcurrents
FROM v_rallye_stats
WHERE nbConcurrents >= (SELECT nbConcurrents FROM v_rallye_stats
                        WHERE nomRallye = 'Paris-Dakar' AND annee = 2002)
ORDER BY nbConcurrents DESC, nomRallye, annee;

-- 5) Nombre de véhicules Toyota ayant participé au Paris-Dakar
--    sur les dix dernières années
SELECT count(DISTINCT p.numeroSerie) AS nbVehicules
FROM pilote p
JOIN vehicule v ON v.numeroSerie = p.numeroSerie
WHERE v.nomMarque = 'Toyota'
  AND p.nomRallye = 'Paris-Dakar'
  AND p.annee > EXTRACT(YEAR FROM CURRENT_DATE) - 10;

-- 6) Classement des équipages par étape pour le Paris-Dakar 2002
SELECT numEtape, typeEtape, rang, numEquipage, numeroOrga, nomEquipe,
       dureeHeure, disqualifiee
FROM v_classement_etape
WHERE nomRallye = 'Paris-Dakar' AND annee = 2002
ORDER BY numEtape, disqualifiee, rang;

-- 7) Nombre de participations au Paris-Dakar par concurrent
SELECT numConcurrent, nom, prenom, count(*) AS nbParticipations
FROM v_participation
WHERE nomRallye = 'Paris-Dakar'
GROUP BY numConcurrent, nom, prenom
ORDER BY nbParticipations DESC, nom, prenom;
