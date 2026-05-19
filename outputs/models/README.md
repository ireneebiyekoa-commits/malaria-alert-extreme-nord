# Dossier `outputs/` — Artefacts ML

Ce dossier doit contenir les sorties du notebook **`modelisation_paludisme_final.ipynb`**.

## Contenu attendu

```
outputs/
├── seuils_alerte.csv                     # moyenne, ecart_type, seuil_alerte (M+σ), seuil_epidemio (M+2σ) par district × mois
├── metriques_walk_forward.csv            # RMSE / MAE / R² par algo × fold × horizon
├── importance_variables.csv              # MDI + Gain
├── permutation_importance.csv
├── treeshap_importance.csv
├── ljung_box_rf.csv / ljung_box_xgb.csv
├── diebold_mariano.csv
├── previsions_fold5_xgb.csv
└── models/
    ├── random_forest_final.pkl           # Modèle RF entraîné (joblib)
    ├── xgboost_final.pkl                 # Modèle XGB entraîné (joblib)
    ├── artefacts.pkl                     # {'features': [...], 'best_params_*': ..., ...}
    └── climatologie_district_mois.csv    # Moyennes climatiques de référence
```

## Comment générer ce contenu

Lancer le notebook `modelisation_paludisme_final.ipynb` en plaçant `DATA_COMP_2025_epuree.xlsx`
dans le même dossier. Le notebook crée automatiquement le dossier `outputs/` à la fin (cellule 49).

## Comment l'utiliser dans l'application

```bash
python manage.py load_model_artifacts    # charge seuils + performances en base
python manage.py runserver
```

Les fichiers `.pkl` sont chargés en mémoire au démarrage du serveur Django via
`apps/predictions/apps.py:ready()`.
