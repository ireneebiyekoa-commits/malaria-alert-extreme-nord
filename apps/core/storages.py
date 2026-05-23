"""
Storage backends personnalisés.

WhiteNoiseTolerantStorage : hérite de CompressedManifestStaticFilesStorage
mais ne plante pas si un fichier référencé via {% static %} est manquant.
- manifest_strict = False  : la recherche dans le manifest ne plante pas
- hashed_name() override   : le calcul du hash ne plante pas si fichier absent
                              (retourne juste le nom non hashé)

Utilisé en production pour éviter qu'un asset oublié casse toute l'app.
"""
import logging

from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class WhiteNoiseTolerantStorage(CompressedManifestStaticFilesStorage):
    """Version tolérante : un fichier manquant retourne l'URL sans plantage."""
    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            # Fichier physique introuvable -> on retourne juste le nom non hashé
            # (au lieu de planter et casser toute la page).
            logger.warning(f"Static file missing : {name} (URL retournée non hashée)")
            return name

    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            logger.warning(f"Static file missing in manifest : {name}")
            return name
