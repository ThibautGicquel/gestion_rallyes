-- =====================================================================
--  Gestion des rallyes sportifs - 04 : fonctions et triggers (PostgreSQL)
-- ---------------------------------------------------------------------
--  Contraintes d'intégrité qui ne s'expriment ni par une clé ni par un
--  CHECK (voir le tableau des contraintes du rapport) :
--    C12  un équipage compte exactement 2 concurrents (et a un véhicule)
--    C13  une équipe association panache au moins 2 marques
--    C14  la marque du véhicule fait partie des marques de l'équipe
--    C15  toute étape / équipe a sa ligne dans la table de son sous-type
--
--  Les contraintes "au moins N lignes liées" ne peuvent être vérifiées
--  qu'une fois toutes les lignes insérées. On utilise donc des
--  CONSTRAINT TRIGGER ... DEFERRABLE INITIALLY DEFERRED : la vérification
--  a lieu au COMMIT. Il faut donc insérer un équipage, ses deux
--  concurrents et son véhicule dans la même transaction.
--
--  Non implémentées (documentées dans le rapport) : "tout rallye a au
--  moins une étape", "toute étape traverse au moins un pays", "toute
--  équipe a au moins un équipage", ainsi que C6 (l'heure d'arrivée
--  n'est pas stockée) et C16 (numérotation continue des étapes).
-- =====================================================================


-- ---------------------------------------------------------------------
--  Fonction utilitaire : nombre de participations d'un concurrent
--  à un rallye donné (toutes années confondues). Cf. requête 7.
--  Exemple : SELECT nb_participations(42, 'Paris-Dakar');
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION nb_participations(p_numConcurrent INTEGER,
                                             p_nomRallye     VARCHAR)
RETURNS INTEGER
LANGUAGE sql STABLE
AS $$
    SELECT count(*)::INTEGER
    FROM compose
    WHERE numConcurrent = p_numConcurrent
      AND nomRallye     = p_nomRallye;
$$;


-- =====================================================================
--  C12 : un équipage = exactement 2 concurrents et 1 véhicule (pilote)
-- =====================================================================
CREATE OR REPLACE FUNCTION verif_equipage(p_nomRallye VARCHAR,
                                          p_annee     INTEGER,
                                          p_num       INTEGER)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    nb INTEGER;
BEGIN
    -- L'équipage a pu être supprimé entre-temps : rien à vérifier.
    PERFORM 1 FROM equipage
     WHERE nomRallye = p_nomRallye AND annee = p_annee AND numEquipage = p_num;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT count(*) INTO nb FROM compose
     WHERE nomRallye = p_nomRallye AND annee = p_annee AND numEquipage = p_num;
    IF nb <> 2 THEN
        RAISE EXCEPTION 'C12 : l''équipage % du rallye % % compte % concurrent(s) au lieu de 2',
                        p_num, p_nomRallye, p_annee, nb;
    END IF;

    PERFORM 1 FROM pilote
     WHERE nomRallye = p_nomRallye AND annee = p_annee AND numEquipage = p_num;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'C12 : l''équipage % du rallye % % n''a pas de véhicule',
                        p_num, p_nomRallye, p_annee;
    END IF;
END;
$$;

-- Déclenché par une modification de compose ou de pilote
CREATE OR REPLACE FUNCTION trg_c12_lien()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        PERFORM verif_equipage(NEW.nomRallye, NEW.annee, NEW.numEquipage);
    END IF;
    IF TG_OP IN ('DELETE', 'UPDATE') THEN
        PERFORM verif_equipage(OLD.nomRallye, OLD.annee, OLD.numEquipage);
    END IF;
    RETURN NULL;
END;
$$;

-- Déclenché par la création d'un équipage
CREATE OR REPLACE FUNCTION trg_c12_equipage()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM verif_equipage(NEW.nomRallye, NEW.annee, NEW.numEquipage);
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER c12_equipage
    AFTER INSERT ON equipage
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION trg_c12_equipage();

CREATE CONSTRAINT TRIGGER c12_compose
    AFTER INSERT OR UPDATE OR DELETE ON compose
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION trg_c12_lien();

CREATE CONSTRAINT TRIGGER c12_pilote
    AFTER INSERT OR UPDATE OR DELETE ON pilote
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION trg_c12_lien();


