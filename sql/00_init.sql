-- =====================================================================
--  Gestion des rallyes sportifs - création complète de la base
-- ---------------------------------------------------------------------
--  Exécute les scripts dans l'ordre. Avec docker compose (voir README.md) :
--      docker compose exec db psql -U rallye -d rallyes -v ON_ERROR_STOP=1 -f /scripts/00_init.sql
--  Normalement inutile : le service loader (notebook) crée la base.
--  Rejouable : 01_tables.sql supprime et recrée toutes les tables.
-- =====================================================================
\ir 01_tables.sql
\ir 02_index.sql
\ir 03_vues.sql
\ir 04_fonctions_triggers.sql
