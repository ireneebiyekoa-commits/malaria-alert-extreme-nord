"""
Module d'analyse IA — Google Gemini REST API (sans SDK).

Cette implémentation utilise directement l'API REST de Gemini via la
bibliothèque `requests` (déjà présente dans le projet), ce qui évite
d'avoir à installer le SDK `google-generativeai` (qui pèse ~130 Mo
avec ses dépendances grpcio/protobuf/pydantic/google-api-client).

Bénéfice : compatible avec les hébergeurs gratuits limités en disque
(PythonAnywhere Free Tier 512 Mo, etc.).
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Endpoint REST Gemini
_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={api_key}"
)

_GEMINI_INIT_ERROR: Optional[str] = None


# ============================================================
# Lecture robuste de la configuration
# ============================================================
def _get_api_key() -> str:
    """Ordre : settings -> variable d'env -> fichier .env."""
    try:
        key = (settings.GEMINI_API_KEY or '').strip()
        if key:
            return key
    except Exception:
        pass

    key = (os.environ.get('GEMINI_API_KEY') or '').strip()
    if key:
        return key

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
    return os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash').strip()


# ============================================================
# Appel REST Gemini
# ============================================================
def call_gemini_rest(
    user_message: str,
    system_prompt: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
    timeout: int = 30,
) -> str:
    """
    Appelle l'API REST de Gemini et retourne le texte de réponse.

    Args:
        user_message: question / consigne courante
        system_prompt: instructions système (rôle, contraintes)
        history: [{'role': 'user' | 'assistant', 'content': '...'}, ...]
        timeout: timeout HTTP en secondes

    Raises:
        RuntimeError: si la clé est absente, l'appel échoue ou la réponse est vide.
    """
    global _GEMINI_INIT_ERROR

    api_key = _get_api_key()
    if not api_key:
        _GEMINI_INIT_ERROR = "Clé API Gemini non configurée"
        raise RuntimeError(_GEMINI_INIT_ERROR)

    model = _get_model_name()
    url = _GEMINI_ENDPOINT.format(model=model, api_key=api_key)

    # Construction du payload
    contents: List[Dict[str, Any]] = []
    for msg in (history or []):
        role = 'user' if msg.get('role') == 'user' else 'model'
        content = (msg.get('content') or '').strip()
        if content:
            contents.append({'role': role, 'parts': [{'text': content}]})

    # Question courante
    contents.append({'role': 'user', 'parts': [{'text': user_message}]})

    payload: Dict[str, Any] = {'contents': contents}
    if system_prompt:
        payload['systemInstruction'] = {'parts': [{'text': system_prompt}]}

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Erreur réseau Gemini : {exc}") from exc

    if resp.status_code == 429:
        raise RuntimeError("Quota Gemini dépassé (limite gratuite atteinte).")
    if resp.status_code != 200:
        raise RuntimeError(
            f"Gemini HTTP {resp.status_code} : {resp.text[:200]}"
        )

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Réponse Gemini invalide : {exc}") from exc

    candidates = data.get('candidates', [])
    if not candidates:
        raise RuntimeError(f"Aucune réponse du modèle : {data}")

    parts = candidates[0].get('content', {}).get('parts', [])
    text_parts = [p.get('text', '') for p in parts if p.get('text')]
    if not text_parts:
        raise RuntimeError(f"Réponse vide du modèle : {candidates[0]}")

    return ''.join(text_parts).strip()


