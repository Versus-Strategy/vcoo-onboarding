#!/usr/bin/env python3
"""VCOO WhatsApp pairing — runs Node.js script and outputs QR or pairing code."""
import json, os, subprocess, sys, time

HERMES_HOME = os.path.expanduser("~/.hermes")
BRIDGE_DIR = os.path.join(HERMES_HOME, "hermes-agent", "scripts", "whatsapp-bridge")
NODE_SCRIPT = os.path.join(HERMES_HOME, "scripts", "vcoo", "vcoo-whatsapp-pair.js")
QR_FILE = os.path.join(HERMES_HOME, "whatsapp-qr.json")
PAIRING_FILE = os.path.join(HERMES_HOME, "whatsapp-pairing.json")
CONNECTED_FILE = os.path.join(HERMES_HOME, "whatsapp-connected.json")

# Accept phone number as argument
phone = sys.argv[1] if len(sys.argv) > 1 else None

if not os.path.isfile(NODE_SCRIPT):
    # Fallback: use bridge.js installed by Hermes
    BRIDGE_JS = os.path.join(BRIDGE_DIR, "bridge.js")
    if not os.path.isfile(BRIDGE_JS):
        print(json.dumps({"error": "WhatsApp bridge not found"}))
        sys.exit(1)
    SESSION_DIR = os.path.join(HERMES_HOME, "whatsapp-session", "main")
    os.makedirs(SESSION_DIR, exist_ok=True)
    env = os.environ.copy()
    env.update({"WHATSAPP_MODE": "bot", "WHATSAPP_ALLOWED_USERS": "*"})
    cmd = ["node", BRIDGE_JS, "--pair-only", "--pair-json"]
    try:
        proc = subprocess.Popen(cmd, cwd=BRIDGE_DIR, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
    except FileNotFoundError:
        print(json.dumps({"error": "node not found"}))
        sys.exit(1)
else:
    cmd = ["node", NODE_SCRIPT]
    if phone:
        cmd += ["--phone", phone]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, bufsize=1)
    except FileNotFoundError:
        print(json.dumps({"error": "node not found"}))
        sys.exit(1)

qr_sent = False
code_sent = False
start_time = time.time()
timeout = 120

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
        with open(QR_FILE, "w") as f:
            json.dump(output, f)

    elif ev == "pairing_code" and not code_sent:
        code = event.get("code", "")
        phone = event.get("phone", "")
        output = {"pairing_code": code, "phone": phone, "status": "waiting"}
        print(json.dumps(output))
        sys.stdout.flush()
        code_sent = True
        with open(PAIRING_FILE, "w") as f:
            json.dump(output, f)

    elif ev == "connected":
        user = event.get("user", {})
        output = {"status": "connected", "user": user}
        print(json.dumps(output))
        sys.stdout.flush()
        with open(CONNECTED_FILE, "w") as f:
            json.dump(output, f)
        for f in [QR_FILE, PAIRING_FILE]:
            if os.path.isfile(f):
                os.remove(f)
        proc.terminate()
        sys.exit(0)

    elif ev == "installing":
        print(json.dumps({"status": "installing_whatsapp"}))
        sys.stdout.flush()

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
