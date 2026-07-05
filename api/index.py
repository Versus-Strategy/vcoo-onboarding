# VCOO Control Plane — Serverless Entry Point (Vercel)
# All requests hit here via vercel.json rewrites.

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'apps'))

from backend.main import application
app = application