# ============================================================
# Analyse de prévisions (interface publique inchangée)
# ============================================================
def analyser_previsions(
    district: str,
    algorithme: str,
    previsions: List[Dict[str, Any]],
    historique_recent: List[Dict[str, Any]],
    metriques: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Génère une analyse IA des prévisions (avec fallback local si Gemini indispo)."""
    prompt = _construire_prompt(district, algorithme, previsions, historique_recent, metriques)

    try:
        text = call_gemini_rest(user_message=prompt, timeout=30)
        return {
            'success': True,
            'analyse': text,
            'source': 'gemini',
            'erreur': None,
        }
    except RuntimeError as exc:
        logger.warning(f"Gemini indisponible : {exc}. Bascule sur fallback local.")
        return _analyse_locale_fallback(
            district, algorithme, previsions, historique_recent, metriques
        )


def _construire_prompt(
    district: str,
    algorithme: str,
    previsions: List[Dict[str, Any]],
    historique_recent: List[Dict[str, Any]],
    metriques: Optional[Dict[str, float]],
) -> str:
    """Construit le prompt à envoyer à Gemini."""
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
        metr_txt = (
            f"Performance du modèle {algorithme} (validation walk-forward) : "
            f"RMSE = {metriques.get('rmse', 0):.2f}, "
            f"MAE = {metriques.get('mae', 0):.2f}, "
            f"R² = {metriques.get('r2', 0):.3f}."
        )

    return f"""Tu es un expert en épidémiologie du paludisme dans la région de l'Extrême-Nord du Cameroun.
Analyse les prévisions d'incidence palustre suivantes pour le {district}.

Contexte : Le système d'alerte précoce s'appuie sur le modèle {algorithme} validé sur la période 2017-2025.
Les seuils d'alerte sont définis selon la **méthode des écarts-types** (recommandation OMS), calculés par district et par mois calendaire à partir de l'historique :
- **Seuil d'alerte** = Moyenne historique + 1 × Écart-type
- **Seuil épidémiologique** = Moyenne historique + 2 × Écarts-types

Classification des niveaux :
- VERT (Normal)    : incidence prédite < seuil d'alerte
- ORANGE (Élevé)   : seuil d'alerte ≤ incidence prédite < seuil épidémiologique
- ROUGE (Critique) : incidence prédite ≥ seuil épidémiologique (épidémie probable)

Prévisions générées :
{prev_txt}

{hist_txt}

{metr_txt}

Fournis une analyse structurée en français en 3 paragraphes clairs et concis (200 mots maximum au total) :

1. **Interprétation des prévisions** : que signifient ces niveaux pour le district ? Réfère-toi explicitement aux seuils d'alerte et épidémiologique.
2. **Tendance** : la situation s'aggrave-t-elle, s'améliore-t-elle, ou reste-t-elle stable par rapport aux 6 derniers mois ?
3. **Recommandations opérationnelles** : actions concrètes que peut entreprendre le GTR Paludisme de l'Extrême-Nord (mobilisation des CPS, distribution de moustiquaires, renforcement diagnostique, surveillance entomologique, etc.).

Sois précis, professionnel et factuel. Évite les généralités. Adresse-toi à un décideur de santé publique."""


def _analyse_locale_fallback(
    district: str,
    algorithme: str,
    previsions: List[Dict[str, Any]],
    historique_recent: List[Dict[str, Any]],
    metriques: Optional[Dict[str, float]],
) -> Dict[str, Any]:
    """Analyse par règles si Gemini indisponible (mode dégradé)."""
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
        metr_str = (f" Les performances du modèle {algorithme} "
                    f"(RMSE = {metriques.get('rmse', 0):.2f}) confirment la fiabilité de la prévision.")

    analyse = (
        f"### Analyse du {district}\n\n"
        f"**1. Interprétation** : {diag} Sur les trois horizons de prévision, "
        f"{nb_rouge} mois sont en niveau rouge et {nb_orange} en orange.\n\n"
        f"**2. Tendance** : L'évolution récente de l'incidence est **{tendance}** "
        f"sur les six derniers mois observés.{metr_str}\n\n"
        f"**3. Recommandations** : {reco}\n\n"
        f"*(Analyse générée en mode dégradé — service IA non disponible)*"
    )

    return {
        'success': True,
        'analyse': analyse,
        'source': 'local_fallback',
        'erreur': _GEMINI_INIT_ERROR,
    }
