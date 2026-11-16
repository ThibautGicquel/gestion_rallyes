"""
Service "loader" : initialise la base de données au démarrage du projet.

- Attend que PostgreSQL accepte les connexions.
- Si la base contient déjà des données, ne fait rien : les données
  modifiées depuis l'application sont ainsi conservées d'un démarrage
  à l'autre.
- Sinon (premier démarrage, ou FORCE_RELOAD=1), exécute le notebook
  d'alimentation, qui recrée les tables, les remplit et lance les
  requêtes du sujet. Une copie du notebook avec tous ses résultats est
  enregistrée dans notebooks/execution/.

Les chemins sont ceux du conteneur (voir docker-compose.yml) ; ils
peuvent être changés par variables d'environnement.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import psycopg

NOTEBOOK = Path(os.environ.get("NOTEBOOK", "/projet/notebooks/alimentation.ipynb"))
SORTIE = Path(os.environ.get("OUT_DIR", "/projet/notebooks/execution"))
FORCER = os.environ.get("FORCE_RELOAD", "0") == "1"


def connexion():
    # Les paramètres viennent des variables PGHOST, PGPORT, PGDATABASE,
    # PGUSER et PGPASSWORD, lues automatiquement par psycopg.
    return psycopg.connect("")


def attendre_postgres(essais=30, pause=2):
    for _ in range(essais):
        try:
            with connexion():
                return
        except psycopg.OperationalError:
            print("En attente de PostgreSQL...", flush=True)
            time.sleep(pause)
    sys.exit("PostgreSQL ne répond pas : abandon.")


def base_deja_alimentee():
    with connexion() as conn:
        existe = conn.execute("SELECT to_regclass('public.resultat') IS NOT NULL").fetchone()[0]
        if not existe:
            return False
        return conn.execute("SELECT EXISTS (SELECT 1 FROM resultat)").fetchone()[0]


def main():
    attendre_postgres()

    if base_deja_alimentee() and not FORCER:
        print("La base contient déjà des données : rien à faire.")
        print("Pour tout recréer : docker compose run --rm -e FORCE_RELOAD=1 loader")
        return

    print(f"Exécution de {NOTEBOOK.name} (création des tables et alimentation)...", flush=True)
    SORTIE.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "jupyter", "nbconvert",
            "--to", "notebook",
            "--execute",
            "--ExecutePreprocessor.timeout=1800",
            "--output-dir", str(SORTIE),
            "--output", "alimentation_execute",
            str(NOTEBOOK),
        ],
        check=True,
    )
    print(f"Base alimentée. Notebook exécuté : {SORTIE / 'alimentation_execute.ipynb'}")


if __name__ == "__main__":
    main()
