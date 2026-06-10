# Getting Started - Gait Analysis with Flask, MongoDB, and Web Visualization

## Quick Overview

This guide walks you through setting up and running the complete gait analysis system with:
- **Flask Server**: Receives and stores gait data
- **MongoDB Database**: Persistent data storage
- **Interactive Dashboard**: Real-time visualization and analysis

## 5-Minute Quick Start

### Prerequisites
- Python 3.8+ installed
- MongoDB running locally (or Docker)

### Windows (Quick Start)

**Option A: Batch File (Easiest)**
```bash
cd "C:\Users\SOURAV S\OneDrive\Documents\PlatformIO\Projects\gait analysis\ros"
START_SERVER.bat
```

**Option B: PowerShell**
```powershell
cd "C:\Users\SOURAV S\OneDrive\Documents\PlatformIO\Projects\gait analysis\ros"
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
.\START_SERVER.ps1
```

**Option C: Python Script**
```bash
cd ros
python quickstart.py
```

**Option D: Manual**
```bash
cd "C:\Users\SOURAV S\OneDrive\Documents\PlatformIO\Projects\gait analysis\ros"
python -m pip install -r requirements.txt
python app.py
```

### Linux/Mac (Quick Start)

```bash
cd "path/to/gait analysis/ros"
pip install -r requirements.txt
python app.py
```

## Step-by-Step Setup

### Step 1: Ensure MongoDB is Running

**Windows - Using MongoDB Service**
```bash
mongod
```
Leave this terminal open.

**Windows - Using Docker**
```bash
docker run -d -p 27017:27017 --name gait-mongo mongo:latest
```

**Linux/Mac**
```bash
brew services start mongodb-community  # macOS
# or
sudo systemctl start mongod            # Linux
```

### Step 2: Install Python Dependencies

```bash
cd ros
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed Flask-2.3.0 Werkzeug-2.3.0 pymongo-4.4.1 ...
```

### Step 3: Start the Flask Server

```bash
python app.py
```

**Expected output:**
```
==================================================
Flask Gait Analysis Server with MongoDB
==================================================
MongoDB URI: mongodb://localhost:27017/
Database: gait_analysis
Collection: gait_data
CSV Output: C:\...\readings
==================================================

 * Running on http://0.0.0.0:5000
```

### Step 4: Access the Dashboard

Open your web browser and go to:
```
http://localhost:5000/
```

You should see:
- 4 stat cards (Velocity, Cadence, Stride Length, Record Count)
- 6 interactive charts
- Control buttons
- Latest data display

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│          ESP32 Microcontroller (Gait Analysis)             │
│  - IMU sensors (thigh & shank)                             │
│  - Force sensor                                            │
│  - Calculates stride metrics                               │
│                                                             │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP POST
                           │ CSV Format
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│       Flask Server (app.py)                                │
│  - Receives CSV data from ESP32                            │
│  - Validates and converts to JSON                          │
│  - Stores in MongoDB                                       │
│  - Backs up to CSV files                                   │
│  - Provides REST API                                       │
│                                                             │
└──────┬──────────────────────────────────────┬───────────────┘
       │                                      │
       │ NoSQL                               │ CSV Files
       ▼                                      ▼
┌────────────────────┐                 ┌─────────────────┐
│   MongoDB Database │                 │ readings/       │
│                    │                 │ *.csv           │
│ gait_analysis      │                 │                 │
│ └─ gait_data       │                 │ (Backup)        │
└────────────────────┘                 └─────────────────┘
       │
       │ REST API
       ▼
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│          Web Dashboard (Browser)                           │
│  - index.html: Main visualization dashboard               │
│  - data.html: Data table view                              │
│  - Chart.js: Real-time charts                              │
│  - Bootstrap: Responsive design                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Using the Dashboard

### Main Dashboard (http://localhost:5000/)

**Statistics Cards** (top row)
- **Avg Walking Velocity**: Average movement speed (m/s)
- **Avg Cadence**: Average step rate (steps/minute)
- **Avg Stride Length**: Average distance per step (m)
- **Total Records**: Number of stored measurements

**Charts** (interactive, hover for details)
- Walking Velocity Over Time
- Cadence Over Time
- Stride Length Over Time
- Knee Angle Over Time
- Thigh IMU Acceleration (X, Y, Z)
- Shank IMU Acceleration (X, Y, Z)

**Controls**
- **Refresh Data**: Update dashboard immediately
- **View Data Table**: Go to detailed data view
- **Export as CSV**: Download all data to file
- **Enable Auto Refresh**: Automatically update every 5 seconds

### Data Table View (http://localhost:5000/data)

**Features**
- Sortable columns
- Velocity filter (minimum value)
- Adjustable record limit (50-1000)
- Summary statistics
- Pagination

**Column Details**
- Time (ms): Timestamp since start
- Velocity (m/s): Walking speed
- Cadence (spm): Steps per minute
- Stride Length (m): Distance per step
- Knee Angle (°): Joint angle
- Force Raw: Pressure sensor reading
- Stance: Phase of gait (Y/N)
- Thigh Accel (g): Magnitude of acceleration
- Shank Accel (g): Magnitude of acceleration
- Received At: Server timestamp

