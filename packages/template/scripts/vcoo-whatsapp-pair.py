#!/usr/bin/env python3
"""VCOO WhatsApp pairing — runs bridge.js --pair-only or vcoo-whatsapp-pair.js."""
import json, os, subprocess, sys, time

HERMES_HOME = os.path.expanduser("~/.hermes")
BRIDGE_DIR = os.path.join(HERMES_HOME, "hermes-agent", "scripts", "whatsapp-bridge")

phone = sys.argv[1] if len(sys.argv) > 1 else None

NODE_SCRIPT = os.path.join(HERMES_HOME, "scripts", "vcoo", "vcoo-whatsapp-pair.js")
BRIDGE_JS = os.path.join(BRIDGE_DIR, "bridge.js")

if os.path.isfile(NODE_SCRIPT):
    cmd = ["node", NODE_SCRIPT]
    if phone:
        cmd += ["--phone", phone]
elif os.path.isfile(BRIDGE_JS):
    BRIDGE_NM = os.path.join(BRIDGE_DIR, "node_modules")
    if not os.path.isdir(BRIDGE_NM):
        print(json.dumps({"status": "installing_whatsapp"}))
        sys.stdout.flush()
        subprocess.run(["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"],
                       cwd=BRIDGE_DIR, capture_output=True, timeout=180)
    env = os.environ.copy()
    env.update({"WHATSAPP_MODE": "bot", "WHATSAPP_ALLOWED_USERS": "*"})
    if phone:
        env["WHATSAPP_ALLOWED_USERS"] = phone
    cmd = ["node", BRIDGE_JS, "--pair-only", "--pair-json"]
    env_cmd = cmd
    try:
        proc = subprocess.Popen(env_cmd, cwd=BRIDGE_DIR, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
    except FileNotFoundError:
        print(json.dumps({"error": "node not found"}))
        sys.exit(1)
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        ev = event.get("event", "")
        if ev == "qr":
            print(json.dumps({"qr": event.get("qr", ""), "status": "waiting"}))
            sys.stdout.flush()
        elif ev == "connected":
            print(json.dumps({"status": "connected", "user": event.get("user", {})}))
            sys.stdout.flush()
            proc.terminate()
            sys.exit(0)
        elif ev == "error":
            print(json.dumps({"status": "error", "error": event.get("error", "")}))
            sys.stdout.flush()
            proc.terminate()
            sys.exit(1)
    proc.wait()
    sys.exit(0)
else:
    print(json.dumps({"error": "WhatsApp bridge not found. Install Hermes first."}))
    sys.exit(1)

try:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, bufsize=1)
except FileNotFoundError:
    print(json.dumps({"error": "node not found"}))
    sys.exit(1)

waiting_for = "pairing_code" if phone else "qr"
found = False
start_time = time.time()

for line in proc.stdout:
    line = line.strip()
    if not line:
        continue
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        continue

    ev = event.get("event", "")

    if ev == "qr" and not phone:
        output = {"qr": event.get("qr", ""), "status": "waiting"}
        print(json.dumps(output))
        sys.stdout.flush()
        found = True

    elif ev == "pairing_code":
        output = {"pairing_code": event.get("code", ""), "phone": event.get("phone", ""), "status": "waiting"}
        print(json.dumps(output))
        sys.stdout.flush()
        found = True

    elif ev == "connected":
        output = {"status": "connected", "user": event.get("user", {})}
        print(json.dumps(output))
        sys.stdout.flush()
        proc.terminate()
        sys.exit(0)

    elif ev == "installing":
        print(json.dumps({"status": "installing_whatsapp"}))
        sys.stdout.flush()

    elif ev == "error":
        print(json.dumps({"status": "error", "error": event.get("error", ""), "message": event.get("message", "")}))
        sys.stdout.flush()
        proc.terminate()
        sys.exit(1)

    if found and time.time() - start_time > 120:
        break

proc.wait(timeout=60)
