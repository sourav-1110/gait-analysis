"""
Flask server to receive gait analysis CSV data from ESP32
Saves data to MongoDB and provides REST API for data retrieval
"""
from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
import csv
import os
from datetime import datetime
import logging
from config import Config

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.config.from_object(Config)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
try:
    mongo_client = MongoClient(
        app.config['MONGO_URI'],
        serverSelectionTimeoutMS=5000
    )
    # Test connection
    mongo_client.admin.command('ping')
    db = mongo_client[app.config['MONGO_DB']]
    collection = db[app.config['MONGO_COLLECTION']]
    logger.info("Connected to MongoDB successfully")
except ServerSelectionTimeoutError as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    logger.warning("MongoDB connection failed. CSV fallback mode enabled.")
    db = None
    collection = None

# CSV header
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

# Ensure readings directory exists
os.makedirs(app.config['CSV_OUTPUT_DIR'], exist_ok=True)


def csv_row_to_dict(csv_row):
    """Convert CSV row string to dictionary"""
    try:
        values = csv_row.strip().split(',')
        if len(values) != len(CSV_HEADER):
            logger.warning(f"CSV row has {len(values)} values, expected {len(CSV_HEADER)}")
            return None
        
        data_dict = {}
        for header, value in zip(CSV_HEADER, values):
            try:
                # Try to convert to float for numeric fields
                if header in ['time_ms', 'knee_deg', 'force_raw']:
                    data_dict[header] = int(value) if value else 0
                elif header != 'stance':
                    data_dict[header] = float(value) if value else 0.0
                else:
                    data_dict[header] = value.lower() == 'true'
            except ValueError:
                data_dict[header] = value
        
        # Add timestamp
        data_dict['received_at'] = datetime.now()
        return data_dict
    except Exception as e:
        logger.error(f"Error converting CSV row: {e}")
        return None


@app.route('/', methods=['GET'])
def index():
    """Main dashboard"""
    return render_template('index.html')


@app.route('/data', methods=['GET'])
def data_view():
    """Data table view"""
    return render_template('data.html')


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    status = "ok"
    mongo_status = "connected" if collection else "disconnected"
    return jsonify({
        "status": status,
        "message": "Flask server is running",
        "mongodb": mongo_status
    }), 200


@app.route('/api/log_data', methods=['POST'])
@app.route('/log_data_csv', methods=['POST'])
def log_data():
    """
    Receive CSV data from ESP32
    Expects raw CSV row(s) in request body
    """
    try:
        csv_data = request.data.decode('utf-8').strip()
        
        if not csv_data:
            return jsonify({"error": "No data provided"}), 400
        
        # Handle multiple rows (separated by newlines)
        rows = csv_data.split('\n')
        saved_count = 0
        
        for csv_row in rows:
            csv_row = csv_row.strip()
            if not csv_row or csv_row.startswith('time_ms'):
                continue  # Skip empty lines and header
            
            # Convert to dictionary
            data_dict = csv_row_to_dict(csv_row)
            if not data_dict:
                continue
            
            # Save to MongoDB
            if collection:
                try:
                    result = collection.insert_one(data_dict)
                    logger.info(f"Data inserted to MongoDB: {result.inserted_id}")
                except Exception as e:
                    logger.error(f"Error inserting to MongoDB: {e}")
            
            # Always save to CSV file (backup)
            csv_filepath = os.path.join(
                app.config['CSV_OUTPUT_DIR'],
                app.config['CSV_FILENAME']
            )
            try:
                with open(csv_filepath, 'a', newline='') as f:
                    f.write(csv_row + '\n')
                saved_count += 1
            except Exception as e:
                logger.error(f"Error saving to CSV: {e}")
        
        logger.info(f"Data logged successfully ({saved_count} rows)")
        return jsonify({"status": "ok", "message": f"Data logged ({saved_count} rows)"}), 200
        
    except Exception as e:
        logger.error(f"Error logging data: {str(e)}")
        return jsonify({"error": str(e)}), 500


