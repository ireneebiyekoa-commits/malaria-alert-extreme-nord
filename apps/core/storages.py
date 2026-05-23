"""
Storage backends personnalisés.

WhiteNoiseTolerantStorage : hérite de CompressedManifestStaticFilesStorage
mais ne plante pas si un fichier référencé via {% static %} est manquant.
Utilisé en production pour éviter qu'un asset oublié casse toute l'app.
"""
from whitenoise.storage import CompressedManifestStaticFilesStorage


class WhiteNoiseTolerantStorage(CompressedManifestStaticFilesStorage):
    """Version tolérante : un fichier manquant retourne l'URL sans plantage."""
    manifest_strict = False
