"""Configuration de production (Render, PythonAnywhere, etc.)."""
import dj_database_url
from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = False

# --- Base de données : PostgreSQL si DATABASE_URL fournie, sinon SQLite ---
_db_url = config('DATABASE_URL', default='')
if _db_url:
    DATABASES = {
        'default': dj_database_url.parse(
            _db_url, conn_max_age=600, conn_health_checks=True
        )
    }
# sinon : on garde SQLite défini dans base.py (idéal pour démo / hébergement gratuit)

# --- ALLOWED_HOSTS : ajout automatique du host Render ---
import os
_render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
# Wildcards Render
ALLOWED_HOSTS = list(set(ALLOWED_HOSTS + ['.onrender.com']))

# --- Sécurité HTTPS (Render impose HTTPS automatiquement) ---
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=bool)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

# CSRF_TRUSTED_ORIGINS pour Render
CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
]
if _render_host:
    CSRF_TRUSTED_ORIGINS.append(f'https://{_render_host}')

# --- Static (WhiteNoise compressé, SANS manifest pour robustesse maximale) ---
# CompressedStaticFilesStorage compresse en gzip/brotli mais N'AJOUTE PAS
# de hash aux noms de fichiers (pas de manifest). Conséquence :
#   - Aucun risque de plantage sur un fichier référencé mais absent
#   - URLs simples (/static/img/favicon.png au lieu de /static/img/favicon.abc123.png)
#   - Cache HTTP géré par les headers WhiteNoise (Cache-Control: public, max-age=...)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# --- Sessions ---
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# --- Logs sur stdout (visible dans dashboard Render) ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '[{asctime}] {levelname} {name} | {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'loggers': {
        'apps':   {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django': {'handlers': ['console'], 'level': 'INFO'},
    },
}
