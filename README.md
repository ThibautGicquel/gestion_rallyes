# Gestion des rallyes sportifs — manuel d'installation et d'usage

Base de données PostgreSQL de gestion de rallyes (automobiles, camions, motos), alimentée par un notebook Python, avec une application web de consultation et de saisie. Le tout se lance avec Docker Compose.

## Prérequis

- **Docker Desktop**, installé et démarré (*Engine running*).
- Pour travailler sur le notebook en dehors de Docker (facultatif) : Python 3.11 ou plus récent et VS Code avec les extensions Python et Jupyter.

## Contenu du projet

```
Projet/
├── docker-compose.yml       services : base (db), initialisation (loader), application (app)
├── .env.example             modèle du fichier .env (identifiants de la base, ports)
├── requirements.txt         dépendances Python du notebook
├── sql/
│   ├── 00_init.sql          exécute 01 à 04 puis 07 dans l'ordre
│   ├── 01_tables.sql        tables et contraintes
│   ├── 02_index.sql         index
│   ├── 03_vues.sql          vues
│   ├── 04_fonctions_triggers.sql   fonctions et triggers
│   ├── 05_requetes.sql      les 7 requêtes du sujet
│   ├── 06_donnees_test.sql  petit jeu de test (facultatif)
│   └── 07_roles.sql         rôles PostgreSQL des profils et table des comptes
├── notebooks/
│   ├── alimentation.ipynb   création + génération des données + requêtes + mesures
│   └── execution/           copie exécutée du notebook (créée au premier lancement)
├── loader/
│   ├── Dockerfile           image Python du service loader
│   └── charger.py           exécute le notebook si la base est vide
├── app/                     application web (Flask, SQLAlchemy, Bootstrap)
│   ├── Dockerfile           image du service app (gunicorn, port 8000)
│   ├── requirements.txt     dépendances de l'application
│   └── rallyes/
│       ├── modeles.py       mapping SQLAlchemy des tables et des vues
│       ├── droits.py        profils et rôles PostgreSQL
│       ├── auth.py          connexion, comptes de démonstration
│       ├── consultation.py  rallyes, étapes, équipages, classements
│       ├── annuaire.py      concurrents, équipes, marques, véhicules, pays
│       ├── requetes.py      les 7 requêtes du sujet avec paramètres
│       ├── organisation.py  saisie : rallyes et étapes
│       ├── saisie.py        saisie : équipages et résultats
│       ├── admin.py         administration : référentiels, équipes, comptes
│       ├── outils.py        tri, pagination, formats, messages d'erreur
│       ├── templates/       pages HTML (Jinja)
│       └── static/          feuille de style
└── dump/                    sauvegardes de la base
```

## Premier lancement

Toutes les commandes se tapent dans un terminal (PowerShell sous Windows), **depuis le dossier du projet**.

Créer d'abord le fichier `.env`, qui contient les identifiants de la base, à partir du modèle fourni (une seule fois) :

```powershell
Copy-Item .env.example .env
```

Puis lancer le projet :

```powershell
docker compose up -d
```

Au premier lancement, Docker télécharge et construit les images (quelques minutes), démarre PostgreSQL, puis le service `loader` crée les tables et alimente la base (environ 15 secondes) avant de s'arrêter. L'application démarre ensuite.

Pour suivre l'initialisation :

```powershell
docker compose logs -f loader
```

