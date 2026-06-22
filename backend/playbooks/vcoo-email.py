#!/usr/bin/env python3
import sys, os, json, subprocess

USAGE = 'Uso: vcoo-email.py list <N>'

def find_token():
    paths = [
        os.path.expanduser('~/.hermes/google_token.json'),
        os.path.expanduser('~/.hermes/.env'),
    ]
    for p in paths:
        if not os.path.isfile(p):
            continue
        if p.endswith('.json'):
            try:
                with open(p) as f:
                    data = json.load(f)
                token = data.get('access_token') or data.get('token')
                if token:
                    return token
            except:
                pass
        elif p.endswith('.env'):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GOOGLE_TOKEN=') or line.startswith('GOOGLE_ACCESS_TOKEN='):
                        val = line.split('=', 1)[1]
                        return val.strip().strip(chr(34) + chr(39))
    return None

def list_emails(count=3):
    token = find_token()
    if not token:
        return {'status': 'error', 'output': 'Token de Google no encontrado.', 'exit_code': 1}
    url = 'https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=' + str(count)
    auth = 'Authorization: Bearer ' + token
    try:
        r = subprocess.run(['curl', '-sS', '-H', auth, url], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return {'status': 'error', 'output': 'Error de red: ' + r.stderr.strip(), 'exit_code': 1}
        data = json.loads(r.stdout)
        if 'error' in data:
            err = data['error'].get('message', str(data['error']))
            return {'status': 'error', 'output': 'Error de Gmail API: ' + err, 'exit_code': 1}
        messages = data.get('messages', [])
        found = len(messages)
        return {'status': 'ok', 'output': 'Gmail: {} mensajes recientes encontrados'.format(found), 'exit_code': 0, 'details': {'count': found}}
    except json.JSONDecodeError:
        return {'status': 'error', 'output': 'Respuesta no es JSON', 'exit_code': 1}
    except Exception as e:
        return {'status': 'error', 'output': 'Error: ' + str(e), 'exit_code': 1}

if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1].lower() != 'list':
        print(USAGE)
        sys.exit(1)
    try:
        n = int(sys.argv[2])
    except ValueError:
        print(USAGE)
        sys.exit(1)
    result = list_emails(n)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(result['exit_code'])
