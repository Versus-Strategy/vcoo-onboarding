# VCOO Control Plane — Serverless Entry Point (Vercel)
# This file wraps the FastAPI app for Vercel's Python runtime.
# All requests hit here via vercel.json rewrites.

import sys
import os

# Ensure the project root is on the path so backend.* imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
handler = app
