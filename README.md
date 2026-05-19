# Système d'alerte précoce du paludisme — Extrême-Nord Cameroun

Application Django de surveillance et de prévision épidémique du paludisme, développée pour le **Groupe Technique Régional (GTR) de lutte contre le paludisme de l'Extrême-Nord**, sous tutelle du **Ministère de la Santé Publique du Cameroun (MINSANTE)**.

## Fonctionnalités

- **Tableau de bord** : KPI régionaux, carte choroplèthe d'incidence, séries temporelles climat-incidence, corrélations croisées (CCF).
- **Prévisions** : modèles Random Forest et XGBoost validés en walk-forward, prévisions récursives à 1, 2 et 3 mois, avec analyse IA automatique et génération de rapports Word.
- **Carte d'alerte épidémique** : 3 niveaux (vert / orange / rouge) basés sur les seuils OMS P75 / P90, filtrable par algorithme et horizon, export PDF.
- **Mise à jour des données** : import Excel mensuel + récupération automatique des données climatiques via l'API NASA POWER, recalcul automatique des prévisions.
- **Gestion des rôles** : Administrateur (accès complet) et Chef de district (accès restreint à son district).

## Stack technique

| Couche | Technologie |
|---|---|
| Backend | Python 3.10+ — Django 4.2 (patron MVT) |
| Base de données | SQLite (dev) — PostgreSQL (prod) |
| ML | Random Forest + XGBoost (joblib) |
| Frontend | Chart.js, Leaflet.js, HTML5/CSS3 |
| IA générative | Google Gemini API (tier gratuit) |
| Climat | API NASA POWER (sans clé, gratuit) |
| Auth | Django auth + bcrypt |

## Installation

### 1. Prérequis

- Python **3.10 à 3.12** recommandé (compatibilité avec les modèles `.pkl` du notebook)
- Git

### 2. Cloner et installer

```bash
git clone <repo>
cd malaria_alert_system

# Environnement virtuel
python -m venv venv
source venv/bin/activate          # Linux/Mac
venv\Scripts\activate             # Windows

# Dépendances
pip install -r requirements.txt
```

### 3. Configuration

```bash
cp .env.example .env
# Éditer .env et renseigner SECRET_KEY et GEMINI_API_KEY
```

Obtenir une clé Gemini gratuite : <https://aistudio.google.com/app/apikey>

### 4. Placer les artefacts du modèle

Copier le dossier `outputs/` issu du notebook `modelisation_paludisme_final.ipynb` à la racine du projet. Il doit contenir au minimum :

```
outputs/
├── models/
│   ├── random_forest_final.pkl
│   ├── xgboost_final.pkl
│   ├── artefacts.pkl
│   └── climatologie_district_mois.csv
├── seuils_alerte.csv
└── (autres fichiers de métriques)
```

### 5. Initialiser la base

```bash
python manage.py migrate
python manage.py seed_districts          # 32 districts + coordonnées + géométrie
python manage.py load_initial_data       # Charge DATA_COMP_2025_epuree.xlsx
python manage.py load_model_artifacts    # Charge seuils + performances
python manage.py createsuperuser
```

### 6. Lancer

```bash
python manage.py runserver
```

Application disponible sur <http://127.0.0.1:8000/>

## Structure du projet

```
malaria_alert_system/
├── config/             # Settings Django (base / development / production)
├── apps/
│   ├── accounts/       # Utilisateurs, rôles, authentification
│   ├── core/           # Modèles District, Observation, Meteo, Prevision, SeuilAlerte
│   ├── accueil/        # Page d'accueil publique
│   ├── dashboard/      # Tableau de bord (KPI, carte, séries temporelles)
│   ├── predictions/    # Prévisions ML + IA d'analyse + rapports
│   ├── alerts/         # Carte d'alerte épidémique
│   ├── data_management/# Import Excel + NASA POWER
│   └── about/          # Page À propos
├── ml_models/          # Fichiers .pkl chargés au démarrage
├── static/             # CSS, JS, images, GeoJSON
├── templates/          # Templates HTML (héritent de base.html)
└── media/              # Uploads et rapports générés
```

## Maître d'ouvrage

**Délégation Régionale de la Santé Publique de l'Extrême-Nord** — Ministère de la Santé Publique du Cameroun.

## Maître d'œuvre

**Équipe Suivi-Évaluation du Groupe Technique Régional Paludisme** (GTR Paludisme Extrême-Nord).

## Licence

Usage réservé au MINSANTE et à ses partenaires institutionnels.
