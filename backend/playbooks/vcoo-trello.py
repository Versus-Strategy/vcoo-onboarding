#!/usr/bin/env python3
"""vcoo-trello: verifica conexión con Trello (lista de boards)."""
import sys, os, json, subprocess

USAGE = "Uso: vcoo-trello.py boards"


def find_credentials():
    """Busca TRELLO_API_KEY y TRELLO_TOKEN en ~/.hermes/.env."""
    env_file = os.path.expanduser("~/.hermes/.env")
    key, token = None, None
    if os.path.isfile(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("TRELLO_API_KEY="):
                    key = line.split("=", 1)[1].strip("\"'")
                elif line.startswith("TRELLO_TOKEN="):
                    token = line.split("=", 1)[1].strip("\"'")
    return key, token


def list_boards():
    """Lista los boards de Trello usando la API REST."""
    key, token = find_credentials()

    if not key or not token:
        return {
            "status": "error",
            "output": (
                "Credenciales de Trello no encontradas. Asegúrate de haber configurado "
                "TRELLO_API_KEY y TRELLO_TOKEN en ~/.hermes/.env desde el wizard."
            ),
            "exit_code": 1,
        }

    url = f"https://api.trello.com/1/members/me/boards?key={key}&token={token}&fields=name"

    try:
        r = subprocess.run(
            ["curl", "-sS", url],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return {"status": "error", "output": f"Error de red: {r.stderr.strip()}", "exit_code": 1}

        data = json.loads(r.stdout)

        if isinstance(data, dict) and data.get("error"):
            return {"status": "error", "output": f"Error de API Trello: {data.get('error', data)}", "exit_code": 1}
        if isinstance(data, str) and "invalid" in data.lower():
            return {"status": "error", "output": f"Credenciales inválidas: {data}", "exit_code": 1}

        if not isinstance(data, list):
            return {"status": "error", "output": f"Respuesta inesperada: {r.stdout[:200]}", "exit_code": 1}

        count = len(data)
        names = ", ".join(b["name"] for b in data[:5]) if data else "(ninguno)"
        return {
            "status": "ok",
            "output": f"Trello: {count} boards encontrados — {names}",
            "exit_code": 0,
            "details": {"count": count, "boards": data[:5]},
        }

    except json.JSONDecodeError:
        return {"status": "error", "output": f"Respuesta no es JSON: {r.stdout[:200]}", "exit_code": 1}
    except Exception as e:
        return {"status": "error", "output": f"Error: {e}", "exit_code": 1}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1].lower() != "boards":
        print(USAGE)
        sys.exit(1)

    result = list_boards()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(result["exit_code"])
