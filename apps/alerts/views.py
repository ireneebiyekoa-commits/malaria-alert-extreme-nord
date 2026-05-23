"""Carte d'alerte épidémique — vert / orange / rouge."""
import io
from datetime import date

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from apps.core.models import District, Meteo, Observation, Prevision, SeuilAlerte
from apps.core.utils import filter_by_user_role, format_mois_annee

from apps.predictions.engine import predict, predict_recursive
from apps.predictions.ml_loader import is_meta_available, is_ready


@login_required
def index(request):
    """Page de la carte d'alerte."""
    user = request.user

    if user.is_admin:
        districts = District.objects.all().order_by('nom')
    elif user.district_id:
        districts = District.objects.filter(pk=user.district_id)
    else:
        districts = District.objects.none()

    algos = []
    if is_meta_available():
        algos.append(('META', 'Méta-modèle adaptatif (recommandé)'))
    algos.extend([('XGB', 'XGBoost'), ('RF', 'Random Forest')])

    context = {
        'districts': districts,
        'algorithmes': algos,
        'horizons': [1, 2, 3],
        'is_admin': user.is_admin,
    }
    return render(request, 'alerts/index.html', context)


@login_required
def api_alertes(request):
    """
    Calcule les niveaux d'alerte pour tous les districts (ou le district de l'utilisateur)
    selon l'algorithme et l'horizon demandés.
    """
    user = request.user
    algo = request.GET.get('algo', 'XGB').upper()
    horizon = int(request.GET.get('horizon', 1))

    if user.is_admin:
        districts = District.objects.all()
    elif user.district_id:
        districts = District.objects.filter(pk=user.district_id)
    else:
        districts = District.objects.none()

    if not is_ready():
        return JsonResponse({'error': 'Modèles ML non chargés'}, status=503)

    results = []
    seuils_qs = SeuilAlerte.objects.select_related('district')
    seuils_map = {(s.district_id, s.mois_calendaire): s for s in seuils_qs}

    for district in districts:
        obs = list(Observation.objects.filter(district=district).order_by('date'))
        meteo = {m.date: m for m in Meteo.objects.filter(district=district)}
        if not obs:
            continue

        rows = []
        for o in obs:
            m = meteo.get(o.date)
            rows.append({
                'date': o.date,
                'annee': o.annee,
                'mois': o.mois,
                'incidence': o.incidence,
                'precip_mensuel': m.precip_mensuel if m else 0,
                'temp_moy': m.temp_moy if m else 0,
                'humidite': m.humidite if m else 0,
                'population': o.population,
            })
        historic_df = pd.DataFrame(rows)

        try:
            if algo == 'META':
                preds = predict('META', district.nom, historic_df, horizons=[horizon])
            else:
                preds = predict_recursive(algo, district.nom, historic_df, horizons=[horizon])
        except Exception:
            continue

        p = preds.get(horizon)
        if not p:
            continue

        seuil = seuils_map.get((district.id, p['mois_cible']))
        s_alerte = seuil.seuil_alerte if seuil else 0
        s_epidemio = seuil.seuil_epidemio if seuil else 0
        moyenne = seuil.moyenne if seuil else 0
        niveau = 'vert'
        if seuil:
            if p['incidence'] >= seuil.seuil_epidemio:
                niveau = 'rouge'
            elif p['incidence'] >= seuil.seuil_alerte:
                niveau = 'orange'

        cas_predits = (p['incidence'] * district.population) / 1000

        results.append({
            'district': district.nom,
            'district_court': district.nom_court,
            'code_geojson': district.code_geojson,
            'longitude': district.longitude,
            'latitude': district.latitude,
            'population': district.population,
            'date_cible': p['date_cible'].isoformat(),
            'mois_label': format_mois_annee(p['date_cible']),
            'incidence_predite': round(p['incidence'], 3),
            'cas_predits': round(cas_predits, 0),
            'seuil_alerte': round(s_alerte, 2),
            'seuil_epidemio': round(s_epidemio, 2),
            'moyenne_hist': round(moyenne, 2),
            'niveau': niveau,
        })

    # Tri par sévérité (rouge → orange → vert) puis incidence décroissante
    severite = {'rouge': 0, 'orange': 1, 'vert': 2}
    results.sort(key=lambda r: (severite.get(r['niveau'], 3), -r['incidence_predite']))

    return JsonResponse({
        'algorithme': algo,
        'horizon': horizon,
        'alertes': results,
        'resume': {
            'rouge': sum(1 for r in results if r['niveau'] == 'rouge'),
            'orange': sum(1 for r in results if r['niveau'] == 'orange'),
            'vert': sum(1 for r in results if r['niveau'] == 'vert'),
            'total': len(results),
        },
    })


