"""URLs racine du projet."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),

    # Pages publiques
    path('', include('apps.accueil.urls', namespace='accueil')),
    path('a-propos/', include('apps.about.urls', namespace='about')),

    # Authentification
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),

    # Applications métier (protégées par @login_required)
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('previsions/', include('apps.predictions.urls', namespace='predictions')),
    path('alertes/', include('apps.alerts.urls', namespace='alerts')),
    path('donnees/', include('apps.data_management.urls', namespace='data_management')),
]

# Servir les fichiers media en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')

# Personnalisation admin
admin.site.site_header = "Administration — Système d'alerte paludisme"
admin.site.site_title = "MalariaAlert XN Admin"
admin.site.index_title = "Tableau de bord administrateur"
