// Dashboard JS — SSE push edition (no polling)

let allData   = [];
let charts    = {};
let stats     = { velocity: 0, cadence: 0, stride: 0, count: 0 };
// Running sums for incremental stat updates (no re-scan of full array)
let _sumV = 0, _sumC = 0, _sumS = 0;

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    connectSSE();
    checkHealth();
    setInterval(checkHealth, 5000);
});

// ── SSE connection ─────────────────────────────────────────────────────────────
function connectSSE() {
    const src = new EventSource('/stream');
    setBadge('Connecting…', 'warning');

    src.onopen = () => {
        setBadge('Connected ✓', 'success');
        console.log('SSE connected');
    };

    src.onmessage = (e) => {
        const payload = JSON.parse(e.data);

        if (payload.seed) {
            // Initial burst: replace allData, rebuild charts and stats from scratch
            allData = payload.seed;
            _sumV = allData.reduce((a, r) => a + (r.velocity_mps    || 0), 0);
            _sumC = allData.reduce((a, r) => a + (r.cadence_spm      || 0), 0);
            _sumS = allData.reduce((a, r) => a + (r.stride_length_m  || 0), 0);
            redrawCharts();
            updateStatsDisplay();
            updateLatestData(allData[allData.length - 1]);
        } else {
            // Single new row pushed by ESP32
            allData.push(payload);
            _sumV += payload.velocity_mps   || 0;
            _sumC += payload.cadence_spm    || 0;
            _sumS += payload.stride_length_m || 0;
            appendToCharts(payload);
            updateStatsDisplay();
            updateLatestData(payload);
        }
    };

    src.onerror = () => {
        setBadge('Reconnecting…', 'danger');
        // EventSource auto-reconnects; we just update the badge
    };
}

// ── Charts ─────────────────────────────────────────────────────────────────────
const MAX_CHART_POINTS = 100;   // rolling window shown on each chart

function initCharts() {
    const base = {
        responsive: true,
        maintainAspectRatio: true,
        animation: false,
        plugins: { legend: { display: true, position: 'top' } },
        scales: {
            y: { beginAtZero: false, ticks: { maxTicksLimit: 5 } },
            x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } }
        }
    };

    const line = (id, label, color, extra) => new Chart(
        document.getElementById(id), {
            type: 'line',
            data: { labels: [], datasets: [{ label, data: [],
                borderColor: color,
                backgroundColor: color.replace(')', ',0.1)').replace('rgb', 'rgba'),
                tension: 0.3, fill: true, pointRadius: 1, borderWidth: 1.5,
                ...extra }] },
            options: base
        });

    charts.velocity    = line('velocityChart',  'Velocity (m/s)',       'rgb(0,123,255)');
    charts.cadence     = line('cadenceChart',   'Cadence (steps/min)',  'rgb(40,167,69)');
    charts.stride      = line('strideChart',    'Stride Length (m)',    'rgb(255,193,7)');
    charts.knee        = line('kneeChart',      'Knee Angle (°)',       'rgb(220,53,69)');

    // Multi-series IMU charts
    const multiBase = { ...base };
    charts.thighAccel = new Chart(document.getElementById('thighAccelChart'), {
        type: 'line',
        data: { labels: [], datasets: [
            mk('Thigh X (g)', 'rgb(23,162,184)'),
            mk('Thigh Y (g)', 'rgb(32,201,151)'),
            mk('Thigh Z (g)', 'rgb(111,66,193)')
        ]},
        options: multiBase
    });
    charts.shankAccel = new Chart(document.getElementById('shankAccelChart'), {
        type: 'line',
        data: { labels: [], datasets: [
            mk('Shank X (g)', 'rgb(253,126,20)'),
            mk('Shank Y (g)', 'rgb(232,62,140)'),
            mk('Shank Z (g)', 'rgb(0,123,255)')
        ]},
        options: multiBase
    });
}

function mk(label, color) {
    return { label, data: [], borderColor: color,
             tension: 0.3, fill: false, pointRadius: 0, borderWidth: 1.2 };
}

/** Full redraw from allData (called on seed / reset) */
function redrawCharts() {
    const window = allData.slice(-MAX_CHART_POINTS);
    const labels = window.map(d => (d.time_ms / 1000).toFixed(1) + 's');

    setChart(charts.velocity,  labels, [window.map(d => d.velocity_mps    ?? 0)]);
    setChart(charts.cadence,   labels, [window.map(d => d.cadence_spm     ?? 0)]);
    setChart(charts.stride,    labels, [window.map(d => d.stride_length_m ?? 0)]);
    setChart(charts.knee,      labels, [window.map(d => d.knee_deg        ?? 0)]);
    setChart(charts.thighAccel, labels, [
        window.map(d => d.th_ax_g ?? 0),
        window.map(d => d.th_ay_g ?? 0),
        window.map(d => d.th_az_g ?? 0)
    ]);
    setChart(charts.shankAccel, labels, [
        window.map(d => d.sh_ax_g ?? 0),
        window.map(d => d.sh_ay_g ?? 0),
        window.map(d => d.sh_az_g ?? 0)
    ]);
}