@login_required
def export_pdf(request):
    """Export PDF de la carte d'alerte avec tableau récapitulatif."""
    algo = request.GET.get('algo', 'XGB').upper()
    horizon = int(request.GET.get('horizon', 1))

    # Récupérer les alertes via api_alertes
    import json
    response = api_alertes(request)
    data = json.loads(response.content)

    if 'error' in data:
        return HttpResponse(f"Erreur : {data['error']}", status=500)

    alertes = data['alertes']
    resume = data['resume']

    # Génération PDF
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'],
        fontSize=16, textColor=colors.HexColor('#0e476e'),
        alignment=1, spaceAfter=12,
    )
    sub_style = ParagraphStyle(
        'SubStyle', parent=styles['Normal'],
        fontSize=10, alignment=1, spaceAfter=18,
    )

    story = []
    story.append(Paragraph("RÉPUBLIQUE DU CAMEROUN", styles['Title']))
    story.append(Paragraph("Ministère de la Santé Publique<br/>GTR Paludisme — Extrême-Nord",
                            sub_style))
    story.append(Paragraph(f"CARTE D'ALERTE ÉPIDÉMIQUE", title_style))
    story.append(Paragraph(
        f"Algorithme : <b>{algo}</b> &nbsp; | &nbsp; Horizon : <b>{horizon} mois</b> &nbsp; | &nbsp; "
        f"Généré le {date.today():%d/%m/%Y}",
        sub_style
    ))

    # Résumé global
    summary_data = [
        ['Niveau', 'Nombre de districts'],
        ['🔴 Rouge (Critique)', str(resume['rouge'])],
        ['🟠 Orange (Élevé)', str(resume['orange'])],
        ['🟢 Vert (Normal)', str(resume['vert'])],
        ['Total', str(resume['total'])],
    ]
    t = Table(summary_data, colWidths=[6*cm, 4*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0e476e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.6*cm))

    # Tableau détaillé
    table_data = [['District', 'Date cible', 'Incidence prédite', 'Cas attendus',
                   'Seuil alerte', 'Seuil épidémio', 'Niveau']]
    for a in alertes:
        table_data.append([
            a['district_court'],
            a['mois_label'],
            f"{a['incidence_predite']:.2f}",
            f"{int(a['cas_predits']):,}".replace(',', ' '),
            f"{a['seuil_alerte']:.2f}",
            f"{a['seuil_epidemio']:.2f}",
            a['niveau'].upper(),
        ])

    big = Table(table_data, repeatRows=1,
                colWidths=[4*cm, 3*cm, 3*cm, 3*cm, 2.5*cm, 2.5*cm, 2.5*cm])

    ts = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0e476e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ])

    color_map = {
        'ROUGE': colors.HexColor('#fde2e2'),
        'ORANGE': colors.HexColor('#fef3e0'),
        'VERT': colors.HexColor('#e3f5e6'),
    }
    for i, a in enumerate(alertes, 1):
        c = color_map.get(a['niveau'].upper(), colors.white)
        ts.add('BACKGROUND', (-1, i), (-1, i), c)

    big.setStyle(ts)
    story.append(big)

    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph(
        "<i>Seuils définis selon les recommandations de l'OMS (2014). "
        "Document confidentiel à usage interne.</i>",
        styles['Italic']
    ))

    doc.build(story)
    buf.seek(0)

    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="carte_alerte_{algo}_h{horizon}_{date.today().isoformat()}.pdf"'
    )
    return response
