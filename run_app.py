#!/usr/bin/env python3
"""Run the FastAPI app and keep it running"""
import subprocess
import sys
import os

os.chdir(r'd:\deploy-retail-mind')

# Run the app
print("Starting FastAPI application...")
print("Server will be available at http://localhost:8000")
print("=" * 60)

subprocess.run([sys.executable, 'app.py'])
