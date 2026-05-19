"""
Configuration de base — Système d'alerte précoce du paludisme.
Les configurations spécifiques (dev / prod) héritent de ce fichier.
"""
from pathlib import Path
from decouple import config, Csv

# ============================================================
# CHEMINS
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Racine des artefacts ML (fournis par le notebook)
ML_OUTPUTS_DIR = BASE_DIR / 'outputs'
ML_MODELS_DIR = ML_OUTPUTS_DIR / 'models'

# Fichier de données initial
INITIAL_DATA_FILE = BASE_DIR / 'data_sources' / 'DATA_COMP_2025_epuree.xlsx'
DISTRICTS_COORDS_FILE = BASE_DIR / 'data_sources' / 'coordonnees_districts_extreme_nord.xlsx'
DISTRICTS_GEOJSON_FILE = BASE_DIR / 'static' / 'geojson' / 'extreme_nord_districts.geojson'

# ============================================================
# SÉCURITÉ
# ============================================================
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# ============================================================
# APPLICATIONS
# ============================================================
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.core',
    'apps.accueil',
    'apps.dashboard',
    'apps.predictions',
    'apps.alerts',
    'apps.data_management',
    'apps.about',
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

# ============================================================
# MIDDLEWARE
# ============================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ============================================================
# URLS & WSGI
# ============================================================
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

# ============================================================
# TEMPLATES
# ============================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.site_context',
            ],
        },
    },
]

# ============================================================
# BASE DE DONNÉES (surchargée en dev / prod)
# ============================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ============================================================
# AUTHENTIFICATION
# ============================================================
AUTH_USER_MODEL = 'accounts.Utilisateur'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Hachage bcrypt (conforme aux spécifications du mémoire §2.3.4.5)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:index'
LOGOUT_REDIRECT_URL = 'accueil:index'

# ============================================================
# INTERNATIONALISATION
# ============================================================
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_TZ = True

# ============================================================
# FICHIERS STATIQUES & MEDIA
# ============================================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ============================================================
# PARAMÈTRES PAR DÉFAUT
# ============================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB

# ============================================================
# IA GÉNÉRATIVE — GOOGLE GEMINI
# ============================================================
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_MODEL = config('GEMINI_MODEL', default='gemini-2.5-flash')
GEMINI_ENABLED = bool(GEMINI_API_KEY)

# ============================================================
# API NASA POWER
# ============================================================
NASA_POWER_BASE_URL = config(
    'NASA_POWER_BASE_URL',
    default='https://power.larc.nasa.gov/api/temporal/monthly/point'
)
NASA_POWER_PARAMETERS = ['T2M', 'RH2M', 'PRECTOTCORR']   # temp, humidité, précipitations
NASA_POWER_TIMEOUT = 30                                   # secondes

# ============================================================
# CONFIGURATION MÉTIER (Application paludisme)
# ============================================================
APP_NAME = "Système d'alerte précoce du paludisme"
APP_NAME_SHORT = "MalariaAlert XN"
APP_INSTITUTION = "Ministère de la Santé Publique du Cameroun"
APP_DELEGATION = "Délégation Régionale de la Santé Publique de l'Extrême-Nord"
APP_PROGRAMME = "Groupe Technique Régional Paludisme"
APP_REGION = "Région de l'Extrême-Nord du Cameroun"
APP_AUTHOR = "Équipe Suivi-Évaluation du GTR"
APP_VERSION = "1.0.0"

# Algorithmes disponibles
ML_ALGORITHMS = ['RF', 'XGB']
ML_ALGORITHM_LABELS = {
    'RF': 'Random Forest',
    'XGB': 'XGBoost',
}

# Horizons de prévision (en mois)
PREDICTION_HORIZONS = [1, 2, 3]

# Couleurs niveaux d'alerte (conformes OMS 2014)
ALERT_LEVELS = {
    'vert':   {'label': 'Normal',  'color': '#28a745', 'priorite': 0},
    'orange': {'label': 'Élevé',   'color': '#fd7e14', 'priorite': 1},
    'rouge':  {'label': 'Critique','color': '#dc3545', 'priorite': 2},
}

# ============================================================
# LOGGING
# ============================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} | {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'malaria_app.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}
