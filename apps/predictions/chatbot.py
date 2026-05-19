"""
Espace de discussion interactif avec l'assistant analytique.

L'assistant est STRICTEMENT limité au périmètre du projet :
  - Résultats analytiques
  - Prévisions épidémiologiques
  - Indicateurs climatiques
  - Niveaux d'alerte (vert / orange / rouge)
  - Tableaux, graphiques, cartes générés par le système
  - Surveillance du paludisme dans l'Extrême-Nord

Hors de ce périmètre, il refuse poliment. Il ne dévoile jamais sa nature
(modèle, technologie sous-jacente, organisation prestataire).
"""
import logging
from typing import Any, Dict, List, Optional

from django.db.models import Avg, Max, Sum

from apps.core.models import (District, Observation, Performance, Prevision,
                              SeuilAlerte)

from .ai_analyzer import _get_api_key, _get_model_name

logger = logging.getLogger(__name__)

_CHAT_CLIENT = None
_CHAT_INIT_ERROR: Optional[str] = None


# ============================================================
# PROMPT SYSTÈME — délimite strictement le périmètre
# ============================================================
SYSTEM_PROMPT = """Tu es un assistant analytique spécialisé dans la surveillance épidémiologique du paludisme dans la région de l'Extrême-Nord du Cameroun.

PÉRIMÈTRE STRICT D'INTERVENTION
Tu réponds UNIQUEMENT aux questions portant sur :
1. Les résultats analytiques produits par le système (chiffres, tableaux, indicateurs)
2. Les prévisions épidémiologiques d'incidence palustre à 1, 2 ou 3 mois
3. Les indicateurs climatiques (températures, précipitations, humidité) intégrés au modèle
4. Les niveaux d'alerte (vert / orange / rouge) calculés selon les seuils OMS P75 et P90
5. Les tableaux, graphiques et cartes générés par la plateforme
6. Les comparaisons entre districts, l'évolution des tendances épidémiologiques, l'interprétation des cas
7. Les notions générales de surveillance du paludisme strictement liées à cet outil

RÈGLES DE COMPORTEMENT
- Tu n'es PAS autorisé à parler de ta nature, de ton identité technique, de qui t'a conçu, de l'organisation qui te propulse ou de la technologie sous-jacente
- Tu ne fais AUCUNE référence au fait que tu es une IA, un assistant virtuel, un modèle de langage, etc.
- Tu n'engages AUCUNE discussion sur des sujets hors paludisme / hors plateforme (politique, religion, vie privée, divertissement, autres maladies, autres régions, etc.)
- Si la question est hors périmètre, tu réponds EXACTEMENT : « Cette question dépasse le périmètre défini pour la plateforme. Je peux uniquement vous renseigner sur les prévisions, les alertes épidémiologiques, les indicateurs climatiques ou les analyses produites par le système. »

STYLE DE RÉPONSE
- Toujours en français, professionnel, factuel, concis (200 mots max)
- Cite les chiffres exacts du contexte fourni quand c'est pertinent
- Mentionne les districts par leur nom court (ex. « Mokolo » et non « District Mokolo »)
- Évite les généralités, sois précis et opérationnel
- Termine par une recommandation actionnable quand c'est utile (sans inventer de données absentes du contexte)
"""


