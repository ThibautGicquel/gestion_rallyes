# Gestion des rallyes sportifs — manuel d'installation

Base de données PostgreSQL de gestion de rallyes (automobiles, camions, motos), alimentée par un notebook Python, le tout lancé avec Docker Compose.

## Prérequis

- **Docker Desktop**, installé et démarré (*Engine running*).
- Pour travailler sur le notebook en dehors de Docker (facultatif) : Python 3.11 ou plus récent et VS Code avec les extensions Python et Jupyter.

## Contenu du projet

```
Projet/
├── docker-compose.yml       services : base (db) et initialisation (loader)
├── .env                     identifiants de la base et port
├── requirements.txt         dépendances Python
├── sql/
│   ├── 00_init.sql          exécute 01 à 04 dans l'ordre
│   ├── 01_tables.sql        tables et contraintes
│   ├── 02_index.sql         index
│   ├── 03_vues.sql          vues
│   ├── 04_fonctions_triggers.sql   fonctions et triggers
│   ├── 05_requetes.sql      les 7 requêtes du sujet
│   └── 06_donnees_test.sql  petit jeu de test (facultatif)
├── notebooks/
│   ├── alimentation.ipynb   création + génération des données + requêtes + mesures
│   └── execution/           copie exécutée du notebook (créée au premier lancement)
├── loader/
│   ├── Dockerfile           image Python du service loader
│   └── charger.py           exécute le notebook si la base est vide
└── dump/                    sauvegardes de la base
```

## Premier lancement

Toutes les commandes se tapent dans un terminal (PowerShell sous Windows), **depuis le dossier du projet**.

```powershell
docker compose up -d
```

Au premier lancement, Docker télécharge les images (quelques minutes), démarre PostgreSQL, puis le service `loader` crée les tables et alimente la base (environ 15 secondes) avant de s'arrêter.

Pour suivre l'initialisation :

```powershell
docker compose logs -f loader
```

L'initialisation est terminée quand s'affiche `Base alimentée.` (`Ctrl+C` pour quitter l'affichage des logs, les services continuent de tourner).

Aux lancements suivants, le `loader` voit que la base contient déjà des données et ne fait rien : les modifications faites entre-temps sont conservées.

## Vérifier que tout fonctionne

```powershell
docker compose ps -a
docker compose exec db psql -U rallye -d rallyes -f /scripts/05_requetes.sql
```

- `rallye-db` doit être `running (healthy)` et `rallye-loader` `exited (0)`.
- La seconde commande affiche le résultat des 7 requêtes du sujet.

Le notebook exécuté, avec tous ses résultats (volumes, requêtes, mesures des index), se trouve dans `notebooks/execution/alimentation_execute.ipynb`.

## Se connecter à la base

| Paramètre | Valeur |
|---|---|
| Hôte | `localhost` (ou `127.0.0.1`) |
| Port | `5432` (valeur de `DB_PORT` dans `.env`) |
| Base | `rallyes` |
| Utilisateur | `rallye` |
| Mot de passe | `rallye` |

Ces paramètres valent pour VS Code (extension PostgreSQL), DBeaver, pgAdmin ou tout autre client.

Console SQL directement dans le conteneur :

```powershell
docker compose exec db psql -U rallye -d rallyes
```

## Commandes courantes

| Action | Commande |
|---|---|
| Démarrer | `docker compose up -d` |
| Arrêter (les données sont conservées) | `docker compose stop` |
| Voir l'état des services | `docker compose ps -a` |
| Recréer et réalimenter la base | `docker compose run --rm -e FORCE_RELOAD=1 loader` |
| Tout supprimer, données comprises | `docker compose down -v` |

## Sauvegarde et restauration (dump)

Sauvegarde dans `dump/rallyes.sql` :

```powershell
docker compose exec db pg_dump -U rallye -d rallyes --clean --if-exists --no-owner -f /dump/rallyes.sql
```

Restauration à partir de `dump/rallyes.sql` (remplace le contenu actuel de la base) :

```powershell
docker compose up -d db
docker compose exec db psql -U rallye -d rallyes -v ON_ERROR_STOP=1 -f /dump/rallyes.sql
```

## Exécuter le notebook à la main (facultatif)

1. Démarrer la base : `docker compose up -d db`.
2. Créer un environnement Python et installer les dépendances :
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Ouvrir `notebooks/alimentation.ipynb` dans VS Code, choisir le kernel `.venv` (**Select Kernel**), puis **Run All**.

Le notebook recrée entièrement la base à chaque exécution. Les données générées sont toujours les mêmes (graine fixe).

## Dépannage

- **`container name "/rallye-db" is already in use`** : un ancien conteneur créé avec `docker run` porte le même nom. Le supprimer : `docker rm -f rallye-db`, puis relancer `docker compose up -d`.
- **`port is already allocated`** : le port 5432 est déjà utilisé (autre PostgreSQL installé sur la machine). Mettre `DB_PORT=5433` dans `.env`, relancer, et utiliser le port 5433 pour se connecter.
- **Le loader échoue** : afficher l'erreur avec `docker compose logs loader`. La base n'est modifiée que si l'alimentation va jusqu'au bout (une seule transaction).
