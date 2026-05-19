# Guide de déploiement gratuit et permanent — PythonAnywhere

**PythonAnywhere** est la meilleure option pour un déploiement **gratuit et définitif** de cette application. Contrairement à Render, l'application reste **toujours active** (pas de mise en veille), et la plateforme est totalement gratuite à vie pour un usage modéré.

## ✅ Pourquoi PythonAnywhere ?

| Critère | PythonAnywhere Free | Render Free |
|---|---|---|
| Prix | **Gratuit à vie** | Gratuit |
| Mise en veille | **Jamais** | Après 15 min d'inactivité |
| Domaine | `votrecompte.pythonanywhere.com` | `votre-app.onrender.com` |
| Base de données | SQLite (illimité disque) | SQLite ou Postgres (30 j) |
| HTTPS | Automatique | Automatique |
| Python 3.12 | ✅ | ✅ |
| API Gemini (Google) | ✅ Whitelisted | ✅ |

> ⚠️ Limites du free tier PythonAnywhere : 1 application web, 512 Mo de disque, CPU partagé (suffisant pour notre usage), domaine personnalisé non disponible (option payante).

## 📋 Prérequis

- Un compte **PythonAnywhere** (gratuit) : <https://www.pythonanywhere.com/registration/register/beginner/>
- Un compte **GitHub** (recommandé) ou possibilité d'uploader un ZIP

---

## 🚀 Procédure complète (≈ 20 minutes)

### Étape 1 — Pousser le code sur GitHub

```bash
cd "C:\Users\UltraBook 3.1\Desktop\MALARIA_APPLI\malaria_alert_system"

git init
git add .
git commit -m "Plateforme d'alerte précoce du paludisme - v1.0"

# Créer un repo sur https://github.com/new (privé recommandé)
git remote add origin https://github.com/VOTRE-COMPTE/malaria-alert-extreme-nord.git
git branch -M main
git push -u origin main
```

> Le fichier `.env` est ignoré par `.gitignore` (vos secrets restent locaux).

---

### Étape 2 — Créer un compte PythonAnywhere

1. Inscription **gratuite** : <https://www.pythonanywhere.com/registration/register/beginner/>
2. Choisir un nom d'utilisateur **professionnel** (ce sera votre URL publique).
   Exemple : `gtr-paludisme-extremenord` → URL : `gtr-paludisme-extremenord.pythonanywhere.com`
3. Confirmer l'email.

---

### Étape 3 — Cloner le code depuis GitHub

Sur le dashboard PythonAnywhere :

1. Cliquer sur l'onglet **Consoles** → **Bash**
2. Dans la console qui s'ouvre :

```bash
# Cloner le code (remplacer VOTRE-COMPTE)
git clone https://github.com/VOTRE-COMPTE/malaria-alert-extreme-nord.git

cd malaria-alert-extreme-nord

# Créer l'environnement virtuel (Python 3.12)
mkvirtualenv --python=python3.12 malaria-env

# Installer les dépendances (~ 3 minutes)
pip install -r requirements.txt
```

---

### Étape 4 — Créer le fichier `.env` de production

Dans la même console Bash :

```bash
# Générer une clé secrète Django solide
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Copier la chaîne obtenue, puis :

```bash
cat > .env << 'EOF'
SECRET_KEY=COLLER_LA_CLE_GENEREE_CI_DESSUS
DEBUG=False
ALLOWED_HOSTS=VOTRE-COMPTE.pythonanywhere.com
DJANGO_SETTINGS_MODULE=config.settings.production

# Désactiver la redirection HTTPS (PythonAnywhere la gère déjà)
SECURE_SSL_REDIRECT=False

GEMINI_API_KEY=AIzaSyDbDsnaI_oAtDIDDMZqT5v-feyNUDoNyVM
GEMINI_MODEL=gemini-2.5-flash
EOF

# Vérifier
cat .env
```

Remplacer `VOTRE-COMPTE` par votre nom d'utilisateur PythonAnywhere.

---

### Étape 5 — Initialiser la base de données

Toujours dans la console Bash :

```bash
# Activer l'env si besoin
workon malaria-env

# Migrations
python manage.py migrate

# Données initiales
python manage.py seed_districts
python manage.py load_initial_data
python manage.py compute_seuils
python manage.py load_performances_officielles
python manage.py seed_chefs_districts

# Fichiers statiques (CSS, JS, images)
python manage.py collectstatic --noinput
```

---

### Étape 6 — Configurer l'application web

1. Aller dans l'onglet **Web** → **Add a new web app**
2. Choisir **Manual configuration** (pas Django, car nous avons notre propre structure)
3. Sélectionner **Python 3.12**

Une fois créée, configurer ces sections :

#### 6.1 — Source code

| Champ | Valeur |
|---|---|
| **Source code** | `/home/VOTRE-COMPTE/malaria-alert-extreme-nord` |
| **Working directory** | `/home/VOTRE-COMPTE/malaria-alert-extreme-nord` |
| **Python version** | 3.12 |

#### 6.2 — Virtualenv

| Champ | Valeur |
|---|---|
| **Virtualenv** | `/home/VOTRE-COMPTE/.virtualenvs/malaria-env` |

#### 6.3 — Fichier WSGI

Cliquer sur le chemin du fichier WSGI proposé (ex. `/var/www/VOTRE-COMPTE_pythonanywhere_com_wsgi.py`) → **éditer entièrement** et coller :

```python
import os
import sys
from pathlib import Path