-- =====================================================================
--  C13 : une équipe association panache au moins 2 marques
-- =====================================================================
CREATE OR REPLACE FUNCTION trg_c13_association()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_equipe VARCHAR;
    nb       INTEGER;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_equipe := OLD.nomEquipe;
    ELSE
        v_equipe := NEW.nomEquipe;
    END IF;

    PERFORM 1 FROM association WHERE nomEquipe = v_equipe;
    IF NOT FOUND THEN
        RETURN NULL;                      -- association supprimée
    END IF;

    SELECT count(*) INTO nb FROM panache WHERE nomEquipe = v_equipe;
    IF nb < 2 THEN
        RAISE EXCEPTION 'C13 : l''association % ne panache que % marque(s)',
                        v_equipe, nb;
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER c13_association
    AFTER INSERT ON association
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION trg_c13_association();

CREATE CONSTRAINT TRIGGER c13_panache
    AFTER UPDATE OR DELETE ON panache
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION trg_c13_association();


-- =====================================================================
--  C14 : la marque du véhicule d'un équipage fait partie des marques
--  de son équipe (marque de l'équipe officielle, ou l'une des marques
--  panachées de l'association). Vérifiée immédiatement : l'équipe et
--  ses marques doivent donc exister avant l'affectation du véhicule.
-- =====================================================================
CREATE OR REPLACE FUNCTION trg_c14_marque()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_equipe VARCHAR;
    v_marque VARCHAR;
BEGIN
    SELECT nomEquipe INTO v_equipe FROM equipage
     WHERE nomRallye = NEW.nomRallye AND annee = NEW.annee
       AND numEquipage = NEW.numEquipage;

    SELECT nomMarque INTO v_marque FROM vehicule
     WHERE numeroSerie = NEW.numeroSerie;

    IF NOT EXISTS (SELECT 1 FROM officielle
                    WHERE nomEquipe = v_equipe AND nomMarque = v_marque)
       AND NOT EXISTS (SELECT 1 FROM panache
                        WHERE nomEquipe = v_equipe AND nomMarque = v_marque)
    THEN
        RAISE EXCEPTION 'C14 : le véhicule % (%) ne correspond à aucune marque de l''équipe %',
                        NEW.numeroSerie, v_marque, v_equipe;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER c14_pilote
    BEFORE INSERT OR UPDATE ON pilote
    FOR EACH ROW EXECUTE FUNCTION trg_c14_marque();


-- =====================================================================
--  C15 (totalité) : toute étape a sa ligne dans speciale ou liaison,
--  toute équipe a sa ligne dans officielle ou association.
--  L'exclusivité est déjà garantie par les clés étrangères sur
--  (…, typeEtape) et (nomEquipe, typeEquipe) : voir 01_tables.sql.
-- =====================================================================
CREATE OR REPLACE FUNCTION trg_c15_etape()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- L'étape a pu être supprimée avant le COMMIT
    PERFORM 1 FROM etape
     WHERE nomRallye = NEW.nomRallye AND annee = NEW.annee AND numEtape = NEW.numEtape;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM speciale
                    WHERE nomRallye = NEW.nomRallye AND annee = NEW.annee
                      AND numEtape = NEW.numEtape)
       AND NOT EXISTS (SELECT 1 FROM liaison
                        WHERE nomRallye = NEW.nomRallye AND annee = NEW.annee
                          AND numEtape = NEW.numEtape)
    THEN
        RAISE EXCEPTION 'C15 : l''étape % du rallye % % (%) n''a pas de ligne dans sa table de sous-type',
                        NEW.numEtape, NEW.nomRallye, NEW.annee, NEW.typeEtape;
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER c15_etape
    AFTER INSERT OR UPDATE ON etape
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION trg_c15_etape();

CREATE OR REPLACE FUNCTION trg_c15_equipe()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM 1 FROM equipe WHERE nomEquipe = NEW.nomEquipe;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM officielle  WHERE nomEquipe = NEW.nomEquipe)
       AND NOT EXISTS (SELECT 1 FROM association WHERE nomEquipe = NEW.nomEquipe)
    THEN
        RAISE EXCEPTION 'C15 : l''équipe % (%) n''a pas de ligne dans sa table de sous-type',
                        NEW.nomEquipe, NEW.typeEquipe;
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER c15_equipe
    AFTER INSERT OR UPDATE ON equipe
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION trg_c15_equipe();
