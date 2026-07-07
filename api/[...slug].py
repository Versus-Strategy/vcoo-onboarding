# VCOO Control Plane — Serverless Entry Point (Vercel)
import sys, os

_sys_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'apps')
if _sys_path not in sys.path:
    sys.path.insert(0, _sys_path)

from fastapi import Request
from fastapi.responses import JSONResponse
from backend.main import application

app = application
