-- Petit jeu de test, sur une base vide
BEGIN;
INSERT INTO pays VALUES ('France'),('Sénégal'),('Mauritanie');
INSERT INTO marque VALUES ('Toyota'),('Honda'),('Mazda');
INSERT INTO rallye VALUES ('Paris-Dakar',2000),('Paris-Dakar',2002),('Paris-Dakar',2020);
INSERT INTO etape VALUES ('Paris-Dakar',2002,1,'Paris','Paris',120,'LIAISON'),
                         ('Paris-Dakar',2002,2,'Dakar','Saint-Louis',260,'SPECIALE');
INSERT INTO liaison (nomRallye,annee,numEtape) VALUES ('Paris-Dakar',2002,1);
INSERT INTO speciale (nomRallye,annee,numEtape,heureDebutEpoch,heureFinEpoch) VALUES ('Paris-Dakar',2002,2,1010000000,1010030000);
INSERT INTO traverse VALUES ('France','Paris-Dakar',2002,1),('Sénégal','Paris-Dakar',2002,2),('Mauritanie','Paris-Dakar',2002,2);
INSERT INTO equipe VALUES ('Team Toyota',1500000,'OFFICIELLE'),('HONDA_MAZDA',800000,'ASSOCIATION');
INSERT INTO officielle (nomEquipe,nomMarque) VALUES ('Team Toyota','Toyota');
INSERT INTO association (nomEquipe) VALUES ('HONDA_MAZDA');
INSERT INTO panache VALUES ('HONDA_MAZDA','Honda'),('HONDA_MAZDA','Mazda');
INSERT INTO concurrent VALUES (1,'Dupont','Jean','1 rue A','France'),(2,'Martin','Paul','2 rue B','France'),
                              (3,'Diallo','Awa','3 rue C','Sénégal'),(4,'Bernard','Luc','4 rue D','France');
INSERT INTO vehicule VALUES ('TOY-001',4000,'Auto','Toyota'),('HON-001',450,'Moto','Honda');
INSERT INTO equipage VALUES ('Paris-Dakar',2002,1,'Team Toyota'),('Paris-Dakar',2002,2,'HONDA_MAZDA'),
                            ('Paris-Dakar',2020,1,'Team Toyota');
INSERT INTO compose VALUES ('Paris-Dakar',2002,1,1),('Paris-Dakar',2002,2,1),('Paris-Dakar',2002,3,2),('Paris-Dakar',2002,4,2),
                           ('Paris-Dakar',2020,1,1),('Paris-Dakar',2020,3,1);
INSERT INTO pilote VALUES ('Paris-Dakar',2002,1,201,'TOY-001'),('Paris-Dakar',2002,2,305,'HON-001'),('Paris-Dakar',2020,1,201,'TOY-001');
INSERT INTO resultat VALUES ('Paris-Dakar',2002,1,1,2.5,false),('Paris-Dakar',2002,1,2,2.25,false),
                            ('Paris-Dakar',2002,2,1,4.1,false),('Paris-Dakar',2002,2,2,NULL,true);
COMMIT;
