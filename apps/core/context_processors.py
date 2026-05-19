"""Context processors — injecte des variables globales dans tous les templates."""
from django.conf import settings


def site_context(request):
    """Variables institutionnelles disponibles dans tous les templates."""
    return {
        'APP_NAME': settings.APP_NAME,
        'APP_NAME_SHORT': settings.APP_NAME_SHORT,
        'APP_INSTITUTION': settings.APP_INSTITUTION,
        'APP_DELEGATION': settings.APP_DELEGATION,
        'APP_PROGRAMME': settings.APP_PROGRAMME,
        'APP_REGION': settings.APP_REGION,
        'APP_AUTHOR': settings.APP_AUTHOR,
        'APP_VERSION': settings.APP_VERSION,
    }
