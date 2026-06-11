// Dashboard JavaScript

let allData = [];
let charts = {};
let autoRefreshInterval = null;
let autoRefreshEnabled = false;

document.addEventListener('DOMContentLoaded', function () {
    console.log('Dashboard loaded');
    initCharts();
    refreshData();
    checkHealth();
    setInterval(checkHealth, 5000);

    // Auto-start refreshing every 3 seconds
    autoRefreshEnabled = true;
    autoRefreshInterval = setInterval(refreshData, 3000);
    document.getElementById('auto-refresh-text').textContent = 'Disable Auto Refresh';
    const btn = document.getElementById('auto-refresh-btn');
    btn.classList.remove('btn-warning');
    btn.classList.add('btn-danger');
});

function initCharts() {
    const chartConfig = {
        responsive: true,
        maintainAspectRatio: true,
        animation: false,
        plugins: { legend: { display: true, position: 'top' } },
        scales: {
            y: { beginAtZero: true, ticks: { maxTicksLimit: 5 } },
            x: { ticks: { maxTicksLimit: 10 } }
        }
    };

    charts.velocity = new Chart(document.getElementById('velocityChart'), {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Velocity (m/s)', data: [], borderColor: '#007bff', backgroundColor: 'rgba(0,123,255,0.1)', tension: 0.4, fill: true, pointRadius: 2 }] },
        options: chartConfig
    });
    charts.cadence = new Chart(document.getElementById('cadenceChart'), {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Cadence (steps/min)', data: [], borderColor: '#28a745', backgroundColor: 'rgba(40,167,69,0.1)', tension: 0.4, fill: true, pointRadius: 2 }] },
        options: chartConfig
    });
    charts.stride = new Chart(document.getElementById('strideChart'), {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Stride Length (m)', data: [], borderColor: '#ffc107', backgroundColor: 'rgba(255,193,7,0.1)', tension: 0.4, fill: true, pointRadius: 2 }] },
        options: chartConfig
    });
    charts.knee = new Chart(document.getElementById('kneeChart'), {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Knee Angle (°)', data: [], borderColor: '#dc3545', backgroundColor: 'rgba(220,53,69,0.1)', tension: 0.4, fill: true, pointRadius: 2 }] },
        options: chartConfig
    });
    charts.thighAccel = new Chart(document.getElementById('thighAccelChart'), {
        type: 'line',
        data: { labels: [], datasets: [
            { label: 'Thigh X (g)', data: [], borderColor: '#17a2b8', tension: 0.4, fill: false, pointRadius: 1, borderWidth: 1 },
            { label: 'Thigh Y (g)', data: [], borderColor: '#20c997', tension: 0.4, fill: false, pointRadius: 1, borderWidth: 1 },
            { label: 'Thigh Z (g)', data: [], borderColor: '#6f42c1', tension: 0.4, fill: false, pointRadius: 1, borderWidth: 1 }
        ]},
        options: chartConfig
    });
    charts.shankAccel = new Chart(document.getElementById('shankAccelChart'), {
        type: 'line',
        data: { labels: [], datasets: [
            { label: 'Shank X (g)', data: [], borderColor: '#fd7e14', tension: 0.4, fill: false, pointRadius: 1, borderWidth: 1 },
            { label: 'Shank Y (g)', data: [], borderColor: '#e83e8c', tension: 0.4, fill: false, pointRadius: 1, borderWidth: 1 },
            { label: 'Shank Z (g)', data: [], borderColor: '#007bff', tension: 0.4, fill: false, pointRadius: 1, borderWidth: 1 }
        ]},
        options: chartConfig
    });
}

function checkHealth() {
    fetch('/health')
        .then(r => r.json())
        .then(data => {
            const badge = document.getElementById('status-badge');
            if (data.status === 'ok') {
                badge.className = 'badge bg-success';
                badge.textContent = `Connected ✓ (${data.records} records)`;
            } else {
                badge.className = 'badge bg-danger';
                badge.textContent = 'Disconnected ✗';
            }
        })
        .catch(() => {
            document.getElementById('status-badge').className = 'badge bg-danger';
            document.getElementById('status-badge').textContent = 'Error';
        });
}

function refreshData() {
    // Always fetch latest 200 rows — no offset slicing
    fetch('/api/data?limit=200')
        .then(r => r.json())
        .then(dataResp => {
            allData = dataResp.data || [];

            Promise.all([
                fetch('/api/data/stats').then(r => r.json()),
                fetch('/api/data/latest').then(r => r.json())
            ]).then(([statsResp, latestResp]) => {
                updateCharts(allData);
                updateStats(statsResp, dataResp.total);
                updateLatestData(latestResp);
            });
        })
        .catch(error => console.error('Error refreshing data:', error));
}

