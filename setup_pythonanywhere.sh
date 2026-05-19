#!/usr/bin/env bash
# ============================================================
# Script d'initialisation tout-en-un pour PythonAnywhere
#
# À exécuter UNE SEULE FOIS, après git clone et activation du virtualenv.
#
# Usage :
#   cd ~/malaria-alert-extreme-nord
#   workon malaria-env
#   bash setup_pythonanywhere.sh
# ============================================================

set -e

echo ""
echo "========================================================"
echo "  Initialisation - Plateforme d'alerte paludisme"
echo "========================================================"
echo ""

# Vérification du virtualenv
if [ -z "$VIRTUAL_ENV" ]; then
    echo "ERREUR : aucun virtualenv actif. Lancez 'workon malaria-env' d'abord."
    exit 1
fi

# Vérification du .env
if [ ! -f .env ]; then
    echo "ERREUR : fichier .env manquant. Créez-le d'abord (voir DEPLOIEMENT.md étape 4)."
    exit 1
fi

echo "[1/8] Installation des dépendances Python..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "       OK"

echo "[2/8] Application des migrations Django..."
python manage.py migrate --noinput
echo "       OK"

echo "[3/8] Chargement des 32 districts sanitaires..."
python manage.py seed_districts
echo "       OK"

echo "[4/8] Chargement des observations historiques (2017-2025)..."
python manage.py load_initial_data
echo "       OK"

echo "[5/8] Calcul des seuils d'alerte P75/P90 (384 entrées)..."
python manage.py compute_seuils
echo "       OK"

echo "[6/8] Chargement des performances ML officielles..."
python manage.py load_performances_officielles
echo "       OK"

echo "[7/8] Création des comptes (admin + 32 chefs de district)..."
python manage.py seed_chefs_districts
echo "       OK"

echo "[8/8] Collecte des fichiers statiques (CSS, JS, images)..."
python manage.py collectstatic --noinput --clear
echo "       OK"

echo ""
echo "========================================================"
echo "  Initialisation terminée avec succès !"
echo "========================================================"
echo ""
echo "Identifiants de connexion :"
echo "  - Admin     : admin_gtr     / admin@2026"
echo "  - Chefs     : voir comptes_chefs_districts.csv"
echo ""
echo "Prochaine étape : configurer l'application web dans PythonAnywhere"
echo "  (onglet Web -> WSGI + Static files), puis cliquer 'Reload'."
echo ""
