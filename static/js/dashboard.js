/* ============================================================
   Dashboard — Carte choroplèthe, séries temporelles, CCF, heatmap
   ============================================================ */

(function () {
    'use strict';

    const $ = (sel) => document.querySelector(sel);
    const filterAnnee = $('#filter-annee');
    const filterDistrict = $('#filter-district');
    const filterVariable = $('#filter-variable');

    let mapIncidence = null;
    let geojsonLayer = null;
    let serieChart = null;
    let ccfChart = null;

    // ============================================================
    // Carte d'incidence (Leaflet + GeoJSON)
    // ============================================================
    function initMap() {
        mapIncidence = L.map('map-incidence', {
            center: [10.7, 14.4],   // Centre Extrême-Nord
            zoom: 8,
            scrollWheelZoom: false,
        });

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap',
            maxZoom: 18,
        }).addTo(mapIncidence);

        // Légende
        const legend = L.control({ position: 'bottomright' });
        legend.onAdd = function () {
            const div = L.DomUtil.create('div', 'legend-card');
            div.innerHTML = `
                <strong>Incidence (/1000)</strong>
                <div class="legend-item"><span class="legend-color" style="background:#fee5d9"></span> &lt; 5</div>
                <div class="legend-item"><span class="legend-color" style="background:#fcae91"></span> 5 - 15</div>
                <div class="legend-item"><span class="legend-color" style="background:#fb6a4a"></span> 15 - 30</div>
                <div class="legend-item"><span class="legend-color" style="background:#de2d26"></span> 30 - 60</div>
                <div class="legend-item"><span class="legend-color" style="background:#a50f15"></span> &gt; 60</div>
            `;
            return div;
        };
        legend.addTo(mapIncidence);

        // Charger le GeoJSON statique
        fetch('/static/geojson/extreme_nord_districts.geojson')
            .then(r => r.json())
            .then(geojson => {
                window.__GEOJSON = geojson;
                loadCarte();
            })
            .catch(err => console.error('Erreur chargement GeoJSON :', err));
    }

    function colorFromIncidence(inc) {
        if (inc >= 60) return '#a50f15';
        if (inc >= 30) return '#de2d26';
        if (inc >= 15) return '#fb6a4a';
        if (inc >= 5) return '#fcae91';
        return '#fee5d9';
    }

    function loadCarte() {
        const annee = filterAnnee.value;
        fetch(`/dashboard/api/carte-incidence/?annee=${annee}`)
            .then(r => r.json())
            .then(data => {
                renderChoroplethe(data);
                $('#carte-annee').textContent = annee;
            })
            .catch(err => console.error(err));
    }

    function renderChoroplethe(data) {
        if (!window.__GEOJSON || !mapIncidence) return;

        const incMap = {};
        data.districts.forEach(d => {
            incMap[d.district] = d;
        });

        if (geojsonLayer) mapIncidence.removeLayer(geojsonLayer);

        geojsonLayer = L.geoJSON(window.__GEOJSON, {
            style: function (feature) {
                const nom = feature.properties.district_nom;
                const d = incMap[nom];
                return {
                    fillColor: d ? colorFromIncidence(d.incidence_moyenne) : '#e0e0e0',
                    weight: 1.5,
                    color: '#555',
                    fillOpacity: 0.78,
                };
            },
            onEachFeature: function (feature, layer) {
                const nom = feature.properties.district_nom;
                const nomCourt = nom.replace('District ', '');
                const d = incMap[nom] || {};

                // Popup détaillé au survol (et au clic)
                const popupHtml = `
                    <div style="min-width:180px;">
                        <strong style="color:#0e476e;font-size:13px;">${nom}</strong><br>
                        <span style="color:#5a6878;font-size:11px;">Année ${data.annee}</span>
                        <hr style="margin:4px 0;border:0;border-top:1px solid #dee2e6;">
                        Incidence moyenne : <b>${d.incidence_moyenne || '—'}</b> /1000<br>
                        Cas total : <b>${(d.cas_total || 0).toLocaleString('fr-FR')}</b><br>
                        Population : <b>${(d.population_moyenne || 0).toLocaleString('fr-FR')}</b>
                    </div>
                `;
                layer.bindPopup(popupHtml, { autoPan: false });

                // Label permanent (nom court) au centre du polygone
                layer.bindTooltip(nomCourt, {
                    permanent: true,
                    direction: 'center',
                    className: 'district-label',
                    opacity: 1,
                });

                layer.on({
                    mouseover: e => {
                        e.target.setStyle({ weight: 3, color: '#0e476e', fillOpacity: 0.9 });
                        e.target.openPopup();
                    },
                    mouseout: e => {
                        geojsonLayer.resetStyle(e.target);
                        e.target.closePopup();
                    },
                });
            },
        }).addTo(mapIncidence);

        try {
            mapIncidence.fitBounds(geojsonLayer.getBounds(), { padding: [20, 20] });
        } catch (e) { /* ignore */ }
    }

    // ============================================================
    // Série temporelle (incidence + climat)
    // ============================================================
    function loadSerie() {
        const districtId = filterDistrict.value;
        if (!districtId) return;

        fetch(`/dashboard/api/serie-district/?district_id=${districtId}`)
            .then(r => r.json())
            .then(data => renderSerie(data))
            .catch(err => console.error(err));
    }

    function renderSerie(data) {
        const labels = data.series.map(s => s.date);
        const inc = data.series.map(s => s.incidence);
        const precip = data.series.map(s => s.precip);
        const temp = data.series.map(s => s.temp_moy);

        if (serieChart) serieChart.destroy();

        const ctx = document.getElementById('chart-serie').getContext('2d');
        serieChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Incidence (/1000)',
                        data: inc,
                        borderColor: '#0e476e',
                        backgroundColor: 'rgba(14, 71, 110, 0.1)',
                        yAxisID: 'y1',
                        tension: 0.25,
                        borderWidth: 2,
                    },
                    {
                        label: 'Précipitations (mm)',
                        data: precip,
                        borderColor: '#1565a0',
                        backgroundColor: 'rgba(21, 101, 160, 0.05)',
                        yAxisID: 'y2',
                        tension: 0.25,
                        borderWidth: 1.5,
                        borderDash: [5, 3],
                    },
                    {
                        label: 'Température (°C)',
                        data: temp,
                        borderColor: '#dc3545',
                        backgroundColor: 'transparent',
                        yAxisID: 'y3',
                        tension: 0.25,
                        borderWidth: 1.5,
                        borderDash: [2, 2],
                        hidden: true,
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                stacked: false,
                scales: {
                    x: { ticks: { maxTicksLimit: 12 } },
                    y1: { type: 'linear', position: 'left', title: { display: true, text: 'Incidence' } },
                    y2: { type: 'linear', position: 'right', title: { display: true, text: 'Précip (mm)' }, grid: { drawOnChartArea: false } },
                    y3: { type: 'linear', position: 'right', display: false },
                },
                plugins: {
                    title: { display: true, text: `${data.district}` },
                    legend: { position: 'top' },
                }
            }
        });
    }

    // ============================================================
    // Corrélation croisée (CCF)
    // ============================================================
    function loadCCF() {
        const districtId = filterDistrict.value;
        const variable = filterVariable.value;
        if (!districtId) return;

        fetch(`/dashboard/api/correlation-croisee/?district_id=${districtId}&variable=${variable}`)
            .then(r => r.json())
            .then(data => renderCCF(data))
            .catch(err => console.error(err));
    }

    function renderCCF(data) {
        if (ccfChart) ccfChart.destroy();

        const ctx = document.getElementById('chart-ccf').getContext('2d');
        const colors = data.lags.map(l => l === data.optimal_lag ? '#ce1126' : '#0e476e');

        ccfChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.lags.map(l => `${l > 0 ? '+' : ''}${l}`),
                datasets: [{
                    label: 'Corrélation',
                    data: data.ccf,
                    backgroundColor: colors,
                    borderColor: colors,
                    borderWidth: 1,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: {
                        display: true,
                        text: `Lag optimal : ${data.optimal_lag > 0 ? '+' : ''}${data.optimal_lag} mois`,
                    },
                },
                scales: {
                    y: {
                        title: { display: true, text: 'Coefficient de corrélation' },
                        min: -1, max: 1,
                    },
                    x: { title: { display: true, text: 'Lag (mois)' } },
                }
            }
        });

        $('#ccf-info').textContent = `Variable : ${data.variable} · Lag optimal : ${data.optimal_lag} mois`;
    }

    // ============================================================
    // Heatmap (rendu HTML simple en table)
    // ============================================================
    function loadHeatmap() {
        fetch('/dashboard/api/heatmap/')
            .then(r => r.json())
            .then(data => renderHeatmap(data))
            .catch(err => console.error(err));
    }

    function renderHeatmap(data) {
        const container = $('#heatmap-container');
        if (!container) return;
        const monthLabels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc'];

        let maxVal = 0;
        data.matrix.forEach(row => row.forEach(v => { if (v > maxVal) maxVal = v; }));

        const colorOf = (v) => {
            if (maxVal === 0) return '#fff';
            const t = Math.min(1, v / maxVal);
            const r = Math.round(255 - (255 - 165) * t);
            const g = Math.round(245 - (245 - 15) * t);
            const b = Math.round(235 - (235 - 21) * t);
            return `rgb(${r},${g},${b})`;
        };

        let html = '<table class="table table-compact" style="min-width: 800px;">';
        html += '<thead><tr><th>District</th>';
        monthLabels.forEach(m => html += `<th style="text-align:center;">${m}</th>`);
        html += '</tr></thead><tbody>';

        data.districts.forEach((dist, i) => {
            html += `<tr><td><strong>${dist}</strong></td>`;
            data.matrix[i].forEach(v => {
                const txt = v ? v.toFixed(1) : '—';
                html += `<td style="background:${colorOf(v)}; text-align:center; font-size:0.78rem;" title="${dist} : ${txt}">${txt}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    // ============================================================
    // Init
    // ============================================================
    document.addEventListener('DOMContentLoaded', function () {
        if (typeof L !== 'undefined') initMap();
        loadSerie();
        loadCCF();
        loadHeatmap();

        filterAnnee.addEventListener('change', loadCarte);
        filterDistrict.addEventListener('change', () => { loadSerie(); loadCCF(); });
        filterVariable.addEventListener('change', loadCCF);
    });
})();
