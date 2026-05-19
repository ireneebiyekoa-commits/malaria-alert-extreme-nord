#!/usr/bin/env bash
# ============================================================
# Script de build Render
# Exécuté à chaque déploiement
# ============================================================
set -o errexit   # arrêt immédiat sur erreur

echo "==> [1/5] Installation des dépendances Python..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> [2/5] Collecte des fichiers statiques..."
python manage.py collectstatic --noinput --clear

echo "==> [3/5] Application des migrations..."
python manage.py migrate --noinput

echo "==> [4/5] Initialisation des données (si nécessaire)..."
# Ces commandes sont idempotentes : elles ne dupliquent pas les données
python manage.py seed_districts || echo "Districts déjà chargés"
python manage.py load_initial_data || echo "Données déjà chargées"
python manage.py compute_seuils || echo "Seuils déjà calculés"
python manage.py seed_chefs_districts || echo "Comptes déjà créés"

echo "==> [5/5] Chargement des artefacts ML personnalisés (si CSV fournis)..."
python manage.py load_model_artifacts || echo "Pas de CSV externe — valeurs par défaut"

echo "==> Build terminé avec succès."
