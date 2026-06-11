"""
Quick start script for Gait Analysis Server
Run this to set up and start the server
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def check_python():
    """Check Python version"""
    print_header("Checking Python")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro} - OK")
    if version.major < 3 or version.minor < 8:
        print("ERROR: Python 3.8+ required")
        return False
    return True

def check_mongodb():
    """Check MongoDB connection"""
    print_header("Checking MongoDB")
    try:
        from pymongo import MongoClient
        client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=3000)
        client.admin.command('ping')
        print("MongoDB connection - OK")
        return True
    except Exception as e:
        print(f"MongoDB NOT connected: {e}")
        print("\nTo start MongoDB:")
        print("  Windows: mongod")
        print("  macOS: brew services start mongodb-community")
        print("  Linux: sudo service mongod start")
        print("  Docker: docker run -d -p 27017:27017 mongo:latest")
        return False

def install_dependencies():
    """Install required packages"""
    print_header("Installing Dependencies")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Dependencies installed - OK")
        return True
    except Exception as e:
        print(f"Error installing dependencies: {e}")
        return False

def verify_structure():
    """Verify directory structure"""
    print_header("Verifying Project Structure")
    
    required_dirs = [
        'templates',
        'static/css',
        'static/js',
        'readings'
    ]
    
    required_files = [
        'app.py',
        'config.py',
        'templates/index.html',
        'templates/data.html',
        'static/css/style.css',
        'static/js/dashboard.js',
        'static/js/data-view.js'
    ]
    
    all_ok = True
    
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"  ✓ {dir_path}")
        else:
            print(f"  ✗ {dir_path} - MISSING")
            all_ok = False
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} - MISSING")
            all_ok = False
    
    return all_ok

def start_server():
    """Start the Flask server"""
    print_header("Starting Flask Server")
    
    try:
        from app import app
        
        print(f"Server configuration:")
        print(f"  Host: {app.config['HOST']}")
        print(f"  Port: {app.config['PORT']}")
        print(f"  Debug: {app.config['DEBUG']}")
        print(f"  MongoDB: {app.config['MONGO_DB']}")
        print(f"  CSV Output: {app.config['CSV_OUTPUT_DIR']}")
        
        print("\nStarting server...")
        print("Dashboard: http://localhost:5000/")
        print("Data View: http://localhost:5000/data")
        print("API Health: http://localhost:5000/health")
        print("\nPress Ctrl+C to stop the server\n")
        
        app.run(
            host=app.config['HOST'],
            port=app.config['PORT'],
            debug=app.config['DEBUG']
        )
    except Exception as e:
        print(f"Error starting server: {e}")
        return False
    
    return True

def main():
    """Main startup sequence"""
    print_header("Gait Analysis Server - Quick Start")
    
    steps = [
        ("Python Version", check_python),
        ("Dependencies", install_dependencies),
        ("Project Structure", verify_structure),
        ("MongoDB Connection", check_mongodb),
    ]
    
    for step_name, step_func in steps:
        if not step_func():
            print(f"\n⚠ WARNING: {step_name} check failed")
            response = input(f"Continue anyway? (y/n): ").strip().lower()
            if response != 'y':
                print("Setup cancelled")
                return
    
    print("\n✓ All checks passed!\n")
    
    if start_server():
        print("\nServer stopped")
    else:
        print("\nServer failed to start")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nShutdown requested")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)
