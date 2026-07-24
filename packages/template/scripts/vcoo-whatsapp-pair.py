#!/usr/bin/env python3
"""VCOO WhatsApp pairing: runs bridge.js --pair-only --pair-json and outputs QR."""
import json, os, subprocess, sys, time

HERMES_HOME = os.path.expanduser("~/.hermes")
BRIDGE_DIR = os.path.join(HERMES_HOME, "hermes-agent", "scripts", "whatsapp-bridge")
BRIDGE_JS = os.path.join(BRIDGE_DIR, "bridge.js")
SESSION_DIR = os.path.join(HERMES_HOME, "whatsapp-session", "main")
QR_FILE = os.path.join(HERMES_HOME, "whatsapp-qr.json")
CONNECTED_FILE = os.path.join(HERMES_HOME, "whatsapp-connected.json")

# Ensure bridge exists
if not os.path.isfile(BRIDGE_JS):
    print(json.dumps({"error": "WhatsApp bridge not found. Install Hermes first."}))
    sys.exit(1)

os.makedirs(SESSION_DIR, exist_ok=True)

# Set env vars for non-interactive mode
env = os.environ.copy()
env.update({
    "WHATSAPP_MODE": "bot",
    "WHATSAPP_ENABLED": "true",
    "WHATSAPP_ALLOWED_USERS": "*",
})

try:
    proc = subprocess.Popen(
        ["node", BRIDGE_JS, "--pair-only", "--pair-json"],
        cwd=BRIDGE_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1, env=env,
    )
except FileNotFoundError:
    print(json.dumps({"error": "node not found"}))
    sys.exit(1)

qr_sent = False
start_time = time.time()
timeout = 120  # 2 minutes max

for line in proc.stdout:
    line = line.strip()
    if not line:
        continue
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        continue

    ev = event.get("event", "")

    if ev == "qr" and not qr_sent:
        qr_data = event.get("qr", "")
        output = {"qr": qr_data, "status": "waiting"}
        print(json.dumps(output))
        sys.stdout.flush()
        qr_sent = True
        # Write QR to file for polling
        with open(QR_FILE, "w") as f:
            json.dump(output, f)

    elif ev == "connected":
        user = event.get("user", {})
        output = {"status": "connected", "user": user}
        print(json.dumps(output))
        sys.stdout.flush()
        with open(CONNECTED_FILE, "w") as f:
            json.dump(output, f)
        if os.path.isfile(QR_FILE):
            os.remove(QR_FILE)
        proc.terminate()
        sys.exit(0)

    elif ev == "error":
        error_msg = event.get("error", "unknown error")
        print(json.dumps({"status": "error", "error": error_msg}))
        sys.stdout.flush()
        proc.terminate()
        sys.exit(1)

    if time.time() - start_time > timeout:
        print(json.dumps({"status": "timeout"}))
        sys.stdout.flush()
        proc.terminate()
        sys.exit(1)

proc.wait()
