#!/usr/bin/env bash
# ============================================================
# Script de build Render
# Exécuté à chaque déploiement via render.yaml
# ============================================================
set -o errexit   # arrêt immédiat sur erreur

echo "==> [1/6] Installation des dépendances Python..."
pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt
pip cache purge 2>/dev/null || true

echo "==> [2/6] Collecte des fichiers statiques..."
python manage.py collectstatic --noinput --clear

echo "==> [3/6] Application des migrations..."
python manage.py migrate --noinput

echo "==> [4/6] Initialisation des données de référence (idempotent)..."
python manage.py seed_districts || echo "Districts déjà chargés"
python manage.py load_initial_data || echo "Données déjà chargées"

echo "==> [5/6] Calcul des seuils + performances officielles..."
python manage.py compute_seuils || echo "Seuils déjà calculés"
python manage.py load_performances_officielles || echo "Performances déjà chargées"

echo "==> [6/7] Création des comptes (admin + 32 chefs de district)..."
python manage.py seed_chefs_districts || echo "Comptes déjà créés"

echo "==> [7/7] Génération des prévisions initiales (192 entrées)..."
python manage.py generate_predictions || echo "Prévisions non générées (vérifier les modèles ML)"

echo ""
echo "============================================================"
echo "  BUILD TERMINÉ AVEC SUCCÈS"
echo "============================================================"
echo "  - URL : https://<nom-de-l-app>.onrender.com"
echo "  - Admin     : admin_gtr / admin@2026"
echo "  - Chefs     : voir comptes_chefs_districts.csv"
echo "============================================================"
