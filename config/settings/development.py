"""Configuration de développement (SQLite, DEBUG=True)."""
from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Désactiver WhiteNoise compressed manifest en dev (évite l'erreur si collectstatic n'a pas tourné)
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Email console
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Internal IPs pour debug toolbar (optionnel)
INTERNAL_IPS = ['127.0.0.1']
