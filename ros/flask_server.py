"""
Gait Analysis Flask Server
Run from project root:
    python ros/flask_server.py
Automatically loads the most recent CSV in readings/ folder.
"""
import os, csv, shutil, logging, sys
from datetime import datetime
from flask import Flask, request, jsonify, render_template

# ── Paths ──────────────────────────────────────────────────────────────────────
THIS_DIR     = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.dirname(THIS_DIR)
TEMPLATE_DIR = os.path.join(ROOT_DIR, 'templates')
STATIC_DIR   = os.path.join(ROOT_DIR, 'static')
READINGS_DIR = os.path.join(ROOT_DIR, 'readings')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

os.makedirs(READINGS_DIR, exist_ok=True)

# ── Create fresh CSV file each startup ──────────────────────────────────────
# Always create a new CSV file with fresh timestamp to avoid cache/parsing issues
CSV_FILENAME = f"gait_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
print(f"\nCreating fresh CSV file: {CSV_FILENAME}")

CSV_FILEPATH = os.path.join(READINGS_DIR, CSV_FILENAME)

CSV_HEADER = [
    "time_ms",
    "th_qw","th_qx","th_qy","th_qz",
    "th_ax_g","th_ay_g","th_az_g",
    "th_gx_dps","th_gy_dps","th_gz_dps",
    "sh_qw","sh_qx","sh_qy","sh_qz",
    "sh_ax_g","sh_ay_g","sh_az_g",
    "sh_gx_dps","sh_gy_dps","sh_gz_dps",
    "knee_deg","force_raw","stance",
    "stride_length_m","velocity_mps","cadence_spm",
    "stance_time_s","swing_time_s"
]

if not os.path.exists(CSV_FILEPATH):
    with open(CSV_FILEPATH, 'w', newline='') as f:
        csv.writer(f).writerow(CSV_HEADER)
    logger.info(f"Created new CSV: {CSV_FILEPATH}")

# ── In-memory cache ────────────────────────────────────────────────────────────
_data_cache = []

def _load_cache_from_csv():
    global _data_cache
    if not os.path.exists(CSV_FILEPATH):
        return
    rows = []
    with open(CSV_FILEPATH, newline='') as f:
        for row in csv.DictReader(f):
            parsed = {}
            for k, v in row.items():
                try:    parsed[k] = float(v)
                except: parsed[k] = v
            rows.append(parsed)
    _data_cache = rows
    logger.info(f"Cache loaded: {len(_data_cache)} rows from {CSV_FILENAME}")

def _append_to_cache(row_str):
    """Parse a single CSV row string and append to cache. Returns True if successful."""
    try:
        values = row_str.strip().split(',')
        if len(values) != len(CSV_HEADER):
            logger.warning(f"Row has {len(values)} values, expected {len(CSV_HEADER)}: {row_str[:100]}")
            return False
        parsed = {}
        for k, v in zip(CSV_HEADER, values):
            try:    
                parsed[k] = float(v)
            except: 
                parsed[k] = v
        _data_cache.append(parsed)
        return True
    except Exception as e:
        logger.error(f"Error appending to cache: {e}")
        return False

_load_cache_from_csv()

# ── Pages ──────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def data_view():
    return render_template('data.html')

# ── Health ─────────────────────────────────────────────────────────────────────
@app.route('/health')
def health():
    file_size = os.path.getsize(CSV_FILEPATH) if os.path.exists(CSV_FILEPATH) else 0
    return jsonify({
        "status": "ok",
        "message": "Flask server is running",
        "records": len(_data_cache),
        "file": CSV_FILENAME,
        "file_size_bytes": file_size,
        "file_size_kb": round(file_size / 1024, 2)
    }), 200

