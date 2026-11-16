-- Fonctions et triggers (C12 à C15)
-- C12, C13 et C15 sont vérifiées au COMMIT (triggers différés)


-- Nombre de participations d'un concurrent à un rallye
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


-- C12 : 2 concurrents et 1 véhicule par équipage
CREATE OR REPLACE FUNCTION verif_equipage(p_nomRallye VARCHAR,
                                          p_annee     INTEGER,
                                          p_num       INTEGER)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    nb INTEGER;
BEGIN
    -- équipage supprimé
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


-- C13 : au moins 2 marques par association
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


-- C14 : la marque du véhicule est une marque de l'équipe
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


-- C15 : toute étape / équipe a sa ligne de sous-type
CREATE OR REPLACE FUNCTION trg_c15_etape()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- étape supprimée
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
