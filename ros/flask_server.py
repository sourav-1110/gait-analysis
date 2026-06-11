"""
Gait Analysis Flask Server — SSE push edition
Run: python ros/flask_server.py
"""
import os, csv, shutil, logging, queue, json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response, stream_with_context

# ── Paths ──────────────────────────────────────────────────────────────────────
THIS_DIR     = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.dirname(THIS_DIR)
TEMPLATE_DIR = os.path.join(ROOT_DIR, 'templates')
STATIC_DIR   = os.path.join(ROOT_DIR, 'static')
READINGS_DIR = os.path.join(ROOT_DIR, 'readings')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.config['SECRET_KEY'] = 'gait2024'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
os.makedirs(READINGS_DIR, exist_ok=True)

# ── CSV setup ──────────────────────────────────────────────────────────────────
CSV_FILENAME = f"gait_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
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
    logger.info(f"Created CSV: {CSV_FILEPATH}")

# ── In-memory store + SSE subscriber queues ───────────────────────────────────
_data_cache   = []          # full history
_sse_clients  = []          # list of queue.Queue(), one per connected browser tab

def _parse_row(row_str):
    """Parse a CSV row string → dict with float values. Returns None on error."""
    values = row_str.strip().split(',')
    if len(values) != len(CSV_HEADER):
        return None
    parsed = {}
    for k, v in zip(CSV_HEADER, values):
        try:    parsed[k] = float(v)
        except: parsed[k] = v
    return parsed

def _broadcast(row_dict):
    """Push one row to every connected SSE client."""
    payload = "data: " + json.dumps(row_dict) + "\n\n"
    dead = []
    for q in _sse_clients:
        try:
            q.put_nowait(payload)
        except queue.Full:
            dead.append(q)
    for q in dead:
        _sse_clients.remove(q)

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
    logger.info(f"Loaded {len(_data_cache)} rows from {CSV_FILENAME}")

_load_cache_from_csv()

# ── SSE stream endpoint ────────────────────────────────────────────────────────
@app.route('/stream')
def stream():
    """
    Each browser tab connects here. Flask holds the connection open and
    pushes new rows as SSE events the instant they arrive from the ESP32.
    """
    client_q = queue.Queue(maxsize=500)
    _sse_clients.append(client_q)
    logger.info(f"SSE client connected. Total: {len(_sse_clients)}")

    # Send the last 200 rows immediately so the dashboard pre-fills
    seed = _data_cache[-200:] if _data_cache else []
    seed_payload = "data: " + json.dumps({"seed": seed}) + "\n\n"

    def generate():
        try:
            yield seed_payload           # initial data burst
            while True:
                try:
                    msg = client_q.get(timeout=20)
                    yield msg
                except queue.Empty:
                    yield ": heartbeat\n\n"   # keep connection alive
        except GeneratorExit:
            pass
        finally:
            if client_q in _sse_clients:
                _sse_clients.remove(client_q)
            logger.info(f"SSE client disconnected. Total: {len(_sse_clients)}")

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control':   'no-cache',
            'X-Accel-Buffering': 'no',    # disable nginx buffering if behind proxy
        }
    )

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
    size = os.path.getsize(CSV_FILEPATH) if os.path.exists(CSV_FILEPATH) else 0
    return jsonify({
        "status": "ok",
        "records": len(_data_cache),
        "sse_clients": len(_sse_clients),
        "file": CSV_FILENAME,
        "file_size_kb": round(size / 1024, 2)
    }), 200

