#!/usr/bin/env bash
# Simula un agente localmente sin Docker. Asume que el backend está en http://localhost:8000
PROVISION_TOKEN=${1:-SIM_TOKEN}
python3 agent/agent.py "$PROVISION_TOKEN"
