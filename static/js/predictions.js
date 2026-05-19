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
        vert: '<span class="badge badge-vert">🟢 Normal</span>',
        orange: '<span class="badge badge-orange">🟠 Élevé</span>',
        rouge: '<span class="badge badge-rouge">🔴 Critique</span>',
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
                btnPredict.innerHTML = '🔮 Générer les prévisions';
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
                <td>${p.p75.toFixed(2)}</td>
                <td>${p.p90.toFixed(2)}</td>
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

        // Connecter la dernière obs à la première prévision
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
            }
        ];

        const buildPredArray = (list) => {
            const arr = new Array(histInc.length - 1).fill(null);
            arr.push(connectorLast);  // connecter visuellement
            list.forEach(p => arr.push(p.incidence));
            // pad
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
            });
            if (prevListXGB) datasets.push({
                label: 'Prévision XGBoost',
                data: buildPredArray(prevListXGB),
                borderColor: '#A23B72',
                borderWidth: 2,
                borderDash: [3, 3],
                tension: 0.25,
                pointRadius: 6,
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
                $('#ai-placeholder').style.display = 'none';
                $('#ai-result').style.display = 'block';
                $('#ai-source').textContent = data.source === 'gemini' ? 'Google Gemini' : 'analyse locale';
                $('#ai-content').innerHTML = formatAnalyse(data.analyse);
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
        btnExportWord.addEventListener('click', function () {
            if (!currentData) { alert('Générez d\'abord les prévisions.'); return; }

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
                historique: currentData.historique.map(h => ({ date: h.mois_label, incidence: h.incidence })),
                metriques: currentData.metriques,
                analyse_ia: currentData.analyse_ia || '',
            };

            btnExportWord.disabled = true;
            btnExportWord.innerHTML = '<span class="loader"></span> Génération...';

            fetch('/previsions/api/rapport/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify(payload),
            })
                .then(r => r.blob())
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `rapport_${currentData.district_court}_${new Date().toISOString().slice(0,10)}.docx`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                })
                .catch(err => alert('Erreur export Word : ' + err.message))
                .finally(() => {
                    btnExportWord.disabled = false;
                    btnExportWord.innerHTML = '📝 Rapport Word';
                });
        });
    }
})();
