"""
Génération de rapports Word (.docx) — page Prévisions.

Utilise le fichier TEMPLATE.docx situé à la racine du projet comme modèle :
l'entête institutionnelle (logos, drapeau, mentions ministérielles) y est
déjà préremplie. Le contenu dynamique (titre, tableaux, graphiques, analyse)
est ajouté à la suite du contenu existant.
"""
import io
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# matplotlib est OPTIONNEL : si absent (déploiement allégé PythonAnywhere),
# le rapport est généré sans graphique mais reste pleinement fonctionnel.
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _MATPLOTLIB_OK = True
except ImportError:
    _MATPLOTLIB_OK = False

from django.conf import settings
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Inches, Pt, RGBColor

TEMPLATE_PATH = settings.BASE_DIR / 'TEMPLATE.docx'


def _load_template() -> Document:
    """Charge le template Word s'il existe, sinon un document vierge."""
    if TEMPLATE_PATH.exists():
        return Document(str(TEMPLATE_PATH))
    return Document()


def generer_rapport_previsions(
    district: str,
    algorithme: str,
    horizon: int,
    previsions: List[Dict[str, Any]],
    historique: List[Dict[str, Any]],
    metriques: Dict[str, float],
    analyse_ia: str,
    auteur: str = "Équipe Suivi-Évaluation du GTR",
) -> io.BytesIO:
    """Génère un rapport Word complet et retourne un buffer BytesIO."""
    doc = _load_template()

    # Marges si le template ne les fixe pas
    if not TEMPLATE_PATH.exists():
        section = doc.sections[0]
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)

    # ============================================================
    # Sépare le contenu institutionnel (template) du contenu dynamique
    # ============================================================
    doc.add_paragraph()   # Séparateur visuel

    # Titre du rapport
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("RAPPORT DE PRÉVISION ÉPIDÉMIQUE")
    r.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = RGBColor(0x0E, 0x47, 0x6E)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s = sub.add_run(
        f"District : {district.replace('District ', '')} — "
        f"Algorithme : {algorithme} — Horizon : {horizon} mois"
    )
    s.italic = True
    s.font.size = Pt(10.5)

    # Métadonnées
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    meta.add_run(f"Date d'émission : {datetime.now():%d/%m/%Y à %H:%M}\n").italic = True
    meta.add_run(f"Auteur : {auteur}").italic = True

    doc.add_paragraph()

    # ============================================================
    # Section 1 — Synthèse
    # ============================================================
    doc.add_heading("1. Synthèse des prévisions", level=1)
    doc.add_paragraph(
        f"Ce rapport présente les prévisions d'incidence palustre générées par le modèle "
        f"{algorithme} pour le {district} aux horizons 1, 2 et 3 mois. Les prévisions sont "
        f"comparées aux seuils d'alerte épidémique (P75 et P90) définis selon les "
        f"recommandations de l'Organisation Mondiale de la Santé (OMS, 2014)."
    )

    # ============================================================
    # Section 2 — Tableau des prévisions
    # ============================================================
    doc.add_heading("2. Prévisions détaillées", level=1)

    table = doc.add_table(rows=1, cols=5)
    try:
        table.style = 'Light Grid Accent 1'
    except KeyError:
        table.style = 'Table Grid'
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER

    hdr = table.rows[0].cells
    hdr[0].text = "Horizon"
    hdr[1].text = "Date cible"
    hdr[2].text = "Incidence prédite (/1000)"
    hdr[3].text = "Cas attendus"
    hdr[4].text = "Niveau d'alerte"

    for cell in hdr:
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True

    for p in previsions:
        row = table.add_row().cells
        row[0].text = f"h={p['horizon']}"
        row[1].text = str(p.get('date', '—'))
        row[2].text = f"{p['incidence']:.2f}"
        row[3].text = f"{p.get('cas', 0):.0f}"
        niv = p.get('niveau', 'vert')
        row[4].text = {'vert': '🟢 Normal',
                       'orange': '🟠 Élevé',
                       'rouge': '🔴 Critique'}.get(niv, niv)

    # ============================================================
    # Section 3 — Graphique
    # ============================================================
    doc.add_heading("3. Visualisation graphique", level=1)
    img_buffer = _generer_graphique(historique, previsions, district, algorithme)
    if img_buffer:
        doc.add_picture(img_buffer, width=Inches(6.0))
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.add_run(
            f"Figure : Évolution observée (12 derniers mois) et prévisions {algorithme} "
            f"pour le {district}."
        ).italic = True

    # ============================================================
    # Section 4 — Performances
    # ============================================================
    doc.add_heading("4. Performance du modèle", level=1)
    perf_table = doc.add_table(rows=1, cols=3)
    try:
        perf_table.style = 'Light Grid Accent 1'
    except KeyError:
        perf_table.style = 'Table Grid'
    h = perf_table.rows[0].cells
    h[0].text = "RMSE"
    h[1].text = "MAE"
    h[2].text = "R²"
    for c in h:
        for p in c.paragraphs:
            for r in p.runs:
                r.bold = True
    row = perf_table.add_row().cells
    row[0].text = f"{metriques.get('rmse', 0):.3f}"
    row[1].text = f"{metriques.get('mae', 0):.3f}"
    row[2].text = f"{metriques.get('r2', 0):.3f}"

    doc.add_paragraph(
        "Métriques calculées en validation walk-forward sur les 5 plis (2021→2025), "
        "agrégées sur l'ensemble des 32 districts."
    )

    # ============================================================
    # Section 5 — Analyse interprétative
    # ============================================================
    doc.add_heading("5. Analyse interprétative", level=1)
    for line in (analyse_ia or '').split('\n'):
        line = line.strip()
        if not line:
            doc.add_paragraph()
            continue
        if line.startswith('### '):
            doc.add_heading(line.replace('### ', ''), level=2)
        elif line.startswith('## '):
            doc.add_heading(line.replace('## ', ''), level=2)
        elif line.startswith('**') and line.endswith('**'):
            p = doc.add_paragraph()
            p.add_run(line.strip('*')).bold = True
        else:
            doc.add_paragraph(line)

    # ============================================================
    # Pied de page
    # ============================================================
    doc.add_paragraph()
    foot = doc.add_paragraph()
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    f = foot.add_run(
        "_______\n"
        "Rapport généré automatiquement par la plateforme d'alerte précoce du paludisme. "
        "Document confidentiel à usage interne."
    )
    f.italic = True
    f.font.size = Pt(8.5)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def _generer_graphique(historique, previsions, district, algorithme):
    """Génère un graphique matplotlib des prévisions et le retourne en BytesIO."""
    if not _MATPLOTLIB_OK:
        return None
    try:
        dates_hist = [h['date'] for h in historique[-12:]]
        inc_hist = [h['incidence'] for h in historique[-12:]]

        dates_pred = [p['date'] for p in previsions]
        inc_pred = [p['incidence'] for p in previsions]

        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(dates_hist, inc_hist, marker='o', color='#0e476e',
                linewidth=2, label='Observé', markersize=6)
        ax.plot(dates_pred, inc_pred, marker='s', color='#dc3545',
                linewidth=2, linestyle='--', label=f'Prévision {algorithme}', markersize=8)

        ax.set_xlabel('Mois')
        ax.set_ylabel('Incidence (/1000 hab.)')
        ax.set_title(f"{district} — Prévisions {algorithme}",
                     fontsize=12, fontweight='bold')
        ax.legend(loc='upper left')
        ax.grid(alpha=0.3)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=130, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception:
        return None