function setChart(chart, labels, dataArrays) {
    chart.data.labels = labels;
    dataArrays.forEach((arr, i) => chart.data.datasets[i].data = arr);
    chart.update('none');
}

/** Incremental append — shift oldest point off if at max window */
function appendToCharts(row) {
    const label = (row.time_ms / 1000).toFixed(1) + 's';

    pushPoint(charts.velocity,   label, [row.velocity_mps    ?? 0]);
    pushPoint(charts.cadence,    label, [row.cadence_spm     ?? 0]);
    pushPoint(charts.stride,     label, [row.stride_length_m ?? 0]);
    pushPoint(charts.knee,       label, [row.knee_deg        ?? 0]);
    pushPoint(charts.thighAccel, label, [row.th_ax_g??0, row.th_ay_g??0, row.th_az_g??0]);
    pushPoint(charts.shankAccel, label, [row.sh_ax_g??0, row.sh_ay_g??0, row.sh_az_g??0]);
}

function pushPoint(chart, label, values) {
    const d = chart.data;
    d.labels.push(label);
    values.forEach((v, i) => d.datasets[i].data.push(v));
    // Slide the window
    if (d.labels.length > MAX_CHART_POINTS) {
        d.labels.shift();
        d.datasets.forEach(ds => ds.data.shift());
    }
    chart.update('none');
}

// ── Stats ──────────────────────────────────────────────────────────────────────
function updateStatsDisplay() {
    const n = allData.length || 1;
    document.getElementById('stat-velocity').textContent = (_sumV / n).toFixed(2) + ' m/s';
    document.getElementById('stat-cadence').textContent  = (_sumC / n).toFixed(1) + ' steps/min';
    document.getElementById('stat-stride').textContent   = (_sumS / n).toFixed(3) + ' m';
    document.getElementById('stat-count').textContent    = allData.length + ' records';
}

function updateLatestData(row) {
    if (!row) return;
    document.getElementById('latest-data').textContent = JSON.stringify(row, null, 2);
}

// ── Health badge ───────────────────────────────────────────────────────────────
function setBadge(text, cls) {
    const b = document.getElementById('status-badge');
    b.className = `badge bg-${cls}`;
    b.textContent = text;
}

function checkHealth() {
    fetch('/health').then(r => r.json()).then(d => {
        setBadge(`Connected ✓ (${d.records} records, ${d.sse_clients} live)`, 'success');
    }).catch(() => setBadge('Server unreachable', 'danger'));
}

// ── Controls ───────────────────────────────────────────────────────────────────
function resetDisplay() {
    if (!confirm('Clear all readings and reset dashboard?')) return;
    fetch('/api/reset', { method: 'POST' })
        .then(r => r.json())
        .then(resp => {
            if (resp.status !== 'ok') { alert('Reset failed: ' + (resp.error||'?')); return; }
            allData = []; _sumV = 0; _sumC = 0; _sumS = 0;
            redrawCharts();
            updateStatsDisplay();
            document.getElementById('latest-data').textContent = 'Reset. Waiting for ESP32…';
        })
        .catch(() => alert('Reset failed — check server.'));
}

function exportData() {
    fetch('/api/data/export').then(r => r.json()).then(d => {
        if (d.error) alert('Error: ' + d.error);
        else alert('Exported to: ' + d.file);
    }).catch(() => alert('Export error'));
}

function goToDataView() { window.location.href = '/data'; }

// Kept for HTML button compatibility — SSE auto-updates, button now triggers manual fetch
function refreshData() {
    fetch('/api/data?limit=200').then(r => r.json()).then(resp => {
        allData = resp.data || [];
        _sumV = allData.reduce((a,r)=>a+(r.velocity_mps||0),0);
        _sumC = allData.reduce((a,r)=>a+(r.cadence_spm||0),0);
        _sumS = allData.reduce((a,r)=>a+(r.stride_length_m||0),0);
        redrawCharts();
        updateStatsDisplay();
        if (allData.length) updateLatestData(allData[allData.length-1]);
    });
}

// No-op stubs so old HTML buttons don't throw errors
function toggleAutoRefresh() {
    alert('Auto-refresh is now replaced by live SSE push — data updates instantly.');
}