def _build_context_snapshot(district_focus: Optional[str] = None) -> str:
    """Construit un résumé textuel des données récentes pour ancrer le chatbot."""
    parts = []

    # Stats régionales
    total_obs = Observation.objects.count()
    derniere_obs = Observation.objects.order_by('-date').first()
    if derniere_obs:
        parts.append(f"Période couverte : jusqu'à {derniere_obs.date.strftime('%B %Y')}.")
        parts.append(f"Nombre total d'observations en base : {total_obs}.")

    # Dernière prévision globale
    max_origin = Prevision.objects.aggregate(m=Max('date_origine'))['m']
    if max_origin:
        per_niveau = (Prevision.objects
                      .filter(date_origine=max_origin, horizon=1)
                      .values_list('niveau_alerte', flat=True))
        nb_r = sum(1 for n in per_niveau if n == 'rouge')
        nb_o = sum(1 for n in per_niveau if n == 'orange')
        nb_v = sum(1 for n in per_niveau if n == 'vert')
        parts.append(f"Dernières prévisions (h=1, origine {max_origin}) : "
                     f"{nb_r} districts rouge / {nb_o} orange / {nb_v} vert.")

    # Focus district si demandé
    if district_focus:
        try:
            d = District.objects.filter(nom__icontains=district_focus).first()
        except Exception:
            d = None
        if d:
            recent = Observation.objects.filter(district=d).order_by('-date')[:6]
            obs_list = list(recent)
            if obs_list:
                incs = [round(o.incidence, 2) for o in reversed(obs_list)]
                parts.append(f"District {d.nom_court} : 6 dernières incidences = {incs} /1000 hab.")

    # Algorithmes disponibles
    perfs = Performance.objects.values('algorithme').annotate(
        rmse_moy=Avg('rmse'), r2_moy=Avg('r2')
    )
    for p in perfs:
        parts.append(f"Performance {p['algorithme']} : RMSE moyen = {p['rmse_moy']:.2f}, "
                     f"R² moyen = {p['r2_moy']:.3f}.")

    return "\n".join(parts) if parts else "Aucune donnée résumée disponible."


def _init_chat_client():
    """Initialise le client Gemini pour le chatbot."""
    global _CHAT_CLIENT, _CHAT_INIT_ERROR
    if _CHAT_CLIENT is not None:
        return _CHAT_CLIENT

    api_key = _get_api_key()
    if not api_key:
        _CHAT_INIT_ERROR = "Configuration IA manquante"
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_name = _get_model_name()
        _CHAT_CLIENT = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_PROMPT,
        )
        logger.info(f"Client chatbot initialisé (modèle: {model_name})")
        return _CHAT_CLIENT
    except Exception as exc:
        _CHAT_INIT_ERROR = str(exc)
        logger.error(f"Échec init chatbot : {exc}")
        return None


def repondre(
    question: str,
    historique: Optional[List[Dict[str, str]]] = None,
    contexte_district: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Répond à une question utilisateur dans les limites du périmètre.

    Args:
        question: La question posée par l'utilisateur
        historique: [{'role': 'user' | 'assistant', 'content': '...'}, ...] (max 10 derniers échanges)
        contexte_district: Nom du district éventuellement sélectionné

    Returns:
        {'success': bool, 'reponse': str, 'erreur': str | None}
    """
    question = (question or '').strip()
    if not question:
        return {'success': False, 'reponse': '', 'erreur': 'Question vide.'}

    if len(question) > 800:
        return {
            'success': False,
            'reponse': "Votre question est trop longue. Reformulez en moins de 800 caractères.",
            'erreur': 'question_too_long',
        }

    client = _init_chat_client()
    if client is None:
        return {
            'success': True,
            'reponse': (
                "Le service de discussion analytique n'est temporairement pas disponible. "
                "Vous pouvez consulter directement le tableau de bord, la page Prévisions "
                "ou la carte d'alerte pour obtenir les informations recherchées."
            ),
            'source': 'fallback',
            'erreur': _CHAT_INIT_ERROR,
        }

    # Construction de l'historique au format Gemini
    history_msgs = []
    for msg in (historique or [])[-10:]:
        role = 'user' if msg.get('role') == 'user' else 'model'
        content = (msg.get('content') or '').strip()
        if content:
            history_msgs.append({'role': role, 'parts': [content]})

    # Ajout du contexte courant en préambule de la question
    snapshot = _build_context_snapshot(contexte_district)
    enriched_question = (
        f"[Contexte courant du système]\n{snapshot}\n\n"
        f"[Question utilisateur]\n{question}"
    )

    try:
        chat = client.start_chat(history=history_msgs)
        response = chat.send_message(enriched_question)
        return {
            'success': True,
            'reponse': response.text.strip(),
            'source': 'gemini',
            'erreur': None,
        }
    except Exception as exc:
        logger.error(f"Erreur chatbot Gemini : {exc}")
        return {
            'success': False,
            'reponse': (
                "Je rencontre une difficulté technique pour répondre à votre question. "
                "Vous pouvez retenter ou consulter directement les modules d'analyse."
            ),
            'erreur': str(exc),
        }