# ── ESP32 ingestion ────────────────────────────────────────────────────────────
@app.route('/log_data', methods=['POST'])
def log_data():
    try:
        data = request.get_json()
        if not data or 'data' not in data:
            return jsonify({"error": "Missing 'data' field"}), 400
        body = data['data'].strip()
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        added = 0
        for row in lines:
            with open(CSV_FILEPATH, 'a', newline='') as f:
                f.write(row + '\n')
            if _append_to_cache(row):
                added += 1
        return jsonify({"status": "ok", "added": added, "total": len(_data_cache)}), 200
    except Exception as e:
        logger.error(f"log_data error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/log_data_csv', methods=['POST'])
def log_data_csv():
    try:
        body = request.data.decode('utf-8').strip()
        if not body:
            return jsonify({"error": "Empty data"}), 400

        lines = [l.strip() for l in body.splitlines() if l.strip() and not l.startswith('time_ms')]
        if not lines:
            logger.warning("No valid data lines received")
            return jsonify({"status": "ok", "added": 0, "total": len(_data_cache), "info": "no valid lines"}), 200
        
        added = 0
        errors = 0
        for row in lines:
            try:
                with open(CSV_FILEPATH, 'a', newline='') as f:
                    f.write(row + '\n')
                if _append_to_cache(row):
                    added += 1
                else:
                    errors += 1
                    logger.warning(f"Failed to cache row: {row[:80]}")
            except Exception as e:
                logger.error(f"Error writing row: {e}")
                errors += 1

        logger.info(f"✓ Received {len(lines)} lines, added {added} to cache (errors: {errors}). Total cache: {len(_data_cache)}")
        return jsonify({
            "status": "ok", 
            "added": added, 
            "total": len(_data_cache),
            "errors": errors,
            "file": CSV_FILENAME
        }), 200
    except Exception as e:
        logger.error(f"log_data_csv error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_status')
def get_status():
    return jsonify({
        "status": "ok",
        "file": CSV_FILENAME,
        "file_size_bytes": os.path.getsize(CSV_FILEPATH) if os.path.exists(CSV_FILEPATH) else 0,
        "cache_records": len(_data_cache),
        "csv_file_path": CSV_FILEPATH
    }), 200

@app.route('/debug/cache')
def debug_cache():
    """Debug endpoint to show cache status and first/last records"""
    return jsonify({
        "total_records": len(_data_cache),
        "cache_status": "ok" if len(_data_cache) > 0 else "empty",
        "first_record": _data_cache[0] if _data_cache else None,
        "last_record": _data_cache[-1] if _data_cache else None,
        "file": CSV_FILENAME,
        "file_exists": os.path.exists(CSV_FILEPATH),
        "file_size_bytes": os.path.getsize(CSV_FILEPATH) if os.path.exists(CSV_FILEPATH) else 0
    }), 200

# ── Dashboard API ──────────────────────────────────────────────────────────────
@app.route('/api/data')
def api_data():
    try:
        limit = int(request.args.get('limit', 100))
        rows  = _data_cache[-limit:]
        return jsonify({
            "status": "ok",
            "total": len(_data_cache),
            "returned": len(rows),
            "data": rows
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/data/stats')
def api_stats():
    try:
        rows = _data_cache
        if not rows:
            return jsonify({
                "count":0,"avg_velocity":0,"avg_cadence":0,
                "avg_stride_length":0,"max_velocity":0,
                "max_knee_deg":0,"avg_knee_deg":0,
                "avg_stance_time":0,"avg_swing_time":0
            }), 200
        def avg(f):
            v = [r[f] for r in rows if isinstance(r.get(f), (int, float))]
            return sum(v)/len(v) if v else 0
        def mx(f):
            v = [r[f] for r in rows if isinstance(r.get(f), (int, float))]
            return max(v) if v else 0
        return jsonify({
            "count":             len(rows),
            "avg_velocity":      avg("velocity_mps"),
            "avg_cadence":       avg("cadence_spm"),
            "avg_stride_length": avg("stride_length_m"),
            "max_velocity":      mx("velocity_mps"),
            "max_knee_deg":      mx("knee_deg"),
            "avg_knee_deg":      avg("knee_deg"),
            "avg_stance_time":   avg("stance_time_s"),
            "avg_swing_time":    avg("swing_time_s"),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/data/latest')
def api_latest():
    if not _data_cache:
        return jsonify({"message": "No data yet"}), 200
    return jsonify(_data_cache[-1]), 200

@app.route('/api/data/export')
def api_export():
    try:
        if not os.path.exists(CSV_FILEPATH):
            return jsonify({"error": "No data file"}), 404
        name = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        dest = os.path.join(READINGS_DIR, name)
        shutil.copy2(CSV_FILEPATH, dest)
        return jsonify({"status": "ok", "file": name, "path": dest}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Reset: delete current CSV, create fresh one, clear cache ──────────────────
@app.route('/api/reset', methods=['POST'])
def api_reset():
    global CSV_FILEPATH, CSV_FILENAME, _data_cache
    try:
        # Delete the old CSV file
        if os.path.exists(CSV_FILEPATH):
            os.remove(CSV_FILEPATH)
            logger.info(f"Deleted old CSV: {CSV_FILEPATH}")

        # Create a new CSV file with a fresh timestamp
        CSV_FILENAME = f"gait_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        CSV_FILEPATH = os.path.join(READINGS_DIR, CSV_FILENAME)
        with open(CSV_FILEPATH, 'w', newline='') as f:
            csv.writer(f).writerow(CSV_HEADER)
        logger.info(f"Created new CSV: {CSV_FILEPATH}")

        # Clear in-memory cache
        _data_cache = []

        return jsonify({
            "status": "ok",
            "new_file": CSV_FILENAME,
            "message": "CSV deleted and fresh file created"
        }), 200
    except Exception as e:
        logger.error(f"api_reset error: {e}")
        return jsonify({"error": str(e)}), 500

# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f"\n{'='*60}")
    print(f"🚀 GAIT ANALYSIS FLASK SERVER")
    print(f"{'='*60}")
    print(f"CSV File       : {CSV_FILEPATH}")
    print(f"Data Points    : {len(_data_cache)} loaded from CSV")
    print(f"File Size      : {os.path.getsize(CSV_FILEPATH) if os.path.exists(CSV_FILEPATH) else 0} bytes")
    print(f"\n📍 URLs:")
    print(f"   Dashboard   : http://localhost:5000/")
    print(f"   Data Table  : http://localhost:5000/data")
    print(f"   API Data    : http://localhost:5000/api/data")
    print(f"   API Stats   : http://localhost:5000/api/data/stats")
    print(f"   Health      : http://localhost:5000/health")
    print(f"\n📤 ESP32 Send To:")
    print(f"   http://<server-ip>:5000/log_data_csv")
    print(f"   (Send CSV rows as raw text in POST body)")
    print(f"\n{'='*60}\n")
    
    print("Starting server... Press Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)