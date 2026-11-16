"""Exécute le notebook d'alimentation si la base est vide (ou FORCE_RELOAD=1)."""
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
    # paramètres lus dans les variables PG*
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
