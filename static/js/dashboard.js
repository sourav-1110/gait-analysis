// Dashboard JavaScript

let allData = [];
let charts = {};
let autoRefreshInterval = null;
let autoRefreshEnabled = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard loaded');
    initCharts();
    refreshData();
    checkHealth();
    setInterval(checkHealth, 30000); // Check health every 30 seconds
});

// Initialize all charts
function initCharts() {
    const chartConfig = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: {
                display: true,
                position: 'top',
            },
            title: {
                display: false
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                ticks: {
                    maxTicksLimit: 5
                }
            },
            x: {
                ticks: {
                    maxTicksLimit: 10
                }
            }
        }
    };

    // Velocity Chart
    charts.velocity = new Chart(document.getElementById('velocityChart'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Velocity (m/s)',
                data: [],
                borderColor: '#007bff',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 2,
                pointBackgroundColor: '#007bff'
            }]
        },
        options: chartConfig
    });

    // Cadence Chart
    charts.cadence = new Chart(document.getElementById('cadenceChart'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Cadence (steps/min)',
                data: [],
                borderColor: '#28a745',
                backgroundColor: 'rgba(40, 167, 69, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 2,
                pointBackgroundColor: '#28a745'
            }]
        },
        options: chartConfig
    });

    // Stride Chart
    charts.stride = new Chart(document.getElementById('strideChart'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Stride Length (m)',
                data: [],
                borderColor: '#ffc107',
                backgroundColor: 'rgba(255, 193, 7, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 2,
                pointBackgroundColor: '#ffc107'
            }]
        },
        options: chartConfig
    });

    // Knee Angle Chart
    charts.knee = new Chart(document.getElementById('kneeChart'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Knee Angle (°)',
                data: [],
                borderColor: '#dc3545',
                backgroundColor: 'rgba(220, 53, 69, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 2,
                pointBackgroundColor: '#dc3545'
            }]
        },
        options: chartConfig
    });

    // Thigh Acceleration Chart
    charts.thighAccel = new Chart(document.getElementById('thighAccelChart'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Thigh Accel X (g)',
                    data: [],
                    borderColor: '#17a2b8',
                    tension: 0.4,
                    fill: false,
                    pointRadius: 1,
                    borderWidth: 1
                },
                {
                    label: 'Thigh Accel Y (g)',
                    data: [],
                    borderColor: '#20c997',
                    tension: 0.4,
                    fill: false,
                    pointRadius: 1,
                    borderWidth: 1
                },
                {
                    label: 'Thigh Accel Z (g)',
                    data: [],
                    borderColor: '#6f42c1',
                    tension: 0.4,
                    fill: false,
                    pointRadius: 1,
                    borderWidth: 1
                }
            ]
        },
        options: chartConfig
    });

    // Shank Acceleration Chart
    charts.shankAccel = new Chart(document.getElementById('shankAccelChart'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Shank Accel X (g)',
                    data: [],
                    borderColor: '#fd7e14',
                    tension: 0.4,
                    fill: false,
                    pointRadius: 1,
                    borderWidth: 1
                },
                {
                    label: 'Shank Accel Y (g)',
                    data: [],
                    borderColor: '#e83e8c',
                    tension: 0.4,
                    fill: false,
                    pointRadius: 1,
                    borderWidth: 1
                },
                {
                    label: 'Shank Accel Z (g)',
                    data: [],
                    borderColor: '#007bff',
                    tension: 0.4,
                    fill: false,
                    pointRadius: 1,
                    borderWidth: 1
                }
            ]
        },
        options: chartConfig
    });
}

// Check server health
function checkHealth() {
    fetch('/health')
        .then(response => response.json())
        .then(data => {
            const badge = document.getElementById('status-badge');
            if (data.status === 'ok') {
                badge.className = 'badge bg-success';
                badge.textContent = 'Connected ✓';
            } else {
                badge.className = 'badge bg-danger';
                badge.textContent = 'Disconnected ✗';
            }
        })
        .catch(error => {
            console.error('Health check error:', error);
            document.getElementById('status-badge').className = 'badge bg-danger';
            document.getElementById('status-badge').textContent = 'Error';
        });
}