function updateCharts(data) {
    // Show placeholder message if no data yet, but don't bail — clear charts cleanly
    if (!data || data.length === 0) {
        Object.values(charts).forEach(chart => {
            chart.data.labels = [];
            chart.data.datasets.forEach(ds => ds.data = []);
            chart.update('none');
        });
        return;
    }

    const recent = data.slice(-50);
    const labels = recent.map(d => (d.time_ms / 1000).toFixed(1) + 's');

    charts.velocity.data.labels = labels;
    charts.velocity.data.datasets[0].data = recent.map(d => d.velocity_mps ?? 0);
    charts.velocity.update('none');

    charts.cadence.data.labels = labels;
    charts.cadence.data.datasets[0].data = recent.map(d => d.cadence_spm ?? 0);
    charts.cadence.update('none');

    charts.stride.data.labels = labels;
    charts.stride.data.datasets[0].data = recent.map(d => d.stride_length_m ?? 0);
    charts.stride.update('none');

    charts.knee.data.labels = labels;
    charts.knee.data.datasets[0].data = recent.map(d => d.knee_deg ?? 0);
    charts.knee.update('none');

    charts.thighAccel.data.labels = labels;
    charts.thighAccel.data.datasets[0].data = recent.map(d => d.th_ax_g ?? 0);
    charts.thighAccel.data.datasets[1].data = recent.map(d => d.th_ay_g ?? 0);
    charts.thighAccel.data.datasets[2].data = recent.map(d => d.th_az_g ?? 0);
    charts.thighAccel.update('none');

    charts.shankAccel.data.labels = labels;
    charts.shankAccel.data.datasets[0].data = recent.map(d => d.sh_ax_g ?? 0);
    charts.shankAccel.data.datasets[1].data = recent.map(d => d.sh_ay_g ?? 0);
    charts.shankAccel.data.datasets[2].data = recent.map(d => d.sh_az_g ?? 0);
    charts.shankAccel.update('none');
}

function updateStats(stats, total) {
    document.getElementById('stat-velocity').textContent = (stats.avg_velocity      || 0).toFixed(2) + ' m/s';
    document.getElementById('stat-cadence').textContent  = (stats.avg_cadence       || 0).toFixed(1) + ' steps/min';
    document.getElementById('stat-stride').textContent   = (stats.avg_stride_length || 0).toFixed(3) + ' m';
    document.getElementById('stat-count').textContent    = (total || 0) + ' records';
}

function updateLatestData(data) {
    if (!data || data.message) {
        document.getElementById('latest-data').textContent = 'No data yet — waiting for ESP32...';
        return;
    }
    document.getElementById('latest-data').textContent = JSON.stringify(data, null, 2);
}

// ── Reset: delete CSV on server, clear cache, start fresh ────────────────────
function resetDisplay() {
    if (!confirm('This will DELETE the current CSV file and reset all readings. Continue?')) return;

    fetch('/api/reset', { method: 'POST' })
        .then(r => r.json())
        .then(resp => {
            if (resp.status !== 'ok') {
                alert('Reset failed: ' + (resp.error || 'unknown error'));
                return;
            }

            // Clear client state
            allData = [];

            // Clear all charts
            Object.values(charts).forEach(chart => {
                chart.data.labels = [];
                chart.data.datasets.forEach(ds => ds.data = []);
                chart.update('none');
            });

            // Reset stat cards
            document.getElementById('stat-velocity').textContent = '0.00 m/s';
            document.getElementById('stat-cadence').textContent  = '0.0 steps/min';
            document.getElementById('stat-stride').textContent   = '0.000 m';
            document.getElementById('stat-count').textContent    = '0 records';
            document.getElementById('latest-data').textContent   = 'Reset complete. Waiting for ESP32 data...';
            document.getElementById('status-badge').className    = 'badge bg-success';
            document.getElementById('status-badge').textContent  = 'Connected ✓ (0 records)';

            // Restart auto-refresh cleanly
            clearInterval(autoRefreshInterval);
            autoRefreshEnabled = true;
            autoRefreshInterval = setInterval(refreshData, 3000);
            document.getElementById('auto-refresh-text').textContent = 'Disable Auto Refresh';
            document.getElementById('auto-refresh-btn').classList.remove('btn-warning');
            document.getElementById('auto-refresh-btn').classList.add('btn-danger');

            console.log('Reset complete. New CSV:', resp.new_file);
        })
        .catch(err => {
            console.error('Reset error:', err);
            alert('Reset failed — check server connection.');
        });
}

function toggleAutoRefresh() {
    autoRefreshEnabled = !autoRefreshEnabled;
    const btn = document.getElementById('auto-refresh-btn');
    if (autoRefreshEnabled) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = setInterval(refreshData, 3000);
        document.getElementById('auto-refresh-text').textContent = 'Disable Auto Refresh';
        btn.classList.remove('btn-warning');
        btn.classList.add('btn-danger');
    } else {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        document.getElementById('auto-refresh-text').textContent = 'Enable Auto Refresh';
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-warning');
    }
}

function goToDataView() { window.location.href = '/data'; }

function exportData() {
    fetch('/api/data/export')
        .then(r => r.json())
        .then(data => {
            if (data.error) alert('Error: ' + data.error);
            else alert('Exported to: ' + data.file);
        })
        .catch(() => alert('Error exporting data'));
}
