/* ============================================================
   Carte d'alerte épidémique — Leaflet choroplèthe + panneau latéral
   ============================================================ */

(function () {
    'use strict';

    const $ = (s) => document.querySelector(s);

    let map = null;
    let geojsonLayer = null;
    let currentData = null;

    const COLOR = {
        vert: '#28a745',
        orange: '#fd7e14',
        rouge: '#dc3545',
    };

    const LABEL = {
        vert: '🟢 Normal',
        orange: '🟠 Élevé',
        rouge: '🔴 Critique',
    };

    function initMap() {
        map = L.map('map-alerts', {
            center: [10.7, 14.4],
            zoom: 8,
            scrollWheelZoom: false,
        });

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap',
        }).addTo(map);

        // Légende
        const legend = L.control({ position: 'bottomright' });
        legend.onAdd = function () {
            const div = L.DomUtil.create('div', 'legend-card');
            div.innerHTML = `
                <strong>Niveau d'alerte</strong>
                <div class="legend-item"><span class="legend-color" style="background:#28a745"></span> Normal (&lt; P75)</div>
                <div class="legend-item"><span class="legend-color" style="background:#fd7e14"></span> Élevé (P75 - P90)</div>
                <div class="legend-item"><span class="legend-color" style="background:#dc3545"></span> Critique (≥ P90)</div>
            `;
            return div;
        };
        legend.addTo(map);

        // Charger GeoJSON
        fetch('/static/geojson/extreme_nord_districts.geojson')
            .then(r => r.json())
            .then(geojson => {
                window.__GEOJSON_ALERTS = geojson;
                loadAlertes();
            })
            .catch(err => console.error('Erreur GeoJSON :', err));
    }

    function loadAlertes() {
        const algo = $('#alert-algo').value;
        const horizon = $('#alert-horizon').value;

        const btn = $('#btn-update-alertes');
        btn.disabled = true;
        btn.innerHTML = '<span class="loader"></span> Calcul...';

        $('#alerts-list').innerHTML = '<p class="text-center text-muted" style="padding: var(--space-5);"><span class="loader"></span> Calcul des alertes en cours...</p>';

        fetch(`/alertes/api/alertes/?algo=${algo}&horizon=${horizon}`)
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    alert('Erreur : ' + data.error);
                    return;
                }
                currentData = data;
                renderMap(data);
                renderPanel(data);
                renderResume(data.resume);
                $('#alert-info').textContent = `Algorithme : ${data.algorithme} · Horizon : ${data.horizon} mois`;

                // Mettre à jour le lien export PDF
                $('#btn-export-pdf').href = `/alertes/export-pdf/?algo=${algo}&horizon=${horizon}`;
            })
            .catch(err => alert('Erreur : ' + err.message))
            .finally(() => {
                btn.disabled = false;
                btn.innerHTML = '🔄 Actualiser';
            });
    }

    function renderMap(data) {
        if (!window.__GEOJSON_ALERTS) return;

        const alertesMap = {};
        data.alertes.forEach(a => { alertesMap[a.district] = a; });

        if (geojsonLayer) map.removeLayer(geojsonLayer);

        geojsonLayer = L.geoJSON(window.__GEOJSON_ALERTS, {
            style: function (feature) {
                const nom = feature.properties.district_nom;
                const a = alertesMap[nom];
                return {
                    fillColor: a ? COLOR[a.niveau] : '#e0e0e0',
                    weight: 1.5,
                    color: '#333',
                    fillOpacity: 0.82,
                };
            },
            onEachFeature: function (feature, layer) {
                const nom = feature.properties.district_nom;
                const nomCourt = nom.replace('District ', '');
                const a = alertesMap[nom];

                // Popup détaillé au survol
                if (a) {
                    const popupHtml = `
                        <div style="min-width:200px;">
                            <strong style="color:#0e476e;font-size:13px;">${nom}</strong>
                            <hr style="margin:4px 0;border:0;border-top:1px solid #dee2e6;">
                            <span style="color:${COLOR[a.niveau]}; font-weight:700;">${LABEL[a.niveau]}</span><br>
                            Incidence prédite : <b>${a.incidence_predite.toFixed(2)}</b> /1000<br>
                            Cas attendus : <b>${Math.round(a.cas_predits).toLocaleString('fr-FR')}</b><br>
                            <hr style="margin:4px 0;border:0;border-top:1px solid #dee2e6;">
                            Seuils OMS — P75: ${a.p75.toFixed(2)} · P90: ${a.p90.toFixed(2)}<br>
                            <span style="font-size:11px;color:#5a6878;">Date cible : ${a.mois_label}</span>
                        </div>
                    `;
                    layer.bindPopup(popupHtml, { autoPan: false });
                }

                // Label permanent (nom court)
                layer.bindTooltip(nomCourt, {
                    permanent: true,
                    direction: 'center',
                    className: 'district-label',
                    opacity: 1,
                });

                layer.on({
                    mouseover: e => {
                        e.target.setStyle({ weight: 3, color: '#0e476e', fillOpacity: 0.95 });
                        if (a) e.target.openPopup();
                    },
                    mouseout: e => {
                        geojsonLayer.resetStyle(e.target);
                        e.target.closePopup();
                    },
                });
            }
        }).addTo(map);

        try { map.fitBounds(geojsonLayer.getBounds(), { padding: [20, 20] }); } catch (e) {}
    }

    function renderPanel(data) {
        const container = $('#alerts-list');
        if (!data.alertes.length) {
            container.innerHTML = '<p class="text-center text-muted" style="padding: var(--space-5);">Aucune alerte à afficher.</p>';
            return;
        }
        let html = '';
        data.alertes.forEach(a => {
            html += `
                <div class="alert-item" data-district="${a.district}">
                    <div>
                        <div class="alert-name">
                            <span class="alert-dot ${a.niveau}"></span>${a.district_court}
                        </div>
                        <div class="alert-incidence">${a.mois_label} · ${a.incidence_predite.toFixed(2)} /1000 · ${Math.round(a.cas_predits).toLocaleString('fr-FR')} cas</div>
                    </div>
                    <span class="badge badge-${a.niveau}">${a.niveau.toUpperCase()}</span>
                </div>
            `;
        });
        container.innerHTML = html;

        // Click → zoom sur le district
        container.querySelectorAll('.alert-item').forEach(item => {
            item.addEventListener('click', function () {
                const nom = this.dataset.district;
                if (!geojsonLayer) return;
                geojsonLayer.eachLayer(layer => {
                    if (layer.feature.properties.district_nom === nom) {
                        map.fitBounds(layer.getBounds(), { padding: [50, 50] });
                        layer.openPopup();
                    }
                });
            });
        });
    }

    function renderResume(resume) {
        $('#resume-rouge').textContent = resume.rouge;
        $('#resume-orange').textContent = resume.orange;
        $('#resume-vert').textContent = resume.vert;
        $('#resume-total').textContent = resume.total;
    }

    // ============================================================
    // Init
    // ============================================================
    document.addEventListener('DOMContentLoaded', function () {
        if (typeof L !== 'undefined') initMap();
        $('#btn-update-alertes').addEventListener('click', loadAlertes);
        // Recharger quand l'algo ou l'horizon change
        $('#alert-algo').addEventListener('change', loadAlertes);
        $('#alert-horizon').addEventListener('change', loadAlertes);
        // Auto-chargement à l'ouverture (après le chargement du GeoJSON)
        // -> géré dans initMap() via le .then(loadAlertes)
    });
})();