// Refresh all data
function refreshData() {
    console.log('Refreshing data...');
    document.querySelector('.container-fluid')?.classList.add('updating');
    
    Promise.all([
        fetch('/api/data?limit=100').then(r => r.json()),
        fetch('/api/data/stats').then(r => r.json()),
        fetch('/api/data/latest').then(r => r.json())
    ])
    .then(([dataResp, statsResp, latestResp]) => {
        allData = dataResp.data || [];
        updateCharts();
        updateStats(statsResp, dataResp.total);
        updateLatestData(latestResp);
        
        document.querySelector('.container-fluid')?.classList.remove('updating');
        console.log('Data refreshed');
    })
    .catch(error => {
        console.error('Error refreshing data:', error);
        document.querySelector('.container-fluid')?.classList.remove('updating');
    });
}

// Update all charts with latest data
function updateCharts() {
    if (allData.length === 0) return;

    // Prepare data
    const labels = allData.map(d => d.time_ms).slice(-50);
    const velocities = allData.map(d => d.velocity_mps).slice(-50);
    const cadences = allData.map(d => d.cadence_spm).slice(-50);
    const strides = allData.map(d => d.stride_length_m).slice(-50);
    const kneeAngles = allData.map(d => d.knee_deg).slice(-50);
    const thighAccelX = allData.map(d => d.th_ax_g).slice(-50);
    const thighAccelY = allData.map(d => d.th_ay_g).slice(-50);
    const thighAccelZ = allData.map(d => d.th_az_g).slice(-50);
    const shankAccelX = allData.map(d => d.sh_ax_g).slice(-50);
    const shankAccelY = allData.map(d => d.sh_ay_g).slice(-50);
    const shankAccelZ = allData.map(d => d.sh_az_g).slice(-50);

    // Update Velocity Chart
    charts.velocity.data.labels = labels;
    charts.velocity.data.datasets[0].data = velocities;
    charts.velocity.update();

    // Update Cadence Chart
    charts.cadence.data.labels = labels;
    charts.cadence.data.datasets[0].data = cadences;
    charts.cadence.update();

    // Update Stride Chart
    charts.stride.data.labels = labels;
    charts.stride.data.datasets[0].data = strides;
    charts.stride.update();

    // Update Knee Angle Chart
    charts.knee.data.labels = labels;
    charts.knee.data.datasets[0].data = kneeAngles;
    charts.knee.update();

    // Update Thigh Acceleration Chart
    charts.thighAccel.data.labels = labels;
    charts.thighAccel.data.datasets[0].data = thighAccelX;
    charts.thighAccel.data.datasets[1].data = thighAccelY;
    charts.thighAccel.data.datasets[2].data = thighAccelZ;
    charts.thighAccel.update();

    // Update Shank Acceleration Chart
    charts.shankAccel.data.labels = labels;
    charts.shankAccel.data.datasets[0].data = shankAccelX;
    charts.shankAccel.data.datasets[1].data = shankAccelY;
    charts.shankAccel.data.datasets[2].data = shankAccelZ;
    charts.shankAccel.update();
}

// Update statistics
function updateStats(stats, total) {
    document.getElementById('stat-velocity').textContent = (stats.avg_velocity || 0).toFixed(2) + ' m/s';
    document.getElementById('stat-cadence').textContent = (stats.avg_cadence || 0).toFixed(1) + ' steps/min';
    document.getElementById('stat-stride').textContent = (stats.avg_stride_length || 0).toFixed(3) + ' m';
    document.getElementById('stat-count').textContent = (stats.count || total || 0) + ' records';
}

// Update latest data display
function updateLatestData(data) {
    if (data.message) {
        document.getElementById('latest-data').textContent = 'No data available yet.';
        return;
    }
    
    const formatted = JSON.stringify(data, null, 2);
    document.getElementById('latest-data').textContent = formatted;
}

// Toggle auto-refresh
function toggleAutoRefresh() {
    autoRefreshEnabled = !autoRefreshEnabled;
    const btn = document.querySelector('button:nth-of-type(4)');
    
    if (autoRefreshEnabled) {
        autoRefreshInterval = setInterval(refreshData, 5000);
        document.getElementById('auto-refresh-text').textContent = 'Disable Auto Refresh';
        btn.classList.remove('btn-warning');
        btn.classList.add('btn-danger');
    } else {
        clearInterval(autoRefreshInterval);
        document.getElementById('auto-refresh-text').textContent = 'Enable Auto Refresh';
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-warning');
    }
}

// Go to data view
function goToDataView() {
    window.location.href = '/data';
}

// Export data as CSV
function exportData() {
    fetch('/api/data/export')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
            } else {
                alert('Data exported successfully to: ' + data.file);
                console.log('Exported to:', data.path);
            }
        })
        .catch(error => {
            console.error('Export error:', error);
            alert('Error exporting data');
        });
}
