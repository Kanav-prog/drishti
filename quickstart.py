#!/usr/bin/env python3
"""
DRISHTI MVP: Quick Start Script
Initializes and runs the complete 4-layer system
"""

import sys
import subprocess
import os
import time
from pathlib import Path

def run_command(cmd, description, background=False):
    """Run shell command and report status"""
    print(f"\n📌 {description}")
    try:
        if background:
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"   ✓ Started in background (PID: {proc.pid})")
            return proc
        else:
            result = subprocess.run(cmd, shell=True, check=True, capture_output=False)
            print(f"   ✓ Completed")
            return result
    except subprocess.CalledProcessError as e:
        print(f"   ✗ Failed: {e}")
        sys.exit(1)

def check_redis():
    """Verify Redis is running"""
    print("\n🔍 Checking Redis...")
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
        r.ping()
        print("   ✓ Redis connected")
        return True
    except:
        print("   ⚠️  Redis not running (optional for demo)")
        return False

def main():
    """Main startup"""
    print("\n" + "="*60)
    print("DRISHTI MVP QUICK START")
    print("="*60)
    
    root_dir = Path(__file__).parent
    os.chdir(root_dir)
    
    # Check Redis
    check_redis()
    
    # Install dependencies
    print("\n📦 Checking dependencies...")
    run_command(
        f"{sys.executable} -m pip install -q -r requirements.txt",
        "Installing Python packages"
    )
    
    # Generate network graph
    print("\n🗺️  Layer 1: Generating Network Graph...")
    run_command(
        f"{sys.executable} backend/network/graph_builder.py",
        "Computing centrality and building graph"
    )
    
    # Start API server
    print("\n⚡ Layer 2-4: Starting FastAPI Server...")
    print("   API will be available at http://localhost:8000")
    print("   API docs at http://localhost:8000/docs")
    run_command(
        f"{sys.executable} -m uvicorn backend.api.server:app --host 0.0.0.0 --port 8000",
        "Starting FastAPI with Cascade Engine"
    )

if __name__ == "__main__":
    main()
