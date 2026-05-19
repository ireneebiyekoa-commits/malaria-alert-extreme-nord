"""
Modèles métier — Système d'alerte paludisme.
Conformes au MCD/MLD du mémoire §2.3.4.3 et §2.3.4.4.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


# ============================================================
# DISTRICT
# ============================================================
class District(models.Model):
    """District sanitaire de la région de l'Extrême-Nord (32 districts)."""

    nom = models.CharField(max_length=100, unique=True, verbose_name='Nom du district')
    code_geojson = models.CharField(
        max_length=50, blank=True,
        verbose_name='Identifiant GeoJSON',
        help_text="Correspond à la propriété 'district_id' dans le GeoJSON",
    )
    longitude = models.FloatField(verbose_name='Longitude')
    latitude = models.FloatField(verbose_name='Latitude')
    population = models.PositiveIntegerField(
        default=0,
        verbose_name='Population (dernière valeur connue)',
    )

    class Meta:
        verbose_name = 'District sanitaire'
        verbose_name_plural = 'Districts sanitaires'
        ordering = ['nom']

    def __str__(self):
        return self.nom

    @property
    def nom_court(self) -> str:
        """Retire le préfixe 'District ' pour l'affichage compact."""
        return self.nom.replace('District ', '')


# ============================================================
# OBSERVATION (cas confirmés mensuels)
# ============================================================
class Observation(models.Model):
    """Cas confirmés de paludisme par district et par mois."""

    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name='observations',
        verbose_name='District',
    )
    date = models.DateField(verbose_name='Mois (1er jour du mois)')
    annee = models.PositiveSmallIntegerField(verbose_name='Année')
    mois = models.PositiveSmallIntegerField(verbose_name='Mois (1-12)')
    trimestre = models.CharField(max_length=2, blank=True, verbose_name='Trimestre')
    cas_confirmes = models.FloatField(verbose_name='Cas confirmés')
    population = models.PositiveIntegerField(verbose_name='Population')

    class Meta:
        verbose_name = 'Observation mensuelle'
        verbose_name_plural = 'Observations mensuelles'
        unique_together = [('district', 'date')]
        ordering = ['district', 'date']
        indexes = [
            models.Index(fields=['district', 'date']),
            models.Index(fields=['annee', 'mois']),
        ]

    def __str__(self):
        return f"{self.district.nom_court} — {self.date:%Y-%m} : {self.cas_confirmes:.0f} cas"

    @property
    def incidence(self) -> float:
        """Incidence pour 1 000 habitants."""
        return (self.cas_confirmes / self.population) * 1000 if self.population else 0.0


# ============================================================
# METEO (données climatiques mensuelles)
# ============================================================
class Meteo(models.Model):
    """Données climatiques mensuelles par district (source : NASA POWER)."""

    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name='meteos',
        verbose_name='District',
    )
    date = models.DateField(verbose_name='Mois')
    temp_moy = models.FloatField(verbose_name='Température moyenne (°C)')
    humidite = models.FloatField(verbose_name='Humidité relative (%)')
    precip_mensuel = models.FloatField(verbose_name='Précipitations mensuelles (mm)')
    source = models.CharField(
        max_length=50, default='NASA_POWER',
        verbose_name='Source de la donnée',
    )

    class Meta:
        verbose_name = 'Donnée climatique'
        verbose_name_plural = 'Données climatiques'
        unique_together = [('district', 'date')]
        ordering = ['district', 'date']

    def __str__(self):
        return f"{self.district.nom_court} — {self.date:%Y-%m}"


# ============================================================
# PREVISION (sorties des modèles ML)
# ============================================================
class Prevision(models.Model):
    """Prévision d'incidence générée par un modèle ML pour un district donné."""

    ALGO_CHOICES = [
        ('RF', 'Random Forest'),
        ('XGB', 'XGBoost'),
    ]
    NIVEAU_CHOICES = [
        ('vert', 'Normal'),
        ('orange', 'Élevé'),
        ('rouge', 'Critique'),
    ]

    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name='previsions',
        verbose_name='District',
    )
    algorithme = models.CharField(max_length=5, choices=ALGO_CHOICES, verbose_name='Algorithme')
    horizon = models.PositiveSmallIntegerField(verbose_name='Horizon (mois)')
    date_origine = models.DateField(verbose_name="Date d'origine de la prévision")
    date_cible = models.DateField(verbose_name='Date cible')
    incidence_predite = models.FloatField(verbose_name='Incidence prédite (/1000)')
    cas_predits = models.FloatField(verbose_name='Cas prédits')
    niveau_alerte = models.CharField(
        max_length=10, choices=NIVEAU_CHOICES, default='vert',
        verbose_name="Niveau d'alerte",
    )
    seuil_alerte = models.FloatField(null=True, blank=True, verbose_name="Seuil d'alerte (M + σ)")
    seuil_epidemio = models.FloatField(null=True, blank=True, verbose_name='Seuil épidémiologique (M + 2σ)')
    date_creation = models.DateTimeField(default=timezone.now, verbose_name='Date de calcul')

    class Meta:
        verbose_name = 'Prévision'
        verbose_name_plural = 'Prévisions'
        unique_together = [('district', 'algorithme', 'horizon', 'date_origine')]
        ordering = ['-date_origine', 'district', 'algorithme', 'horizon']
        indexes = [
            models.Index(fields=['date_origine', 'algorithme']),
            models.Index(fields=['niveau_alerte']),
        ]

    def __str__(self):
        return (f"{self.district.nom_court} — {self.algorithme} h={self.horizon} "
                f"({self.date_cible:%Y-%m}) : {self.incidence_predite:.2f}")