# ── ESP32 ingestion ────────────────────────────────────────────────────────────
@app.route('/log_data_csv', methods=['POST'])
def log_data_csv():
    try:
        body = request.data.decode('utf-8').strip()
        if not body:
            return jsonify({"error": "Empty data"}), 400

        lines = [l.strip() for l in body.splitlines()
                 if l.strip() and not l.startswith('time_ms')]
        if not lines:
            return jsonify({"status": "ok", "added": 0, "total": len(_data_cache)}), 200

        added = 0
        with open(CSV_FILEPATH, 'a', newline='') as f:
            for row in lines:
                parsed = _parse_row(row)
                if parsed is None:
                    logger.warning(f"Bad row ({len(row.split(','))} cols): {row[:80]}")
                    continue
                f.write(row + '\n')
                _data_cache.append(parsed)
                _broadcast(parsed)        # ← push to every browser tab instantly
                added += 1

        logger.info(f"✓ {added}/{len(lines)} rows added. Cache: {len(_data_cache)}")
        return jsonify({"status": "ok", "added": added, "total": len(_data_cache)}), 200

    except Exception as e:
        logger.error(f"log_data_csv error: {e}")
        return jsonify({"error": str(e)}), 500

# ── REST API (still used for stats / export / debug) ──────────────────────────
@app.route('/api/data')
def api_data():
    limit = int(request.args.get('limit', 200))
    rows  = _data_cache[-limit:]
    return jsonify({"status":"ok","total":len(_data_cache),"returned":len(rows),"data":rows}), 200

@app.route('/api/data/stats')
def api_stats():
    rows = _data_cache
    if not rows:
        return jsonify({"count":0,"avg_velocity":0,"avg_cadence":0,
                        "avg_stride_length":0,"max_velocity":0,
                        "max_knee_deg":0,"avg_knee_deg":0,
                        "avg_stance_time":0,"avg_swing_time":0}), 200
    def avg(f):
        v=[r[f] for r in rows if isinstance(r.get(f),(int,float))]
        return sum(v)/len(v) if v else 0
    def mx(f):
        v=[r[f] for r in rows if isinstance(r.get(f),(int,float))]
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

@app.route('/api/data/latest')
def api_latest():
    if not _data_cache:
        return jsonify({"message":"No data yet"}), 200
    return jsonify(_data_cache[-1]), 200

@app.route('/api/data/export')
def api_export():
    if not os.path.exists(CSV_FILEPATH):
        return jsonify({"error":"No data file"}), 404
    name = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    dest = os.path.join(READINGS_DIR, name)
    shutil.copy2(CSV_FILEPATH, dest)
    return jsonify({"status":"ok","file":name,"path":dest}), 200

@app.route('/api/reset', methods=['POST'])
def api_reset():
    global _data_cache
    _data_cache = []
    if os.path.exists(CSV_FILEPATH):
        with open(CSV_FILEPATH, 'w', newline='') as f:
            csv.writer(f).writerow(CSV_HEADER)
    logger.info("Data reset.")
    return jsonify({"status":"ok","file":CSV_FILENAME,"message":"Cleared."}), 200

@app.route('/get_status')
def get_status():
    size = os.path.getsize(CSV_FILEPATH) if os.path.exists(CSV_FILEPATH) else 0
    return jsonify({"status":"ok","file":CSV_FILENAME,
                    "file_size_bytes":size,"cache_records":len(_data_cache)}), 200

@app.route('/debug/cache')
def debug_cache():
    return jsonify({
        "total_records": len(_data_cache),
        "first_record":  _data_cache[0]  if _data_cache else None,
        "last_record":   _data_cache[-1] if _data_cache else None,
        "sse_clients":   len(_sse_clients),
    }), 200

# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f"\n{'='*60}")
    print(f"🚀 GAIT ANALYSIS SERVER  (SSE push mode)")
    print(f"{'='*60}")
    print(f"CSV       : {CSV_FILEPATH}")
    print(f"Records   : {len(_data_cache)} pre-loaded")
    print(f"\nURLs:")
    print(f"  Dashboard  : http://localhost:5000/")
    print(f"  Stream     : http://localhost:5000/stream  (SSE)")
    print(f"  Health     : http://localhost:5000/health")
    print(f"\nESP32 → http://<server-ip>:5000/log_data_csv")
    print(f"{'='*60}\n")
    # threaded=True required for concurrent SSE connections + ESP32 POSTs
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)