def load_data_from_csv():
    """Load data from CSV file (fallback mode)"""
    try:
        csv_filepath = os.path.join(
            app.config['CSV_OUTPUT_DIR'],
            app.config['CSV_FILENAME']
        )
        if not os.path.exists(csv_filepath):
            return []
        
        data = []
        with open(csv_filepath, 'r') as f:
            reader = csv.DictReader(f, fieldnames=CSV_HEADER)
            for row in reader:
                if row['time_ms'] == 'time_ms':  # Skip header
                    continue
                # Convert numeric fields
                try:
                    row_dict = {
                        'time_ms': int(row['time_ms']),
                        'th_qw': float(row.get('th_qw', 0)),
                        'th_qx': float(row.get('th_qx', 0)),
                        'th_qy': float(row.get('th_qy', 0)),
                        'th_qz': float(row.get('th_qz', 0)),
                        'th_ax_g': float(row.get('th_ax_g', 0)),
                        'th_ay_g': float(row.get('th_ay_g', 0)),
                        'th_az_g': float(row.get('th_az_g', 0)),
                        'th_gx_dps': float(row.get('th_gx_dps', 0)),
                        'th_gy_dps': float(row.get('th_gy_dps', 0)),
                        'th_gz_dps': float(row.get('th_gz_dps', 0)),
                        'sh_qw': float(row.get('sh_qw', 0)),
                        'sh_qx': float(row.get('sh_qx', 0)),
                        'sh_qy': float(row.get('sh_qy', 0)),
                        'sh_qz': float(row.get('sh_qz', 0)),
                        'sh_ax_g': float(row.get('sh_ax_g', 0)),
                        'sh_ay_g': float(row.get('sh_ay_g', 0)),
                        'sh_az_g': float(row.get('sh_az_g', 0)),
                        'sh_gx_dps': float(row.get('sh_gx_dps', 0)),
                        'sh_gy_dps': float(row.get('sh_gy_dps', 0)),
                        'sh_gz_dps': float(row.get('sh_gz_dps', 0)),
                        'knee_deg': float(row.get('knee_deg', 0)),
                        'force_raw': int(row.get('force_raw', 0)),
                        'stance': row.get('stance', '0').lower() == 'true',
                        'stride_length_m': float(row.get('stride_length_m', 0)),
                        'velocity_mps': float(row.get('velocity_mps', 0)),
                        'cadence_spm': float(row.get('cadence_spm', 0)),
                        'stance_time_s': float(row.get('stance_time_s', 0)),
                        'swing_time_s': float(row.get('swing_time_s', 0)),
                    }
                    data.append(row_dict)
                except (ValueError, KeyError) as e:
                    continue
        
        return data
    except Exception as e:
        logger.error(f"Error loading CSV data: {e}")
        return []


