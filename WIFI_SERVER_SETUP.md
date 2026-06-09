# Gait Analysis System - WiFi & Flask Server Setup

## Overview
The gait analysis firmware now sends sensor data to a Flask server via WiFi, which automatically saves the data to a CSV file. This allows real-time data logging and remote monitoring.

## Setup Instructions

### 1. Python Flask Server Setup

**On your PC (where you want to store the data):**

1. Install Python 3.7+ if not already installed
2. Install Flask server dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Find your PC's IP address:
   - **Windows**: Open Command Prompt and run `ipconfig` (look for "IPv4 Address" under your WiFi adapter, usually something like 192.168.x.x)
   - **Linux/Mac**: Open Terminal and run `ifconfig` or `ip addr`

4. Start the Flask server:
   ```bash
   python ros/flask_server.py
   ```
   
   You should see output like:
   ```
   ==================================================
   Flask Gait Analysis Server Starting
   CSV Output: gait_data\gait_data_20240609_120000.csv
   Data Points: 0
   ==================================================
   ```

### 2. ESP32 Firmware Configuration

**In VS Code (Arduino IDE):**

1. Open [src/main.cpp](src/main.cpp)

2. Find these lines near the top:
   ```cpp
   const char* SSID = "YOUR_SSID";           // Your WiFi network name
   const char* PASSWORD = "YOUR_PASSWORD";   // Your WiFi password
   const char* SERVER_IP = "192.168.1.100";  // Your PC's IP address
   const int SERVER_PORT = 5000;
   ```

3. Update with your WiFi credentials and PC's IP address:
   - `SSID`: Your WiFi network name
   - `PASSWORD`: Your WiFi password
   - `SERVER_IP`: Your PC's IP address (from step 1.3 above)
   - `SERVER_PORT`: Keep as 5000 (matches Flask server)

4. Save the file

### 3. Build and Upload

1. Build the project: `Ctrl+Alt+B` (or run "Build" task)
2. Upload to board: `Ctrl+Alt+U` (or run "Upload" task)
3. Monitor: `Ctrl+Alt+J` (or run "Monitor" task)

### 4. Verify Connection

In the Serial Monitor, you should see:
```
>>> BOARD IS ALIVE <<<
Initializing Gait Analysis System...

--- WiFi Setup ---
Connecting to WiFi: YOUR_SSID
WiFi connected!
IP address: 192.168.x.x

--- I2C & Sensors Setup ---
=== I2C Device Scan ===
Found device at 0x68
Found device at 0x69
Total devices found: 2
...
```

When data is being sent to the server, you'll see:
```
✓ Data sent to server
```

If there's a connection error:
```
✗ Server error: 0
```

### 5. Accessing Collected Data

- **CSV files** are saved in: `gait_data/` folder with timestamp-based names
- **Check server status**: Open browser and go to `http://127.0.0.1:5000/get_status`
  - Returns: file name, size, number of data points collected

### 6. Flask Server Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check - returns `{"status": "ok"}` |
| `/log_data_csv` | POST | Receive CSV row as plain text and append to file |
| `/get_status` | GET | Get current logging status and file info |

### Troubleshooting

**ESP32 won't connect to WiFi:**
- Verify SSID and PASSWORD are correct (case-sensitive)
- Check 2.4GHz WiFi is available (ESP32 doesn't support 5GHz)
- Check signal strength near the board

**Data not reaching server:**
- Verify PC's IP address is correct (use `ipconfig` again)
- Check Flask server is running (should print startup message)
- Check firewall isn't blocking port 5000
- Verify both devices are on the same WiFi network

**Server throws error 0:**
- This typically means the server endpoint is unreachable
- Check PC's IP address in the firmware
- Restart the Flask server
- Make sure firewall allows port 5000

**Serial Monitor shows but no server messages:**
- Server might not be running - check Python terminal
- WiFi might not be connected - look for "WiFi connected!" message
- May need to add delay between data sends if network is slow

## Data Format

Each row in the CSV file contains:

```
time_ms, 
th_qw, th_qx, th_qy, th_qz,              (Thigh quaternion)
th_ax_g, th_ay_g, th_az_g,               (Thigh acceleration in g)
th_gx_dps, th_gy_dps, th_gz_dps,         (Thigh gyro in deg/s)
sh_qw, sh_qx, sh_qy, sh_qz,              (Shank quaternion)
sh_ax_g, sh_ay_g, sh_az_g,               (Shank acceleration in g)
sh_gx_dps, sh_gy_dps, sh_gz_dps,         (Shank gyro in deg/s)
knee_deg,                                 (Knee flexion angle)
force_raw,                                (Piezo sensor raw ADC value)
stance,                                   (0=swing, 1=stance)
stride_length_m,                          (Estimated stride length)
velocity_mps,                             (Walking velocity)
cadence_spm,                              (Steps per minute)
stance_time_s,                            (Stance phase duration)
swing_time_s                              (Swing phase duration)
```

## Performance Notes

- Data is sent to server every **10 samples** (~100ms at 100Hz sampling)
- This reduces WiFi load while maintaining reasonable temporal resolution
- Serial output shows **all** samples for local debugging
- Total upload rate: ~10 rows/second to server

## Stopping the Server

- In the terminal running Flask: Press `Ctrl+C`
- This will clean shutdown the server

---

For sensor calibration and other settings, see [main.cpp](src/main.cpp) configuration section.