L'initialisation est terminée quand s'affiche `Base alimentée.` (`Ctrl+C` pour quitter l'affichage des logs, les services continuent de tourner).

L'application est alors accessible sur **<http://localhost:8000>**.

Aux lancements suivants, le `loader` voit que la base contient déjà des données et ne fait rien : les modifications faites entre-temps, notamment depuis l'application, sont conservées.

## Vérifier que tout fonctionne

```powershell
docker compose ps -a
docker compose exec db psql -U rallye -d rallyes -f /scripts/05_requetes.sql
```

- `rallye-db` doit être `running (healthy)`, `rallye-loader` `exited (0)` et `rallye-app` `running`.
- La seconde commande affiche le résultat des 7 requêtes du sujet.

Le notebook exécuté, avec tous ses résultats (volumes, requêtes, mesures des index), se trouve dans `notebooks/execution/alimentation_execute.ipynb`.

## Application web

### Comptes et profils

La consultation est libre : un visiteur n'a pas besoin de compte. La saisie demande de se connecter (bouton **Connexion** en haut à droite).

Deux comptes de démonstration sont créés au démarrage de l'application s'ils n'existent pas :

| Identifiant | Mot de passe | Profil |
|---|---|---|
| `admin` | `admin` | administrateur |
| `organisateur` | `organisateur` | organisateur |

Chaque profil correspond à un rôle PostgreSQL (`sql/07_roles.sql`). L'application prend ce rôle au début de chaque transaction (`SET LOCAL ROLE`) : même en cas d'erreur dans l'application, PostgreSQL refuse ce que le profil n'a pas le droit de faire.

| Profil | Rôle PostgreSQL | Droits |
|---|---|---|
| Visiteur (sans compte) | `rallye_lecture` | lecture de toutes les tables et vues, sauf les comptes |
| Organisateur | `rallye_saisie` | lecture, plus écriture des rallyes, étapes, équipages et résultats |
| Administrateur | `rallye_admin` | tout, y compris les référentiels (pays, marques, sponsors, fournisseurs, concurrents, véhicules, équipes) et les comptes |

Les mots de passe sont stockés hachés (scrypt) dans la table `utilisateur`. Cette table n'est pas supprimée par `01_tables.sql` : les comptes survivent à un rechargement de la base.

### Consultation (tous les profils)

Le menu donne accès à :

- **Rallyes** : liste filtrable par nom et par année. La fiche d'une édition présente :
  - ses étapes et les pays traversés ;
  - ses équipages, filtrables par catégorie ;
  - le classement général par catégorie, avec le temps cumulé et l'écart au premier ;
  - ses sponsors et fournisseurs.
- **Fiche d'une étape** : tranche horaire pour une spéciale, classement de l'étape (général ou par catégorie, écart au meilleur temps, disqualifiés à la fin).
- **Fiche d'un équipage** : concurrents, équipe, véhicule, résultats étape par étape avec le temps cumulé, et résultat final (classé, disqualifié ou abandon).
- **Concurrents** : recherche par nom, prénom ou numéro, filtre par nationalité. La fiche donne l'historique des participations et leur nombre par rallye.
- **Équipes** : filtre par type (officielle ou association) et par marque. La fiche donne les marques, les sponsors et les équipages engagés.
- **Marques** : véhicules par catégorie, équipes officielles et associations ; fiche de chaque véhicule.
- **Pays** : étapes qui traversent chaque pays (requêtes 2 et 3 du sujet) et concurrents de cette nationalité.
- **Requêtes du sujet** : les 7 requêtes de `sql/05_requetes.sql`. Pour chacune :
  - les valeurs de l'énoncé sont préremplies et peuvent être changées (rallye, année, catégorie, pays, marque, nombre d'années) ;
  - la requête SQL exécutée est affichée ;
  - le résultat peut être exporté en CSV ;
  - le bouton **Plan d'exécution** affiche le résultat d'`EXPLAIN ANALYZE`.

Les listes se trient en cliquant sur les en-têtes de colonnes. Les noms (rallye, étape, équipage, concurrent, équipe, marque, pays) sont des liens vers la fiche correspondante.

### Saisie (organisateur et administrateur)

Les boutons de saisie apparaissent dans les pages de consultation une fois connecté.

- **Créer un rallye** : *Rallyes* → **Nouveau rallye** (nom, année, sponsors, fournisseurs). Sur la fiche d'un rallye, **Sponsors et fournisseurs** modifie ses partenaires. Le nom et l'année ne sont pas modifiables : ils forment la clé primaire.
- **Ajouter une étape** : sur la fiche du rallye, **Ajouter une étape**.
  - Le numéro est attribué à la suite des étapes existantes (numérotation continue).
  - Une **spéciale** demande une tranche horaire (début et fin, en UTC) ; une **liaison** n'en a pas.
  - Une étape traverse au moins un pays.
  - Le type d'une étape peut être changé ensuite (**Modifier** sur la fiche de l'étape).
- **Inscrire un équipage** : onglet *Équipages* du rallye → **Inscrire un équipage**.
  - Choisir l'équipe, puis les deux concurrents : taper au moins deux lettres du nom ou le numéro, et choisir dans les suggestions.
  - Choisir ensuite le véhicule et le numéro attribué par l'organisation.
  - Seuls sont proposés les concurrents qui ne courent pas déjà ce rallye, et les véhicules des marques de l'équipe qui ne sont pas encore engagés.
  - L'équipage, ses deux concurrents et son véhicule sont enregistrés ensemble, dans une seule transaction.
- **Saisir les résultats** : sur la fiche d'une étape, **Saisir les résultats**.
  - Pour chaque équipage : la durée au format `h:mm:ss` et, si besoin, la case *Disqualifié*.
  - Une durée vide avec la case décochée correspond à un abandon : un éventuel résultat existant est supprimé.
  - Pour une spéciale, une durée supérieure à la tranche horaire disqualifie automatiquement l'équipage.
  - Si une durée est invalide, rien n'est enregistré.