# Chemin du projet
PROJECT_DIR = '/home/VOTRE-COMPTE/malaria-alert-extreme-nord'
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Charger .env
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, '.env'))

# Settings de production
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

# Application WSGI Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

> Remplacer `VOTRE-COMPTE` partout par votre nom d'utilisateur.

#### 6.4 — Fichiers statiques (très important)

Dans l'onglet **Web** → section **Static files** → **Enter URL and Directory** :

| URL | Directory |
|---|---|
| `/static/` | `/home/VOTRE-COMPTE/malaria-alert-extreme-nord/staticfiles/` |
| `/media/` | `/home/VOTRE-COMPTE/malaria-alert-extreme-nord/media/` |

#### 6.5 — Installer python-dotenv

Dans la console Bash :

```bash
workon malaria-env
pip install python-dotenv
```

(Nécessaire pour que le WSGI charge le fichier `.env`)

---

### Étape 7 — Lancer l'application

Onglet **Web** → bouton vert **Reload** en haut.

L'application est disponible sur :

```
https://VOTRE-COMPTE.pythonanywhere.com
```

Premier accès : ~10 secondes (chargement des modèles ML en mémoire).
Accès suivants : instantanés.

---

### Étape 8 — Premier login

| Rôle | Identifiant | Mot de passe |
|---|---|---|
| Administrateur | `admin_gtr` | `admin@2026` |
| Chef Mokolo | `mokolo` | `mokolo@2026` |
| Chef Maroua 1 | `maroua_1` | `maroua_1@2026` |
| … (32 chefs) | voir `comptes_chefs_districts.csv` | … |

⚠️ **Important** : changez le mot de passe `admin_gtr` après le premier login (via l'admin Django à `/admin/`).

---

## 🔄 Mises à jour ultérieures

Pour mettre à jour l'application après un changement de code :

```bash
# 1. Pousser localement
git add .
git commit -m "Mise à jour : description"
git push

# 2. Sur PythonAnywhere (console Bash)
workon malaria-env
cd ~/malaria-alert-extreme-nord
git pull
pip install -r requirements.txt    # si nouvelles dépendances
python manage.py migrate            # si nouvelles migrations
python manage.py collectstatic --noinput

# 3. Recharger l'app web
# Onglet Web → bouton Reload
```

---

## 🛡️ Sécurité production — checklist

| ✅ | Action |
|---|---|
| ☐ | Changer le mot de passe `admin_gtr` |
| ☐ | Vérifier que `DEBUG=False` dans `.env` |
| ☐ | Vérifier que `.env` n'est PAS dans le dépôt git |
| ☐ | Activer la double authentification PythonAnywhere (Account → Security) |
| ☐ | Vérifier les logs régulièrement (onglet **Web** → **Error log**) |

---

## 📊 Surveillance et logs

- **Logs d'accès** : onglet **Web** → **Access log**
- **Logs d'erreur** : onglet **Web** → **Error log** (utile en cas de bug)
- **Logs du serveur** : onglet **Web** → **Server log**

---

## 🆘 Dépannage

### Erreur : "Something went wrong :-("
→ Consulter **Error log**. Souvent une variable d'env manquante ou un chemin WSGI incorrect.

### Modèles ML pas chargés
→ Vérifier que `outputs/models/` contient bien les `.pkl` :
```bash
ls -lh ~/malaria-alert-extreme-nord/outputs/models/
```

Si les `.pkl` font plus de 100 Mo (limite GitHub), utiliser **git LFS** ou les uploader via l'interface PythonAnywhere (onglet **Files**).

### CSS / JS non chargés
→ Vérifier la configuration **Static files** (étape 6.4) puis :
```bash
python manage.py collectstatic --noinput --clear
```
Puis **Reload** l'app web.

### Quota Gemini dépassé (HTTP 429)
→ `gemini-2.5-flash` : 20 req/jour gratuit. Passer à `gemini-1.5-flash` (1 500 req/jour) en éditant `.env` :
```
GEMINI_MODEL=gemini-1.5-flash
```

---

## 💡 Optimisation pour le free tier

Si vous atteignez la limite de 512 Mo de disque :

1. **Retirer le Random Forest** (17 Mo) si XGBoost suffit :
   ```bash
   rm outputs/models/random_forest_final.pkl
   ```
2. **Limiter les rapports Word** dans `media/reports/` (purge périodique).
3. **Compresser le GeoJSON** (le fichier 15 Mo peut être simplifié).

---

## 🌐 Comparaison hébergeurs gratuits (rappel)

| Plateforme | Toujours actif ? | Setup | Recommandation |
|---|:---:|---|---|
| **PythonAnywhere** | ✅ Oui | Manuel (20 min) | ✅ **Choix optimal pour votre cas** |
| Render | ❌ Sleep 15 min | Auto (5 min) | Bon pour MVP / démo |
| Fly.io | ⚠️ Limité free | Technique (Docker) | Pour devs avancés |
| Railway | ❌ Free retiré | Auto | Crédit limité |

---

**Auteur** : Équipe Suivi-Évaluation du GTR Paludisme — Délégation Régionale de la Santé Publique de l'Extrême-Nord.
