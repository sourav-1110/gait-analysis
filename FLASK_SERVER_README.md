# Gait Analysis Flask Server with MongoDB & Web Visualization

A comprehensive Flask web server that receives gait analysis data from ESP32 microcontrollers, stores it in MongoDB, and provides real-time visualization through an interactive web dashboard.

## Features

- **Data Collection**: Receive CSV gait data from ESP32 via HTTP POST
- **MongoDB Storage**: Persistent storage of all gait analysis measurements
- **CSV Fallback**: Automatically backs up data to CSV files
- **REST API**: Full REST API for data retrieval, statistics, and export
- **Interactive Dashboard**: Real-time charts and graphs for visualization
- **Data Table View**: Detailed data table with filtering and sorting
- **Auto-Refresh**: Optional automatic data refresh every 5 seconds
- **Statistics**: Calculate and display aggregate statistics
- **Data Export**: Export data to CSV format

## Project Structure

```
gait-analysis/
├── ros/
│   ├── app.py              # Main Flask application
│   ├── config.py           # Configuration settings
│   ├── flask_server.py     # Original flask server (backup)
│   ├── serial_bridge.py    # ROS serial bridge
│   └── tf_broadcaster.py   # ROS TF broadcaster
├── templates/
│   ├── index.html          # Main dashboard
│   └── data.html           # Data table view
├── static/
│   ├── css/
│   │   └── style.css       # Dashboard styling
│   └── js/
│       ├── dashboard.js    # Dashboard functionality
│       └── data-view.js    # Data table functionality
├── readings/               # CSV file storage
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Installation

### Prerequisites

- Python 3.8+
- MongoDB (local or remote instance)
- pip (Python package manager)

### Step 1: Install MongoDB

**Windows:**
Download and install from: https://www.mongodb.com/try/download/community

**Linux/Mac:**
```bash
brew install mongodb-community  # macOS
# or
sudo apt-get install mongodb    # Ubuntu/Debian
```

**Using Docker:**
```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### Step 2: Install Python Dependencies

```bash
# Navigate to the project directory
cd "path/to/gait analysis"

# Install dependencies
pip install -r requirements.txt
```

If you encounter issues, install each package individually:
```bash
pip install Flask==2.3.0
pip install Werkzeug==2.3.0
pip install pymongo==4.4.1
pip install python-dotenv==1.0.0
pip install pyserial==3.5
```

### Step 3: Run MongoDB (if not already running)

```bash
# Local MongoDB
mongod

# Or in Docker
docker start mongodb
```

### Step 4: Run the Flask Server

```bash
cd ros
python app.py
```

You should see output like:
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

## Usage

### Web Dashboard

Open your browser and navigate to:
```
http://localhost:5000/
```

Features:
- Real-time statistics cards (velocity, cadence, stride length, record count)
- Interactive line charts for gait metrics
- IMU acceleration data visualization
- Data table view with filtering
- Auto-refresh toggle
- Export to CSV

### Data Table View

Navigate to:
```
http://localhost:5000/data
```

Features:
- Sortable and filterable data table
- Minimum velocity filter
- Summary statistics
- Adjustable record display limit

### REST API Endpoints

#### Health Check
```
GET /health
```
Returns server status and MongoDB connection status.

#### Log Data
```
POST /api/log_data
Content-Type: text/plain

time_ms,th_qw,th_qx,th_qy,th_qz,th_ax_g,th_ay_g,th_az_g,...
```

Receive and store gait analysis CSV data from ESP32.

#### Get All Data
```
GET /api/data?limit=100&skip=0
```

Get paginated gait analysis data.

**Response:**
```json
{
    "total": 1000,
    "returned": 100,
    "data": [
        {
            "time_ms": 12345,
            "th_qw": 0.9950,
            "velocity_mps": 1.45,
            "cadence_spm": 120,
            "stride_length_m": 0.725,
            "knee_deg": 45.2,
            "force_raw": 512,
            "stance": true,
            "received_at": "2024-06-10T10:30:45.123Z"
        }
    ]
}
```

#### Get Latest Data
```
GET /api/data/latest
```

Get the most recent gait analysis record.

#### Get Statistics
```
GET /api/data/stats
```

Get aggregate statistics.

**Response:**
```json
{
    "avg_velocity": 1.32,
    "avg_cadence": 118.5,
    "avg_stride_length": 0.71,
    "avg_knee_angle": 42.3,
    "max_velocity": 2.1,
    "min_velocity": 0.8,
    "count": 1000
}
```

