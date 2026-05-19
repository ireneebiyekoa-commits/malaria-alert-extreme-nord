# Cellule à ajouter à votre notebook `modelisation_paludisme_final.ipynb`

Vos fichiers `.pkl` (random_forest_final.pkl, xgboost_final.pkl, artefacts.pkl) ne contiennent **pas** les métriques de validation walk-forward.

Pour exporter ces métriques vers l'application Django, ajoutez **cette cellule** à la fin de votre notebook (juste après la cellule où vous calculez `results_walk_forward` ou équivalent), et exécutez-la. Elle créera le fichier `outputs/metriques_walk_forward.csv`.

```python
# ============================================================
# Export des métriques walk-forward pour l'application Django
# ============================================================
import pandas as pd

# Adapter le nom de la variable selon votre notebook
# (la liste/DataFrame contenant vos résultats par pli x algo x horizon)
rows = []
for algo in ['RF', 'XGB']:
    for fold in range(1, 6):
        for horizon in [1, 2, 3]:
            # ----- À ADAPTER : récupérer vos vraies métriques ici -----
            # Exemple si vos métriques sont dans un dict :
            # rmse = mes_metriques[algo][fold][horizon]['rmse']
            #
            # Si vous avez un DataFrame `df_metriques`:
            # row = df_metriques.query(f"algo == '{algo}' & fold == {fold} & horizon == {horizon}").iloc[0]
            # rmse, mae, r2 = row['rmse'], row['mae'], row['r2']

            rmse = ...   # REMPLACER
            mae  = ...   # REMPLACER
            r2   = ...   # REMPLACER
            n    = 320   # nombre de prédictions par fold (32 districts × 10-12 mois)

            rows.append({
                'algo':     algo,
                'fold':     fold,
                'horizon':  horizon,
                'rmse':     rmse,
                'mae':      mae,
                'r2':       r2,
                'n':        n,
            })

df_export = pd.DataFrame(rows)
df_export.to_csv('outputs/metriques_walk_forward.csv', index=False)
print(f"Exporté : {len(df_export)} lignes dans outputs/metriques_walk_forward.csv")
df_export.head(10)
```

Une fois ce fichier généré, lancez dans le dossier Django :

```bash
python manage.py load_model_artifacts
```

Cette commande :
1. Charge `outputs/metriques_walk_forward.csv` dans la table `Performance`
2. Remplace les valeurs calculées par défaut

**En attendant que vous fournissiez ce fichier**, l'application utilise des valeurs **réelles calculées en walk-forward** sur vos données via la commande `python manage.py compute_performances` (déjà exécutée). Ces valeurs sont méthodologiquement correctes et utilisables pour le mémoire si elles vous conviennent.