# ============================================================
# SEUIL D'ALERTE (moyenne + écart-type, méthode OMS)
# ============================================================
class SeuilAlerte(models.Model):
    """
    Seuils d'alerte épidémique par district x mois calendaire.

    Méthode des écarts-types (recommandée par l'OMS pour la surveillance
    épidémiologique du paludisme) :
       - Seuil d'alerte         = Moyenne + 1 * Écart-type
       - Seuil épidémiologique  = Moyenne + 2 * Écart-type

    Interprétation des niveaux :
       - VERT    : incidence < seuil_alerte         (situation normale)
       - ORANGE  : seuil_alerte ≤ incidence < seuil_epidemio  (alerte)
       - ROUGE   : incidence ≥ seuil_epidemio       (épidémie probable)
    """

    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name='seuils',
        verbose_name='District',
    )
    mois_calendaire = models.PositiveSmallIntegerField(verbose_name='Mois calendaire (1-12)')

    # Statistiques de base (référence historique)
    moyenne = models.FloatField(default=0, verbose_name='Moyenne historique')
    ecart_type = models.FloatField(default=0, verbose_name='Écart-type historique')

    # Seuils dérivés (= valeurs stockées pour accès rapide)
    seuil_alerte = models.FloatField(default=0, verbose_name="Seuil d'alerte (M + σ)")
    seuil_epidemio = models.FloatField(default=0, verbose_name='Seuil épidémiologique (M + 2σ)')

    class Meta:
        verbose_name = "Seuil d'alerte"
        verbose_name_plural = "Seuils d'alerte"
        unique_together = [('district', 'mois_calendaire')]
        ordering = ['district', 'mois_calendaire']

    def __str__(self):
        return (f"{self.district.nom_court} — mois {self.mois_calendaire} : "
                f"alerte={self.seuil_alerte:.2f} / épidémio={self.seuil_epidemio:.2f}")


# ============================================================
# PERFORMANCE (métriques de validation walk-forward)
# ============================================================
class Performance(models.Model):
    """Métriques de validation walk-forward (globales, sans district).

    Conforme au choix méthodologique du mémoire : un seul modèle est entraîné
    sur les données poolées des 32 districts, donc les métriques sont régionales.
    """

    algorithme = models.CharField(max_length=5, verbose_name='Algorithme')
    fold = models.PositiveSmallIntegerField(verbose_name='Pli walk-forward (1-5)')
    horizon = models.PositiveSmallIntegerField(verbose_name='Horizon (mois)')
    rmse = models.FloatField(verbose_name='RMSE')
    mae = models.FloatField(verbose_name='MAE')
    r2 = models.FloatField(verbose_name='R²')
    n_predictions = models.PositiveIntegerField(default=0, verbose_name='Nombre de prédictions')

    class Meta:
        verbose_name = 'Performance modèle'
        verbose_name_plural = 'Performances modèles'
        unique_together = [('algorithme', 'fold', 'horizon')]
        ordering = ['algorithme', 'fold', 'horizon']

    def __str__(self):
        return f"{self.algorithme} fold={self.fold} h={self.horizon} : RMSE={self.rmse:.3f}"


# ============================================================
# IMPORT LOG (journal des imports mensuels)
# ============================================================
class ImportLog(models.Model):
    """Journal horodaté des imports mensuels de données."""

    STATUT_CHOICES = [
        ('succes', 'Succès'),
        ('erreur', 'Erreur'),
        ('partiel', 'Partiel'),
    ]

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='imports', verbose_name='Utilisateur',
    )
    date_import = models.DateTimeField(default=timezone.now, verbose_name="Date d'import")
    fichier_nom = models.CharField(max_length=255, blank=True, verbose_name='Fichier')
    nb_lignes = models.PositiveIntegerField(default=0, verbose_name='Nombre de lignes')
    nb_districts = models.PositiveIntegerField(default=0, verbose_name='Districts couverts')
    periode = models.CharField(max_length=50, blank=True, verbose_name='Période (YYYY-MM)')
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='succes')
    message = models.TextField(blank=True, verbose_name='Détails')

    class Meta:
        verbose_name = 'Journal des imports'
        verbose_name_plural = 'Journaux des imports'
        ordering = ['-date_import']

    def __str__(self):
        return f"{self.date_import:%Y-%m-%d %H:%M} — {self.statut} ({self.nb_lignes} lignes)"