#### Export Data
```
GET /api/data/export
```

Export all data to CSV file.

#### Clear Data
```
DELETE /api/data/clear?token=admin123
```

Clear all data from MongoDB (requires admin token).

## MongoDB Schema

Each gait analysis record contains:

```javascript
{
    "_id": ObjectId,
    "time_ms": Number,
    "th_qw": Number,           // Thigh quaternion
    "th_qx": Number,
    "th_qy": Number,
    "th_qz": Number,
    "th_ax_g": Number,         // Thigh acceleration (g)
    "th_ay_g": Number,
    "th_az_g": Number,
    "th_gx_dps": Number,       // Thigh gyro (dps)
    "th_gy_dps": Number,
    "th_gz_dps": Number,
    "sh_qw": Number,           // Shank quaternion
    "sh_qx": Number,
    "sh_qy": Number,
    "sh_qz": Number,
    "sh_ax_g": Number,         // Shank acceleration (g)
    "sh_ay_g": Number,
    "sh_az_g": Number,
    "sh_gx_dps": Number,       // Shank gyro (dps)
    "sh_gy_dps": Number,
    "sh_gz_dps": Number,
    "knee_deg": Number,        // Knee angle
    "force_raw": Number,       // Force sensor reading
    "stance": Boolean,         // Stance phase indicator
    "stride_length_m": Number,
    "velocity_mps": Number,
    "cadence_spm": Number,     // Steps per minute
    "stance_time_s": Number,
    "swing_time_s": Number,
    "received_at": Date        // Server timestamp
}
```

## ESP32 Configuration

Update the ESP32 code in `src/main.cpp` to send data to your server:

```cpp
const char* SERVER_IP  = "192.168.X.X";  // Your laptop IP
const int   SERVER_PORT     = 5000;
const char* SERVER_ENDPOINT = "/api/log_data";
```

The ESP32 sends CSV data via POST request:
```
POST /api/log_data HTTP/1.1
Host: 192.168.X.X:5000
Content-Type: text/plain

12345,0.9950,0.0050,0.0100,-0.0050,0.15,-0.02,1.05,2.1,-0.5,0.3,...
```

## Configuration

Edit `ros/config.py` to customize:

```python
# Flask settings
HOST = '0.0.0.0'           # Server address
PORT = 5000                # Server port
DEBUG = True               # Debug mode

# MongoDB settings
MONGO_URI = 'mongodb://localhost:27017/'
MONGO_DB = 'gait_analysis'
MONGO_COLLECTION = 'gait_data'

# CSV settings
CSV_OUTPUT_DIR = './readings'
CSV_FILENAME = f'gait_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

# Admin token (change in production)
ADMIN_TOKEN = 'admin123'
```

## Troubleshooting

### MongoDB Connection Error
- Ensure MongoDB is running: `mongod`
- Check URI in `config.py`
- Verify firewall allows port 27017

### Flask Server Won't Start
- Check if port 5000 is already in use
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Try a different port in `config.py`

### Data Not Appearing
- Check Flask server logs for errors
- Verify ESP32 is sending to correct IP and port
- Check MongoDB connection status at `/health`
- Verify CSV data format matches header

### Charts Not Loading
- Check browser console (F12) for JavaScript errors
- Ensure JavaScript files are loading: Check static/js/
- Try hard refresh (Ctrl+Shift+R or Cmd+Shift+R)

## Production Deployment

For production use:

1. Set `DEBUG = False` in `config.py`
2. Change `ADMIN_TOKEN` to a strong random token
3. Use environment variables for sensitive data
4. Deploy with gunicorn: `pip install gunicorn && gunicorn app:app`
5. Use reverse proxy (nginx) for HTTPS
6. Set up MongoDB authentication
7. Configure firewall rules

## Performance Tips

- Create MongoDB index on `time_ms` field for faster queries
- Limit displayed records in dashboard (default: 100)
- Archive old data to separate collection periodically
- Use MongoDB sharding for large datasets

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review logs in Flask server output
3. Check MongoDB status with `mongo` command
4. Verify data format from ESP32

## Development

To modify the dashboard:
- Edit HTML in `templates/`
- Update CSS in `static/css/style.css`
- Modify JavaScript in `static/js/`
- Update Flask routes in `ros/app.py`

Restart Flask server after code changes (or use `DEBUG = True` for auto-reload).
