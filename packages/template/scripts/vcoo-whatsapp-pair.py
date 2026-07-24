#!/usr/bin/env python3
"""VCOO WhatsApp pairing — captures QR or pairing code from Node script, exits immediately."""
import json, os, signal, subprocess, sys, time

HERMES_HOME = os.path.expanduser("~/.hermes")
BRIDGE_DIR = os.path.join(HERMES_HOME, "hermes-agent", "scripts", "whatsapp-bridge")
BRIDGE_NM = os.path.join(BRIDGE_DIR, "node_modules")

_NODE = "node"
for _p in [
    os.path.join(HERMES_HOME, "node", "bin", "node"),
    os.path.join(HERMES_HOME, "hermes-agent", "node", "bin", "node"),
]:
    if os.path.isfile(_p):
        _NODE = _p
        break

phone = sys.argv[1] if len(sys.argv) > 1 else None
NODE_SCRIPT = os.path.join(HERMES_HOME, "scripts", "vcoo", "vcoo-whatsapp-pair.js")

if not os.path.isfile(NODE_SCRIPT):
    print(json.dumps({"error": "vcoo-whatsapp-pair.js not found"}))
    sys.exit(1)

_env = os.environ.copy()
if os.path.isdir(BRIDGE_NM):
    _env.setdefault("NODE_PATH", BRIDGE_NM)

# Only wait for first output event (QR or pairing code), then exit
# The Node process keeps running in background for pairing
cmd = [_NODE, NODE_SCRIPT, "--timeout", "120"]
if phone:
    cmd += ["--phone", phone]

try:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, bufsize=1, env=_env, preexec_fn=os.setsid)
except FileNotFoundError:
    print(json.dumps({"error": "node not found"}))
    sys.exit(1)

# Read stdout until we get a usable event or timeout
start = time.time()
while time.time() - start < 30:
    line = proc.stdout.readline()
    if not line:
        time.sleep(0.5)
        continue
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
        # Background the process — don't wait for connection
        os.killpg(os.getpgid(proc.pid), signal.SIGCONT)
        sys.exit(0)

    elif ev == "pairing_code":
        print(json.dumps({
            "pairing_code": event.get("code", ""),
            "phone": event.get("phone", ""),
            "status": "waiting"
        }))
        sys.stdout.flush()
        # Background the process
        os.killpg(os.getpgid(proc.pid), signal.SIGCONT)
        sys.exit(0)

    elif ev == "installing":
        print(json.dumps({"status": "installing_whatsapp"}))
        sys.stdout.flush()

    elif ev == "connected":
        print(json.dumps({"status": "connected", "user": event.get("user", {})}))
        sys.stdout.flush()
        proc.terminate()
        sys.exit(0)

    elif ev == "error":
        print(json.dumps({"status": "error", "error": event.get("error", ""), "message": event.get("message", "")}))
        sys.stdout.flush()
        proc.terminate()
        sys.exit(1)

# Timeout reading first event
proc.kill()
print(json.dumps({"status": "timeout"}))
sys.exit(1)
