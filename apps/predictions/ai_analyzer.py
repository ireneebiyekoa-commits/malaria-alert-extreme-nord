"""
Module d'analyse IA — Google Gemini API.
Génère des interprétations automatiques des résultats de prévision.
"""
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Initialisation conditionnelle
_GEMINI_CLIENT = None
_GEMINI_INIT_ERROR: Optional[str] = None


def _get_api_key() -> str:
    """
    Lecture robuste de la clé Gemini.
    Ordre : settings → variable d'environnement → fichier .env.
    """
    # 1) Django settings
    try:
        key = (settings.GEMINI_API_KEY or '').strip()
        if key:
            return key
    except Exception:
        pass

    # 2) Variable d'environnement directe
    import os
    key = (os.environ.get('GEMINI_API_KEY') or '').strip()
    if key:
        return key

    # 3) Fichier .env (lecture brute, dernier recours)
    try:
        env_path = settings.BASE_DIR / '.env'
        if env_path.exists():
            for line in env_path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line.startswith('GEMINI_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass

    return ''


def _get_model_name() -> str:
    try:
        m = (settings.GEMINI_MODEL or '').strip()
        if m:
            return m
    except Exception:
        pass
    import os
    return os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash').strip()


def _init_gemini():
    """Initialise le client Gemini si la clé est disponible."""
    global _GEMINI_CLIENT, _GEMINI_INIT_ERROR

    if _GEMINI_CLIENT is not None:
        return _GEMINI_CLIENT

    api_key = _get_api_key()
    model_name = _get_model_name()

    if not api_key:
        _GEMINI_INIT_ERROR = "Clé API Gemini non configurée"
        logger.warning("Gemini désactivé : aucune clé trouvée dans settings/env/.env")
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        _GEMINI_CLIENT = genai.GenerativeModel(model_name)
        logger.info(f"Client Gemini initialisé (modèle : {model_name})")
        return _GEMINI_CLIENT
    except Exception as exc:
        _GEMINI_INIT_ERROR = str(exc)
        logger.error(f"Échec initialisation Gemini : {exc}")
        return None


def analyser_previsions(
    district: str,
    algorithme: str,
    previsions: List[Dict[str, Any]],
    historique_recent: List[Dict[str, Any]],
    metriques: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Génère une analyse IA des prévisions.

    Args:
        district: nom du district
        algorithme: 'Random Forest' ou 'XGBoost'
        previsions: [{'horizon': 1, 'date': 'YYYY-MM', 'incidence': X, 'cas': N, 'niveau': 'orange'}, ...]
        historique_recent: 12 derniers mois observés
        metriques: {'rmse': X, 'mae': Y, 'r2': Z}

    Returns:
        {'success': bool, 'analyse': str, 'erreur': str | None}
    """
    client = _init_gemini()
    if client is None:
        return _analyse_locale_fallback(district, algorithme, previsions, historique_recent, metriques)

    prompt = _construire_prompt(district, algorithme, previsions, historique_recent, metriques)

    try:
        response = client.generate_content(prompt)
        return {
            'success': True,
            'analyse': response.text.strip(),
            'source': 'gemini',
            'erreur': None,
        }
    except Exception as exc:
        logger.error(f"Erreur Gemini : {exc}")
        return _analyse_locale_fallback(district, algorithme, previsions, historique_recent, metriques)


def _construire_prompt(
    district: str,
    algorithme: str,
    previsions: List[Dict[str, Any]],
    historique_recent: List[Dict[str, Any]],
    metriques: Optional[Dict[str, float]],
) -> str:
    """Construit le prompt pour Gemini."""
    prev_txt = "\n".join([
        f"  - Horizon {p['horizon']} mois ({p.get('date', '?')}): "
        f"incidence prédite = {p['incidence']:.2f}/1000 hab., "
        f"~{p.get('cas', 0):.0f} cas attendus, niveau d'alerte = {p.get('niveau', 'n/a').upper()}"
        for p in previsions
    ])

    hist_txt = ""
    if historique_recent:
        valeurs = [h.get('incidence', 0) for h in historique_recent[-6:]]
        hist_txt = (
            f"Évolution récente (6 derniers mois) : "
            + ", ".join([f"{v:.2f}" for v in valeurs])
            + f". Moyenne : {sum(valeurs)/len(valeurs):.2f}/1000 hab."
        )

    metr_txt = ""
    if metriques:
        metr_txt = (f"Performance du modèle {algorithme} (validation walk-forward) : "
                    f"RMSE = {metriques.get('rmse', 0):.2f}, "
                    f"MAE = {metriques.get('mae', 0):.2f}, "
                    f"R² = {metriques.get('r2', 0):.3f}.")

    return f"""Tu es un expert en épidémiologie du paludisme dans la région de l'Extrême-Nord du Cameroun.
Analyse les prévisions d'incidence palustre suivantes pour le {district}.

Contexte : Le système d'alerte précoce s'appuie sur le modèle {algorithme} validé sur la période 2017-2025.
Les seuils d'alerte sont définis selon les recommandations de l'OMS :
- VERT (Normal) : incidence < percentile 75
- ORANGE (Élevé) : entre P75 et P90
- ROUGE (Critique) : incidence >= P90

Prévisions générées :
{prev_txt}

{hist_txt}

{metr_txt}

Fournis une analyse structurée en français en 3 paragraphes clairs et concis (200 mots maximum au total) :

1. **Interprétation des prévisions** : que signifient ces niveaux pour le district ?
2. **Tendance** : la situation s'aggrave-t-elle, s'améliore-t-elle, ou reste-t-elle stable ?
3. **Recommandations opérationnelles** : actions concrètes que peut entreprendre le GTR Paludisme de l'Extrême-Nord (mobilisation des CPS, distribution de moustiquaires, renforcement diagnostique, etc.).

Sois précis, professionnel et factuel. Évite les généralités. Adresse-toi à un décideur de santé publique."""


def _analyse_locale_fallback(
    district: str,
    algorithme: str,
    previsions: List[Dict[str, Any]],
    historique_recent: List[Dict[str, Any]],
    metriques: Optional[Dict[str, float]],
) -> Dict[str, Any]:
    """Analyse par règles si l'API IA est indisponible (mode dégradé)."""
    niveaux = [p.get('niveau', 'vert') for p in previsions]
    nb_rouge = sum(1 for n in niveaux if n == 'rouge')
    nb_orange = sum(1 for n in niveaux if n == 'orange')

    if nb_rouge >= 2:
        diag = "🔴 **Situation critique** : plusieurs horizons en alerte rouge."
        reco = ("Mobilisation immédiate des équipes du district. Renforcement de la chimioprévention "
                "saisonnière (CPS), pré-positionnement des intrants antipaludiques (TDR, ACT), "
                "intensification de la surveillance entomologique et communication communautaire.")
    elif nb_rouge == 1 or nb_orange >= 2:
        diag = "🟠 **Situation à surveiller** : alerte élevée détectée sur au moins un horizon."
        reco = ("Activation des protocoles d'alerte précoce. Vérification des stocks de moustiquaires "
                "imprégnées et de tests diagnostiques rapides. Sensibilisation accrue dans les zones à risque.")
    else:
        diag = "🟢 **Situation normale** : incidence prédite sous les seuils d'alerte."
        reco = ("Poursuite des activités courantes de prévention et de surveillance. "
                "Maintien de la vigilance saisonnière, en particulier en période de transmission élevée.")

    inc_values = [h.get('incidence', 0) for h in historique_recent[-6:]]
    tendance = "stable"
    if len(inc_values) >= 3:
        debut = sum(inc_values[:len(inc_values)//2]) / max(1, len(inc_values)//2)
        fin = sum(inc_values[len(inc_values)//2:]) / max(1, len(inc_values) - len(inc_values)//2)
        if fin > debut * 1.15:
            tendance = "en hausse"
        elif fin < debut * 0.85:
            tendance = "en baisse"

    metr_str = ""
    if metriques:
        metr_str = f" Les performances du modèle {algorithme} (RMSE = {metriques.get('rmse', 0):.2f}) confirment la fiabilité de la prévision."

    analyse = (
        f"### Analyse du {district}\n\n"
        f"**1. Interprétation** : {diag} Sur les trois horizons de prévision, "
        f"{nb_rouge} mois sont en niveau rouge et {nb_orange} en orange.\n\n"
        f"**2. Tendance** : L'évolution récente de l'incidence est **{tendance}** "
        f"sur les six derniers mois observés.{metr_str}\n\n"
        f"**3. Recommandations** : {reco}\n\n"
        f"*(Analyse générée en mode dégradé — API Gemini non disponible)*"
    )

    return {
        'success': True,
        'analyse': analyse,
        'source': 'local_fallback',
        'erreur': _GEMINI_INIT_ERROR,
    }
