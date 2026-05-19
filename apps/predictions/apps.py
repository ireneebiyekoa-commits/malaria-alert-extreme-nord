"""
Configuration de l'app predictions.
Charge les modèles ML une seule fois au démarrage du serveur (cf. mémoire §2.3.4.6).
"""
import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PredictionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.predictions'
    verbose_name = 'Prévisions ML'

    def ready(self):
        """Précharge les modèles .pkl en mémoire dès le démarrage."""
        # Import différé pour éviter les imports circulaires
        from .ml_loader import preload_models
        try:
            preload_models()
        except Exception as exc:
            logger.warning(f"Modèles ML non préchargés au démarrage : {exc}")