## API Endpoints Reference

### Health Check
```
GET http://localhost:5000/health
```
Returns: `{"status": "ok", "mongodb": "connected"}`

### Log Data (from ESP32)
```
POST http://localhost:5000/api/log_data
Content-Type: text/plain

12345,0.9950,0.0050,...
```

### Get Data
```
GET http://localhost:5000/api/data?limit=100&skip=0
```

### Get Latest Record
```
GET http://localhost:5000/api/data/latest
```

### Get Statistics
```
GET http://localhost:5000/api/data/stats
```

### Export to CSV
```
GET http://localhost:5000/api/data/export
```

### Clear All Data
```
DELETE http://localhost:5000/api/data/clear?token=admin123
```

## Configure ESP32 to Send Data

Edit `src/main.cpp` and update:

```cpp
const char* SERVER_IP  = "192.168.X.X";  // Your computer's IP
const int   SERVER_PORT     = 5000;
const char* SERVER_ENDPOINT = "/api/log_data";
```

Find your computer's IP:
- **Windows**: Run `ipconfig` and look for "IPv4 Address"
- **Linux/Mac**: Run `ifconfig` and look for "inet"

## Troubleshooting

### MongoDB Won't Connect
```bash
# Check if MongoDB is running
mongod

# Or start with Docker
docker run -d -p 27017:27017 mongo:latest

# Test connection
python -c "from pymongo import MongoClient; MongoClient().admin.command('ping')"
```

### Port 5000 Already in Use
```python
# Edit ros/config.py
PORT = 5001  # Use different port
```

### Flask Can't Find Templates
```bash
# Make sure you're in the ros directory
cd ros
python app.py
```

### Data Not Appearing on Dashboard
1. Check Flask console for errors
2. Verify ESP32 is sending to correct IP:port
3. Check /health endpoint
4. Verify data format matches CSV header

### Browser Shows Blank Page
- Hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
- Check browser console (F12) for JavaScript errors
- Verify all files in `templates/` and `static/` exist

## Next Steps

1. **Collect Real Data**
   - Deploy ESP32 with sensors
   - Connect to WiFi
   - Start data collection

2. **Analyze Results**
   - Use data table to find patterns
   - Export CSV for analysis
   - Compare different sessions

3. **Custom Visualizations**
   - Modify `static/js/dashboard.js`
   - Add new charts for specific metrics
   - Create session comparison tools

4. **Backup Data**
   ```bash
   # MongoDB backup
   mongodump --out backup_folder
   
   # Restore
   mongorestore backup_folder
   ```

## Performance Tips

- Close unused browser tabs
- Use Firefox or Chrome for best performance
- Limit dashboard to 100 recent records
- Archive old data periodically
- Monitor MongoDB disk usage

## File Locations

```
gait analysis/
├── ros/
│   ├── app.py              ← Main server (EDIT HERE)
│   ├── config.py           ← Settings (EDIT HERE)
│   ├── START_SERVER.bat    ← Windows quick start
│   ├── START_SERVER.ps1    ← PowerShell quick start
│   └── quickstart.py       ← Python quick start
├── templates/
│   ├── index.html          ← Main dashboard
│   └── data.html           ← Data table
├── static/
│   ├── css/style.css       ← Styling
│   └── js/
│       ├── dashboard.js    ← Charts & updates
│       └── data-view.js    ← Table functionality
├── readings/               ← CSV backup files
└── FLASK_SERVER_README.md  ← Detailed documentation
```

## Need Help?

1. Read FLASK_SERVER_README.md for detailed docs
2. Check `/health` endpoint for server status
3. Look at browser console (F12) for client-side errors
4. Check Flask server console for backend errors
5. Verify MongoDB is running with `mongod`

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "No module named pymongo" | `pip install pymongo` |
| MongoDB connection error | Start `mongod` in separate terminal |
| Port 5000 in use | Change PORT in config.py |
| Dashboard won't load | Hard refresh browser (Ctrl+Shift+R) |
| No data appearing | Check ESP32 IP address in main.cpp |
| Charts empty | Ensure data is being received via /health |

## Quick Reference

**Start server:**
- Windows Batch: `START_SERVER.bat`
- PowerShell: `SET-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process; .\START_SERVER.ps1`
- Python: `python app.py`

**Open dashboard:**
- Main: http://localhost:5000/
- Data Table: http://localhost:5000/data
- API Health: http://localhost:5000/health

**Stop server:**
- Press Ctrl+C in terminal

**View recent logs:**
- Check Flask console output

**Export data:**
- Dashboard → Export as CSV button
- Or: `GET http://localhost:5000/api/data/export`

## Version Info

- Flask 2.3.0
- MongoDB (any recent version)
- Python 3.8+
- Chart.js 3.9.1
- Bootstrap 5.3.0

Happy gait analysis! 🚶‍♂️