@app.route('/api/data', methods=['GET'])
def get_data():
    """Get all gait analysis data"""
    try:
        if collection:
            # Query parameters
            limit = request.args.get('limit', default=100, type=int)
            skip = request.args.get('skip', default=0, type=int)
            
            # Get data from MongoDB
            data = list(collection.find({}, {'_id': 0}).sort('time_ms', -1).skip(skip).limit(limit))
            total = collection.count_documents({})
        else:
            # CSV fallback mode
            all_data = load_data_from_csv()
            limit = request.args.get('limit', default=100, type=int)
            skip = request.args.get('skip', default=0, type=int)
            
            # Sort by time_ms descending
            all_data.sort(key=lambda x: x.get('time_ms', 0), reverse=True)
            total = len(all_data)
            data = all_data[skip:skip+limit]
        
        return jsonify({
            "total": total,
            "returned": len(data),
            "data": data,
            "mode": "mongodb" if collection else "csv_fallback"
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/data/latest', methods=['GET'])
def get_latest_data():
    """Get latest gait analysis record"""
    try:
        if collection:
            data = collection.find_one({}, sort=[('time_ms', -1)], projection={'_id': 0})
        else:
            # CSV fallback mode
            all_data = load_data_from_csv()
            if all_data:
                all_data.sort(key=lambda x: x.get('time_ms', 0), reverse=True)
                data = all_data[0]
            else:
                data = None
        
        if data:
            return jsonify(data), 200
        else:
            return jsonify({"message": "No data available"}), 404
    except Exception as e:
        logger.error(f"Error retrieving latest data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/data/stats', methods=['GET'])
def get_stats():
    """Get statistics about gait analysis"""
    try:
        if collection:
            pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "avg_velocity": {"$avg": "$velocity_mps"},
                        "avg_cadence": {"$avg": "$cadence_spm"},
                        "avg_stride_length": {"$avg": "$stride_length_m"},
                        "avg_knee_angle": {"$avg": "$knee_deg"},
                        "max_velocity": {"$max": "$velocity_mps"},
                        "min_velocity": {"$min": "$velocity_mps"},
                        "count": {"$sum": 1}
                    }
                }
            ]
            
            stats = list(collection.aggregate(pipeline))
        else:
            # CSV fallback mode
            all_data = load_data_from_csv()
            if not all_data:
                return jsonify({"message": "No data available"}), 404
            
            velocities = [d.get('velocity_mps', 0) for d in all_data]
            cadences = [d.get('cadence_spm', 0) for d in all_data]
            strides = [d.get('stride_length_m', 0) for d in all_data]
            knees = [d.get('knee_deg', 0) for d in all_data]
            
            stats = [{
                "avg_velocity": sum(velocities) / len(velocities) if velocities else 0,
                "avg_cadence": sum(cadences) / len(cadences) if cadences else 0,
                "avg_stride_length": sum(strides) / len(strides) if strides else 0,
                "avg_knee_angle": sum(knees) / len(knees) if knees else 0,
                "max_velocity": max(velocities) if velocities else 0,
                "min_velocity": min(velocities) if velocities else 0,
                "count": len(all_data)
            }]
        
        if stats:
            return jsonify(stats[0]), 200
        else:
            return jsonify({"message": "No data available"}), 404
    except Exception as e:
        logger.error(f"Error calculating stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/data/export', methods=['GET'])
def export_data():
    """Export data as CSV"""
    try:
        if not collection:
            return jsonify({"error": "MongoDB not connected"}), 503
        
        data = list(collection.find({}, {'_id': 0}).sort('time_ms', 1))
        
        if not data:
            return jsonify({"error": "No data to export"}), 404
        
        # Create CSV
        export_filename = f"gait_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        export_path = os.path.join(app.config['CSV_OUTPUT_DIR'], export_filename)
        
        with open(export_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADER + ['received_at'])
            writer.writeheader()
            writer.writerows(data)
        
        return jsonify({
            "status": "ok",
            "message": "Data exported",
            "file": export_filename,
            "path": export_path
        }), 200
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/data/clear', methods=['DELETE'])
def clear_data():
    """Clear all data (admin only)"""
    try:
        if not collection:
            return jsonify({"error": "MongoDB not connected"}), 503
        
        # Check for authorization (optional)
        token = request.args.get('token')
        if token != app.config.get('ADMIN_TOKEN', 'admin123'):
            return jsonify({"error": "Unauthorized"}), 401
        
        result = collection.delete_many({})
        return jsonify({
            "status": "ok",
            "message": f"Deleted {result.deleted_count} records"
        }), 200
    except Exception as e:
        logger.error(f"Error clearing data: {e}")
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    print("\n" + "="*50)
    print("Flask Gait Analysis Server with MongoDB")
    print("="*50)
    print(f"MongoDB URI: {app.config['MONGO_URI']}")
    print(f"Database: {app.config['MONGO_DB']}")
    print(f"Collection: {app.config['MONGO_COLLECTION']}")
    print(f"CSV Output: {app.config['CSV_OUTPUT_DIR']}")
    print("="*50 + "\n")
    
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )
