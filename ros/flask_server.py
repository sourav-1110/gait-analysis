"""
Flask server to receive gait analysis CSV data from ESP32
Saves data to a CSV file with timestamp
"""
from flask import Flask, request, jsonify
import csv
import os
from datetime import datetime
import logging

app = Flask(__name__)

# Configuration
CSV_OUTPUT_DIR = r"D:\vs projects\gait-analysis-main\readings"

# Prompt user for filename
print("\n" + "="*50)
print("Flask Gait Analysis Server")
print("="*50)
print("Enter CSV filename (without .csv extension):")
user_filename = input().strip()
if not user_filename:
    user_filename = f"gait_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
CSV_FILENAME = f"{user_filename}.csv"
CSV_FILEPATH = os.path.join(CSV_OUTPUT_DIR, CSV_FILENAME)

# Ensure output directory exists
os.makedirs(CSV_OUTPUT_DIR, exist_ok=True)

# CSV header (must match the C++ code)
CSV_HEADER = [
    "time_ms", 
    "th_qw", "th_qx", "th_qy", "th_qz",
    "th_ax_g", "th_ay_g", "th_az_g",
    "th_gx_dps", "th_gy_dps", "th_gz_dps",
    "sh_qw", "sh_qx", "sh_qy", "sh_qz",
    "sh_ax_g", "sh_ay_g", "sh_az_g",
    "sh_gx_dps", "sh_gy_dps", "sh_gz_dps",
    "knee_deg", "force_raw", "stance",
    "stride_length_m", "velocity_mps", "cadence_spm",
    "stance_time_s", "swing_time_s"
]

# Initialize CSV file with header
if not os.path.exists(CSV_FILEPATH):
    with open(CSV_FILEPATH, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
    print(f"Created CSV file: {CSV_FILEPATH}")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "Flask server is running"}), 200


@app.route('/log_data', methods=['POST'])
def log_data():
    """
    Receive CSV data from ESP32 and append to file
    Expects JSON with "data" field containing comma-separated values
    """
    try:
        data = request.get_json()
        
        if not data or 'data' not in data:
            return jsonify({"error": "Missing 'data' field"}), 400
        
        csv_row = data['data']
        
        # Append to CSV file
        with open(CSV_FILEPATH, 'a', newline='') as f:
            f.write(csv_row + '\n')
        
        logger.info(f"Data logged successfully")
        return jsonify({"status": "ok", "message": "Data logged"}), 200
        
    except Exception as e:
        logger.error(f"Error logging data: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/log_data_csv', methods=['POST'])
def log_data_csv():
    """
    Alternative endpoint that accepts CSV data in request body
    Content-Type should be text/plain
    """
    try:
        csv_row = request.data.decode('utf-8').strip()
        
        if not csv_row:
            return jsonify({"error": "Empty data"}), 400
        
        # Append to CSV file
        with open(CSV_FILEPATH, 'a', newline='') as f:
            f.write(csv_row + '\n')
        
        logger.info(f"Data logged: {csv_row[:50]}...")
        return jsonify({"status": "ok", "message": "Data logged"}), 200
        
    except Exception as e:
        logger.error(f"Error logging data: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_status', methods=['GET'])
def get_status():
    """Get current logging status"""
    try:
        if os.path.exists(CSV_FILEPATH):
            file_size = os.path.getsize(CSV_FILEPATH)
            with open(CSV_FILEPATH, 'r') as f:
                line_count = sum(1 for _ in f) - 1  # Subtract header
            
            return jsonify({
                "status": "ok",
                "file": CSV_FILENAME,
                "file_path": CSV_FILEPATH,
                "file_size_bytes": file_size,
                "data_points": line_count
            }), 200
        else:
            return jsonify({"error": "CSV file not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print(f"\n{'='*50}")
    print(f"CSV Output: {CSV_FILEPATH}")
    print(f"Data Points: 0")
    print(f"{'='*50}\n")
    
    # Run on 0.0.0.0 to allow connections from other devices (like ESP32)
    app.run(host='0.0.0.0', port=5000, debug=True)
