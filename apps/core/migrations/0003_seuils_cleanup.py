"""
Migration manuelle :
  - Prevision : RENAME seuil_p75 -> seuil_alerte, RENAME seuil_p90 -> seuil_epidemio
  - SeuilAlerte : DROP p25, p75, p90 (deprecated)

Préserve les données existantes (RenameField).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_seuilalerte_ecart_type_seuilalerte_moyenne_and_more'),
    ]

    operations = [
        # ---------- Prevision : renommage ----------
        migrations.RenameField(
            model_name='prevision',
            old_name='seuil_p75',
            new_name='seuil_alerte',
        ),
        migrations.RenameField(
            model_name='prevision',
            old_name='seuil_p90',
            new_name='seuil_epidemio',
        ),
        # Update verbose_name après renommage
        migrations.AlterField(
            model_name='prevision',
            name='seuil_alerte',
            field=models.FloatField(
                blank=True, null=True,
                verbose_name="Seuil d'alerte (M + σ)"
            ),
        ),
        migrations.AlterField(
            model_name='prevision',
            name='seuil_epidemio',
            field=models.FloatField(
                blank=True, null=True,
                verbose_name='Seuil épidémiologique (M + 2σ)'
            ),
        ),

        # ---------- SeuilAlerte : suppression des champs deprecated ----------
        migrations.RemoveField(
            model_name='seuilalerte',
            name='p25',
        ),
        migrations.RemoveField(
            model_name='seuilalerte',
            name='p75',
        ),
        migrations.RemoveField(
            model_name='seuilalerte',
            name='p90',
        ),
    ]
