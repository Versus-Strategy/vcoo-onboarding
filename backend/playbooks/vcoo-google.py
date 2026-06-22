#!/usr/bin/env python3
"""vcoo-google: verifica conexion con Google Workspace."""
import sys, os, json, subprocess

USAGE = "Uso: vcoo-google.py <drive|gmail> list"

def find_token():
    paths = [
        os.path.expanduser("~/.hermes/google_token.json"),
        os.path.expanduser("~/.hermes/.env"),
    ]
    for p in paths:
        if not os.path.isfile(p):
            continue
        if p.endswith(".json"):
            try:
                with open(p) as f:
                    data = json.load(f)
                t = data.get("access_token") or data.get("token")
                if t:
                    return t
            except:
                pass
        elif p.endswith(".env"):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GOOGLE_TOKEN="):
                        return line.split("=", 1)[1].strip().strip(D+S)
                    if line.startswith("GOOGLE_ACCESS_TOKEN="):
                        return line.split("=", 1)[1].strip().strip(D+S)
    return None

def run_check(service, action):
    token = find_token()
    if not token:
        return {"status": "error", "output": "Token de Google no encontrado.", "exit_code": 1}
    if service == "drive":
        url = "https://www.googleapis.com/drive/v3/files?pageSize=10&fields=files(id,name)"
        label = "Google Drive"
    elif service == "gmail":
        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=5"
        label = "Gmail"
    else:
        return {"status": "error", "output": "Servicio no soportado: " + service, "exit_code": 1}
    auth = "Authorization: Bearer " + token
    try:
        r = subprocess.run(["curl", "-sS", "-H", auth, url], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return {"status": "error", "output": "Error de red: " + r.stderr.strip(), "exit_code": 1}
        data = json.loads(r.stdout)
        if "error" in data:
            err = data["error"].get("message", str(data["error"]))
            return {"status": "error", "output": "Error de API: " + err, "exit_code": 1}
        if service == "drive":
            files = data.get("files", [])
            count = len(files)
            names = ", ".join(f["name"] for f in files[:5]) if files else "(ninguno)"
            return {"status": "ok", "output": f"{label}: {count} archivos encontrados - {names}", "exit_code": 0, "details": {"count": count}}
        else:
            messages = data.get("messages", [])
            count = len(messages)
            return {"status": "ok", "output": f"{label}: {count} mensajes encontrados", "exit_code": 0, "details": {"count": count}}
    except json.JSONDecodeError:
        return {"status": "error", "output": "Respuesta no es JSON", "exit_code": 1}
    except Exception as e:
        return {"status": "error", "output": "Error: " + str(e), "exit_code": 1}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(USAGE)
        sys.exit(1)
    service = sys.argv[1].lower()
    action = sys.argv[2].lower()
    result = run_check(service, action)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(result["exit_code"])
