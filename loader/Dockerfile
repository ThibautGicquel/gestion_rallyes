# Image du service "loader" : Python + bibliothèques du projet.
# Construite depuis la racine du projet (voir docker-compose.yml).
FROM python:3.12-slim

# Affiche les messages Python immédiatement dans les logs Docker,
# et n'encombre pas l'image avec le cache de pip.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /projet

# Dépendances du projet + nbconvert, qui exécute le notebook sans interface
COPY requirements.txt .
RUN pip install -r requirements.txt nbconvert

COPY loader/charger.py .

CMD ["python", "charger.py"]
