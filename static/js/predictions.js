/* ============================================================
   Page Prévisions — Graphique, tableau, IA, exports
   ============================================================ */

(function () {
    'use strict';

    const $ = (s) => document.querySelector(s);

    const selDistrict = $('#sel-district');
    const selAlgo = $('#sel-algo');
    const selHorizon = $('#sel-horizon');
    const btnPredict = $('#btn-predict');
    const btnAnalyseIa = $('#btn-analyse-ia');
    const btnExportExcel = $('#btn-export-excel');
    const btnExportWord = $('#btn-export-word');

    let predictionChart = null;
    let currentData = null;

    const NIVEAU_BADGE = {
        vert:   '<span class="badge badge-vert"><i class="fa-solid fa-circle-check"></i> Normal</span>',
        orange: '<span class="badge badge-orange"><i class="fa-solid fa-circle-exclamation"></i> Élevé</span>',
        rouge:  '<span class="badge badge-rouge"><i class="fa-solid fa-triangle-exclamation"></i> Critique</span>',
    };

    const NIVEAU_COLOR = {
        vert: '#28a745',
        orange: '#fd7e14',
        rouge: '#dc3545',
    };

    // ============================================================
    // Utilitaire CSRF
    // ============================================================
    function getCookie(name) {
        const cookies = document.cookie.split(';');
        for (const c of cookies) {
            const [k, v] = c.trim().split('=');
            if (k === name) return decodeURIComponent(v);
        }
        return null;
    }

    // ============================================================
    // Chargement des prévisions
    // ============================================================
    function chargerPrevisions(silencieux = false) {
        const districtId = selDistrict.value;
        const algo = selAlgo.value;
        const horizon = selHorizon.value;

        if (!districtId) return;

        btnPredict.disabled = true;
        btnPredict.innerHTML = '<span class="loader"></span> Calcul...';
        btnAnalyseIa.disabled = true;

        return fetch(`/previsions/api/prevision/?district_id=${districtId}&algo=${algo}&horizon=${horizon}`)
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                return r.json();
            })
            .then(data => {
                if (data.error) throw new Error(data.error);
                currentData = data;
                renderPrediction(data);
                btnAnalyseIa.disabled = false;
            })
            .catch(err => {
                if (!silencieux) alert('Erreur : ' + err.message);
                else console.warn('Auto-prévision : ' + err.message);
            })
            .finally(() => {
                btnPredict.disabled = false;
                btnPredict.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Générer les prévisions';
            });
    }

    btnPredict.addEventListener('click', () => chargerPrevisions(false));

    // Recharger automatiquement à chaque changement de paramètre
    [selDistrict, selAlgo, selHorizon].forEach(sel => {
        sel.addEventListener('change', () => chargerPrevisions(false));
    });

    // Auto-chargement initial dès l'ouverture de la page
    document.addEventListener('DOMContentLoaded', function () {
        if (selDistrict.value) {
            setTimeout(() => chargerPrevisions(true), 200);
        }
    });

    function renderPrediction(data) {
        // Info
        $('#predict-info').textContent = `${data.district} · Population : ${data.population.toLocaleString('fr-FR')} · Algo : ${data.algorithme} · h=${data.horizon}`;

        // Performance
        $('#perf-rmse').textContent = data.metriques.rmse;
        $('#perf-mae').textContent = data.metriques.mae;
        $('#perf-r2').textContent = data.metriques.r2;

        // Tableau
        const tbody = $('#table-previsions tbody');
        tbody.innerHTML = '';
        const prevList = Array.isArray(data.previsions) ? data.previsions : (data.previsions.XGB || []);

        prevList.forEach(p => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>h=${p.horizon}</strong></td>
                <td>${p.mois_label}</td>
                <td>${p.incidence.toFixed(2)}</td>
                <td>${Math.round(p.cas).toLocaleString('fr-FR')}</td>
                <td>${(p.seuil_alerte || 0).toFixed(2)}</td>
                <td>${(p.seuil_epidemio || 0).toFixed(2)}</td>
                <td>${NIVEAU_BADGE[p.niveau] || p.niveau}</td>
            `;
            tbody.appendChild(tr);
        });

        // Graphique
        renderChart(data);
    }

    function renderChart(data) {
        const histLabels = data.historique.map(h => h.mois_label);
        const histInc = data.historique.map(h => h.incidence);

        const prevList = Array.isArray(data.previsions) ? data.previsions : null;
        const prevListRF = data.previsions.RF || null;
        const prevListXGB = data.previsions.XGB || null;

        const labelsAll = [...histLabels];
        if (prevList) prevList.forEach(p => labelsAll.push(p.mois_label));
        else if (prevListXGB) prevListXGB.forEach(p => labelsAll.push(p.mois_label));

        const connectorLast = histInc.length ? histInc[histInc.length - 1] : null;

        const datasets = [
            {
                label: 'Observé (12 derniers mois)',
                data: [...histInc, ...new Array(labelsAll.length - histInc.length).fill(null)],
                borderColor: '#0e476e',
                backgroundColor: 'rgba(14, 71, 110, 0.1)',
                borderWidth: 2.5,
                tension: 0.25,
                pointRadius: 4,
                order: 1,
            }
        ];

        const buildPredArray = (list) => {
            const arr = new Array(histInc.length - 1).fill(null);
            arr.push(connectorLast);
            list.forEach(p => arr.push(p.incidence));
            while (arr.length < labelsAll.length) arr.push(null);
            return arr;
        };

        if (prevList) {
            datasets.push({
                label: `Prévision ${data.algorithme}`,
                data: buildPredArray(prevList),
                borderColor: '#dc3545',
                backgroundColor: 'rgba(220, 53, 69, 0.1)',
                borderWidth: 2.5,
                borderDash: [6, 4],
                tension: 0.25,
                pointRadius: 6,
                pointStyle: 'rectRot',
                pointBackgroundColor: prevList.map(p => NIVEAU_COLOR[p.niveau] || '#888'),
                order: 1,
            });
        } else {
            if (prevListRF) datasets.push({
                label: 'Prévision RF',
                data: buildPredArray(prevListRF),
                borderColor: '#1565a0',
                borderWidth: 2,
                borderDash: [6, 4],
                tension: 0.25,
                pointRadius: 6,
                order: 1,
            });
            if (prevListXGB) datasets.push({
                label: 'Prévision XGBoost',
                data: buildPredArray(prevListXGB),
                borderColor: '#A23B72',
                borderWidth: 2,
                borderDash: [3, 3],
                tension: 0.25,
                pointRadius: 6,
                order: 1,
            });
        }

        // ===== COURBES de seuils saisonniers =====
        // Chaque mois calendaire a SON seuil propre (il varie selon la saison).
        // On construit donc deux séries de valeurs alignées sur labelsAll :
        //   - une valeur de seuil_alerte pour chaque point (historique + prévision)
        //   - idem pour seuil_epidemio
        // Cela produit deux *courbes* saisonnières, pas des lignes droites.
        const referenceList = prevList || prevListXGB || prevListRF || [];

        // Concaténer historique + référence de prévisions pour avoir les seuils
        // de TOUS les points du graphique
        const allPoints = [...data.historique, ...referenceList];
        const seuilAlerteCurve = allPoints.map(pt =>
            (pt.seuil_alerte != null && pt.seuil_alerte > 0) ? pt.seuil_alerte : null
        );
        const seuilEpidemioCurve = allPoints.map(pt =>
            (pt.seuil_epidemio != null && pt.seuil_epidemio > 0) ? pt.seuil_epidemio : null
        );

        // Aligner longueur sur labelsAll (au cas où en mode comparaison RF+XGB,
        // labelsAll inclut les deux séries — on pad avec null)
        while (seuilAlerteCurve.length < labelsAll.length) seuilAlerteCurve.push(null);
        while (seuilEpidemioCurve.length < labelsAll.length) seuilEpidemioCurve.push(null);

        if (seuilAlerteCurve.some(v => v !== null)) {
            datasets.push({
                label: "Seuil d'alerte (M + σ)",
                data: seuilAlerteCurve,
                borderColor: '#fd7e14',
                backgroundColor: 'rgba(253, 126, 20, 0.05)',
                borderWidth: 2,
                borderDash: [5, 4],
                pointRadius: 0,
                pointHoverRadius: 4,
                fill: false,
                tension: 0.3,           // courbe douce
                order: 2,
                spanGaps: true,
            });
        }
        if (seuilEpidemioCurve.some(v => v !== null)) {
            datasets.push({
                label: 'Seuil épidémiologique (M + 2σ)',
                data: seuilEpidemioCurve,
                borderColor: '#c0392b',
                backgroundColor: 'rgba(192, 57, 43, 0.05)',
                borderWidth: 2,
                borderDash: [8, 4],
                pointRadius: 0,
                pointHoverRadius: 4,
                fill: false,
                tension: 0.3,
                order: 2,
                spanGaps: true,
            });
        }

        if (predictionChart) predictionChart.destroy();

        const ctx = document.getElementById('chart-prediction').getContext('2d');
        predictionChart = new Chart(ctx, {
            type: 'line',
            data: { labels: labelsAll, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: true, text: `Prévision d'incidence — ${data.district}` },
                    legend: { position: 'top' },
                },
                scales: {
                    y: { title: { display: true, text: 'Incidence (/1000 hab.)' }, beginAtZero: true },
                    x: { title: { display: true, text: 'Mois' } },
                }
            }
        });
    }

    // ============================================================
    // Analyse IA
    // ============================================================
    btnAnalyseIa.addEventListener('click', function () {
        if (!currentData) return;

        btnAnalyseIa.disabled = true;
        btnAnalyseIa.innerHTML = '<span class="loader"></span> Analyse...';

        const prevs = Array.isArray(currentData.previsions)
            ? currentData.previsions
            : (currentData.previsions.XGB || []);

        const payload = {
            district: currentData.district,
            algorithme: selAlgo.options[selAlgo.selectedIndex].text,
            previsions: prevs.map(p => ({
                horizon: p.horizon,
                date: p.mois_label,
                incidence: p.incidence,
                cas: p.cas,
                niveau: p.niveau,
            })),
            historique: currentData.historique,
            metriques: currentData.metriques,
        };

        fetch('/previsions/api/analyse-ia/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify(payload),
        })
            .then(r => r.json())
            .then(data => {
                // Récupère les éléments en sécurité (peuvent être absents du template)
                const placeholder = document.getElementById('ai-placeholder');
                const result = document.getElementById('ai-result');
                const source = document.getElementById('ai-source');
                const content = document.getElementById('ai-content');

                if (placeholder) placeholder.style.display = 'none';
                if (result) result.style.display = 'block';
                if (source) source.textContent = data.source === 'gemini' ? 'Google Gemini' : 'analyse locale';
                if (content) content.innerHTML = formatAnalyse(data.analyse || '');

                currentData.analyse_ia = data.analyse;
            })
            .catch(err => {
                alert('Erreur analyse IA : ' + err.message);
            })
            .finally(() => {
                btnAnalyseIa.disabled = false;
                btnAnalyseIa.innerHTML = 'Régénérer l\'analyse';
            });
    });

    function formatAnalyse(txt) {
        // Conversion markdown léger -> HTML
        return txt
            .replace(/\n\n/g, '</p><p>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            .replace(/^## (.+)$/gm, '<h3>$1</h3>')
            .replace(/^# (.+)$/gm, '<h2>$1</h2>')
            .replace(/^/, '<p>')
            .concat('</p>');
    }

    // ============================================================
    // Exports
    // ============================================================
    if (btnExportExcel) {
        btnExportExcel.addEventListener('click', function () {
            if (!currentData) { alert('Générez d\'abord les prévisions.'); return; }
            const districtId = selDistrict.value;
            const algo = selAlgo.value;
            const horizon = selHorizon.value;
            window.location.href =
                `/previsions/api/export-excel/?district_id=${districtId}&algo=${algo}&horizon=${horizon}`;
        });
    }

    if (btnExportWord) {
        btnExportWord.addEventListener('click', async function () {
            if (!currentData) {
                alert('Générez d\'abord les prévisions (cliquez sur le bouton bleu).');
                return;
            }

            const prevs = Array.isArray(currentData.previsions)
                ? currentData.previsions
                : (currentData.previsions.XGB || []);

            const payload = {
                district: currentData.district,
                algorithme: selAlgo.options[selAlgo.selectedIndex].text,
                horizon: parseInt(selHorizon.value, 10),
                previsions: prevs.map(p => ({
                    horizon: p.horizon,
                    date: p.mois_label,
                    incidence: p.incidence,
                    cas: p.cas,
                    niveau: p.niveau,
                })),
                historique: currentData.historique.map(h => ({
                    date: h.mois_label, incidence: h.incidence
                })),
                metriques: currentData.metriques,
                analyse_ia: currentData.analyse_ia || '',
            };

            btnExportWord.disabled = true;
            btnExportWord.innerHTML = '<span class="loader"></span> Génération...';

            try {
                const res = await fetch('/previsions/api/rapport/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(payload),
                });

                // Vérification du statut HTTP
                if (!res.ok) {
                    let errMsg = `Erreur HTTP ${res.status}`;
                    try {
                        const errData = await res.json();
                        if (errData.error) errMsg = errData.error;
                    } catch (_) { /* réponse non JSON */ }
                    throw new Error(errMsg);
                }

                // Vérifier que c'est bien un fichier Word
                const ctype = res.headers.get('Content-Type') || '';
                if (!ctype.includes('wordprocessingml')) {
                    throw new Error('Le serveur n\'a pas renvoyé un fichier Word.');
                }

                // Récupérer le blob
                const blob = await res.blob();
                if (blob.size < 1000) {
                    throw new Error('Le fichier généré est anormalement petit.');
                }

                // Téléchargement robuste : ajout au DOM avant click
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                const today = new Date().toISOString().slice(0, 10);
                a.href = url;
                a.download = `rapport_${currentData.district_court.replace(/\s+/g, '_')}_${selAlgo.value}_h${selHorizon.value}_${today}.docx`;
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                // Nettoyage après un court délai (laisse le temps au téléchargement)
                setTimeout(() => {
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                }, 200);

                // Feedback visuel
                btnExportWord.innerHTML = '<i class="fa-solid fa-check"></i> Téléchargé';
                setTimeout(() => {
                    btnExportWord.innerHTML = '<i class="fa-solid fa-file-word"></i> Rapport Word';
                    btnExportWord.disabled = false;
                }, 2000);
                return;
            } catch (err) {
                console.error('Erreur export Word :', err);
                alert('Erreur lors de l\'export Word :\n' + err.message);
            } finally {
                if (btnExportWord.disabled && !btnExportWord.innerHTML.includes('Téléchargé')) {
                    btnExportWord.disabled = false;
                    btnExportWord.innerHTML = '<i class="fa-solid fa-file-word"></i> Rapport Word';
                }
            }
        });
    }
})();
