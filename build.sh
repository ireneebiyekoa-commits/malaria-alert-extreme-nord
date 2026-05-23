#!/usr/bin/env bash
# ============================================================
# Script de build Render
# Exécuté à chaque déploiement via render.yaml
# ============================================================
set -o errexit

echo "==> [1/7] Installation des dépendances Python..."
pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt
pip cache purge 2>/dev/null || true

echo "==> [2/7] Collecte des fichiers statiques..."
python manage.py collectstatic --noinput --clear

echo "==> [3/7] Application des migrations..."
python manage.py migrate --noinput

echo "==> [4/7] Initialisation des données de référence (idempotent)..."
python manage.py seed_districts || echo "Districts déjà chargés"
python manage.py load_initial_data || echo "Données déjà chargées"

echo "==> [5/7] Calcul des seuils d'alerte (M+σ et M+2σ, 384 entrées)..."
python manage.py compute_seuils || echo "Seuils déjà calculés"

echo "==> [6/7] Performances officielles + 33 comptes utilisateurs..."
python manage.py load_performances_officielles || echo "Performances déjà chargées"
python manage.py seed_chefs_districts || echo "Comptes déjà créés"

echo "==> [7/7] Génération des prévisions initiales (288 entrées : 32 dist × 3 algos × 3 horizons)..."
python manage.py generate_predictions || echo "Prévisions non générées (vérifier modèles ML)"

echo ""
echo "============================================================"
echo "  BUILD TERMINÉ AVEC SUCCÈS"
echo "============================================================"
echo "  Admin     : admin_gtr / admin@2026"
echo "  Chefs     : <nom_district>/ <nom_district>@2026"
echo "              ex. mokolo / mokolo@2026"
echo "============================================================"
