from django.contrib import admin

from .models import (District, ImportLog, Meteo, Observation, Performance,
                     Prevision, SeuilAlerte)


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('nom', 'longitude', 'latitude', 'population')
    search_fields = ('nom',)
    ordering = ('nom',)


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ('district', 'date', 'cas_confirmes', 'population', 'incidence')
    list_filter = ('annee', 'mois', 'district')
    search_fields = ('district__nom',)
    date_hierarchy = 'date'


@admin.register(Meteo)
class MeteoAdmin(admin.ModelAdmin):
    list_display = ('district', 'date', 'temp_moy', 'humidite', 'precip_mensuel', 'source')
    list_filter = ('district', 'source')
    date_hierarchy = 'date'


@admin.register(Prevision)
class PrevisionAdmin(admin.ModelAdmin):
    list_display = ('district', 'algorithme', 'horizon', 'date_origine', 'date_cible',
                    'incidence_predite', 'cas_predits', 'niveau_alerte')
    list_filter = ('algorithme', 'horizon', 'niveau_alerte', 'date_origine')
    search_fields = ('district__nom',)
    date_hierarchy = 'date_origine'


@admin.register(SeuilAlerte)
class SeuilAlerteAdmin(admin.ModelAdmin):
    list_display = ('district', 'mois_calendaire', 'p25', 'p75', 'p90')
    list_filter = ('mois_calendaire',)
    search_fields = ('district__nom',)


@admin.register(Performance)
class PerformanceAdmin(admin.ModelAdmin):
    list_display = ('algorithme', 'fold', 'horizon', 'rmse', 'mae', 'r2', 'n_predictions')
    list_filter = ('algorithme', 'horizon')


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = ('date_import', 'utilisateur', 'fichier_nom', 'periode',
                    'nb_lignes', 'nb_districts', 'statut')
    list_filter = ('statut', 'date_import')
    readonly_fields = ('date_import',)
    date_hierarchy = 'date_import'