- **Supprimer** :
  - un équipage (**Désinscrire**, sur sa fiche), avec ses résultats ;
  - la dernière étape d'un rallye, avec ses résultats ;
  - un rallye qui n'a plus d'équipage inscrit, avec ses étapes.

### Administration (administrateur)

Le menu **Administration** permet de gérer :

- **Pays, marques, sponsors, fournisseurs** : ajout et suppression. Une valeur utilisée ailleurs (par exemple le pays d'un concurrent) ne peut pas être supprimée ; le nombre d'utilisations est affiché.
- **Concurrents** : création (numéro attribué automatiquement), modification, suppression s'ils n'ont jamais couru.
- **Véhicules** (depuis la fiche d'une marque) : création, modification de la cylindrée, suppression s'ils n'ont jamais couru. La marque et la catégorie d'un véhicule qui a déjà couru ne sont plus modifiables.
- **Équipes** :
  - création d'une équipe officielle (une marque) ou d'une association (au moins deux marques), avec budget et sponsors ;
  - modification du budget, des sponsors et des marques, sans retirer une marque sur laquelle ses équipages ont déjà couru ;
  - suppression si l'équipe n'a engagé aucun équipage.
- **Comptes** : création, changement de profil, nouveau mot de passe, suppression. Un administrateur ne peut ni supprimer son propre compte ni retirer ses propres droits.

Si la base refuse une opération (contrainte, trigger, droit insuffisant), la transaction est annulée et le message s'affiche en haut de la page.

### Paramètres de l'application

Variables à décommenter dans `.env`, toutes facultatives :

| Variable | Rôle | Valeur par défaut |
|---|---|---|
| `APP_PORT` | port de l'application sur la machine | `8000` |
| `SECRET_KEY` | clé de signature des sessions, à changer en dehors d'un usage local | `change-moi` |
| `COMPTES_DEMO` | `0` pour ne pas créer les comptes de démonstration | `1` |

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
| Reconstruire l'application après une modification de son code | `docker compose up -d --build app` |
| Afficher les messages de l'application | `docker compose logs -f app` |
| Recréer et réalimenter la base (les ajouts faits depuis l'application sont perdus, les comptes conservés) | `docker compose run --rm -e FORCE_RELOAD=1 loader` |
| Tout supprimer, données comprises | `docker compose down -v` |

## Sauvegarde et restauration (dump)

Sauvegarde dans `dump/rallyes.sql` :

```powershell
docker compose exec db pg_dump -U rallye -d rallyes --clean --if-exists --no-owner -f /dump/rallyes.sql
```

Restauration à partir de `dump/rallyes.sql` (remplace le contenu actuel de la base) :

```powershell
docker compose up -d
docker compose exec db psql -U rallye -d rallyes -v ON_ERROR_STOP=1 -f /dump/rallyes.sql
```

Sur une nouvelle installation, attendre la fin de l'initialisation (`Base alimentée.` dans `docker compose logs -f loader`) avant de restaurer. Le dump contient les données, les comptes et les droits accordés aux rôles de l'application, mais pas les rôles eux-mêmes : ils appartiennent au serveur PostgreSQL, pas à la base, et c'est l'initialisation (`sql/07_roles.sql`) qui les crée.

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
- **`The "POSTGRES_USER" variable is not set`** ou **`Database is uninitialized and superuser password is not specified`** : le fichier `.env` manque. Le créer avec `Copy-Item .env.example .env`, puis relancer `docker compose up -d`.
- **`port is already allocated`** : le port 5432 (base) ou 8000 (application) est déjà utilisé. Mettre `DB_PORT=5433` ou `APP_PORT=8001` dans `.env`, relancer, et utiliser le nouveau port.
- **Le loader échoue** : afficher l'erreur avec `docker compose logs loader`. La base n'est modifiée que si l'alimentation va jusqu'au bout (une seule transaction).
- **L'application ne répond pas ou affiche une erreur** : afficher ses messages avec `docker compose logs app`.
- **Impossible de se connecter avec les comptes de démonstration, ou « permission denied » dans l'application** : la base a été créée sans `sql/07_roles.sql` (par exemple avant l'ajout de l'application). L'appliquer, puis redémarrer l'application :

  ```powershell
  docker compose exec db psql -U rallye -d rallyes -v ON_ERROR_STOP=1 -f /scripts/07_roles.sql
  docker compose restart app
  ```
