// Data View JavaScript

let allTableData = [];
let dataTable = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Data view loaded');
    loadData();
    
    // Event listeners
    document.getElementById('records-limit').addEventListener('change', loadData);
});

// Load data from API
function loadData() {
    const limit = document.getElementById('records-limit').value;
    
    fetch(`/api/data?limit=${limit}`)
        .then(response => response.json())
        .then(data => {
            allTableData = data.data || [];
            populateTable();
            updateStats();
        })
        .catch(error => {
            console.error('Error loading data:', error);
            document.getElementById('tableBody').innerHTML = 
                '<tr><td colspan="10" class="text-center text-danger">Error loading data</td></tr>';
        });
}

// Populate data table
function populateTable() {
    const tbody = document.getElementById('tableBody');
    
    if (allTableData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center">No data available</td></tr>';
        return;
    }
    
    tbody.innerHTML = '';
    
    allTableData.forEach((record, index) => {
        const row = document.createElement('tr');
        
        // Calculate accelerations
        const thighAccel = Math.sqrt(
            (record.th_ax_g ?? 0) ** 2 + 
            (record.th_ay_g ?? 0) ** 2 + 
            (record.th_az_g ?? 0) ** 2
        ).toFixed(2);
        
        const shankAccel = Math.sqrt(
            (record.sh_ax_g ?? 0) ** 2 + 
            (record.sh_ay_g ?? 0) ** 2 + 
            (record.sh_az_g ?? 0) ** 2
        ).toFixed(2);
        
        const receivedAt = record.received_at ? new Date(record.received_at).toLocaleString() : '-';
        const stanceText = record.stance ? '✓ Yes' : '✗ No';
        
        row.innerHTML = `
            <td>${record.time_ms || 0}</td>
            <td><strong>${(record.velocity_mps ?? 0).toFixed(2)}</strong></td>
            <td>${(record.cadence_spm ?? 0).toFixed(1)}</td>
            <td>${(record.stride_length_m ?? 0).toFixed(3)}</td>
            <td>${(record.knee_deg ?? 0).toFixed(1)}</td>
            <td>${record.force_raw || 0}</td>
            <td>${stanceText}</td>
            <td>${thighAccel} g</td>
            <td>${shankAccel} g</td>
            <td><small>${receivedAt}</small></td>
        `;
        
        tbody.appendChild(row);
    });
}

// Apply filters
function applyFilters() {
    const minVelocity = parseFloat(document.getElementById('min-velocity').value) || 0;
    
    const filtered = allTableData.filter(record => {
        return record.velocity_mps >= minVelocity;
    });
    
    // Temporarily replace table data
    const original = allTableData;
    allTableData = filtered;
    populateTable();
    updateStats();
    
    // Show filter info
    const info = document.createElement('div');
    info.className = 'alert alert-info mt-3';
    info.innerHTML = `Showing ${filtered.length} of ${original.length} records (Velocity ≥ ${minVelocity} m/s) 
        <button class="btn btn-sm btn-link" onclick="resetFilters()" style="float: right;">Reset Filters</button>`;
    
    const existingAlert = document.querySelector('.alert-info');
    if (existingAlert) existingAlert.remove();
    document.querySelector('.card').parentElement.insertBefore(info, document.querySelector('.card').nextSibling);
}

// Reset filters
function resetFilters() {
    document.getElementById('min-velocity').value = '';
    loadData();
    const alert = document.querySelector('.alert-info');
    if (alert) alert.remove();
}

// Update statistics
function updateStats() {
    if (allTableData.length === 0) {
        document.getElementById('summary-count').textContent = '0';
        document.getElementById('summary-velocity').textContent = '- m/s';
        document.getElementById('summary-cadence').textContent = '- spm';
        document.getElementById('summary-stride').textContent = '- m';
        document.getElementById('summary-min-vel').textContent = '- m/s';
        document.getElementById('summary-max-vel').textContent = '- m/s';
        return;
    }
    
    const velocities = allTableData.map(d => d.velocity_mps);
    const cadences = allTableData.map(d => d.cadence_spm);
    const strides = allTableData.map(d => d.stride_length_m);
    
    const avgVelocity = (velocities.reduce((a, b) => a + b, 0) / velocities.length).toFixed(2);
    const avgCadence = (cadences.reduce((a, b) => a + b, 0) / cadences.length).toFixed(1);
    const avgStride = (strides.reduce((a, b) => a + b, 0) / strides.length).toFixed(3);
    const minVelocity = Math.min(...velocities).toFixed(2);
    const maxVelocity = Math.max(...velocities).toFixed(2);
    
    document.getElementById('summary-count').textContent = allTableData.length;
    document.getElementById('summary-velocity').textContent = avgVelocity + ' m/s';
    document.getElementById('summary-cadence').textContent = avgCadence + ' spm';
    document.getElementById('summary-stride').textContent = avgStride + ' m';
    document.getElementById('summary-min-vel').textContent = minVelocity + ' m/s';
    document.getElementById('summary-max-vel').textContent = maxVelocity + ' m/s';
}
