#!/usr/bin/env python3
"""
vcoo-email.py — Interfaz para Gmail vía Google API
Uso: python3 vcoo-email.py <acción> [args...]

Acciones:
  list [N]                      Listar últimos N correos (defecto: 10)
  read <message-id>             Leer contenido de un correo
  search <query>                Buscar correos
  send <to> <subject> <body>    Enviar correo
  draft <to> <subject> <body>   Crear borrador
  labels                        Listar etiquetas/carpetas
  recent [N]                    Últimos N correos importantes
"""

import json, os, sys, base64, email
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

TOKEN_PATH = os.path.expanduser('~/.hermes/google_token.json')

def get_creds():
    with open(TOKEN_PATH) as f:
        tok = json.load(f)
    creds = Credentials.from_authorized_user_info(tok, scopes=tok.get('scopes', []))
    return creds

def save_creds(creds):
    with open(TOKEN_PATH, 'w') as f:
        json.dump(json.loads(creds.to_json()), f, indent=2)

def decode_body(payload):
    """Decode message body from base64"""
    if 'parts' in payload:
        for part in payload['parts']:
            body = part.get('body', {})
            mime = part.get('mimeType', '')
            if mime == 'text/plain' and 'data' in body:
                return base64.urlsafe_b64decode(body['data'].encode('UTF-8')).decode('UTF-8', errors='replace')
            elif mime == 'text/html' and 'data' in body:
                return base64.urlsafe_b64decode(body['data'].encode('UTF-8')).decode('UTF-8', errors='replace')[:500]
        # Recursive check nested parts
        for part in payload['parts']:
            if 'parts' in part:
                result = decode_body(part)
                if result:
                    return result
    body = payload.get('body', {})
    if 'data' in body:
        return base64.urlsafe_b64decode(body['data'].encode('UTF-8')).decode('UTF-8', errors='replace')
    return '(sin contenido visible)'

def get_header(headers, name):
    for h in headers:
        if h['name'].lower() == name.lower():
            return h['value']
    return ''

def list_messages(n=10):
    creds = get_creds()
    svc = build('gmail', 'v1', credentials=creds)
    results = svc.users().messages().list(userId='me', maxResults=n, q='in:inbox').execute()
    save_creds(creds)
    msgs = results.get('messages', [])
    if not msgs:
        print("📬 Bandeja vacía")
        return
    print(f"📬 Últimos {len(msgs)} correos en inbox:")
    for i, m in enumerate(msgs, 1):
        msg = svc.users().messages().get(userId='me', id=m['id'], format='metadata',
                                          metadataHeaders=['From','Subject','Date']).execute()
        headers = msg.get('payload', {}).get('headers', [])
        fr = get_header(headers, 'From')
        subj = get_header(headers, 'Subject') or '(sin asunto)'
        date = get_header(headers, 'Date')[:25]
        print(f"  {i:2d}. [{m['id']}] {fr[:35]:35s} | {subj[:50]:50s}")
    save_creds(svc._http.credentials)

def read_message(msg_id):
    creds = get_creds()
    svc = build('gmail', 'v1', credentials=creds)
    msg = svc.users().messages().get(userId='me', id=msg_id, format='full').execute()
    save_creds(creds)
    headers = msg.get('payload', {}).get('headers', [])
    fr = get_header(headers, 'From')
    to = get_header(headers, 'To')
    subj = get_header(headers, 'Subject') or '(sin asunto)'
    date = get_header(headers, 'Date')
    body = decode_body(msg.get('payload', {}))
    print(f"📧 De:        {fr}")
    print(f"   Para:      {to}")
    print(f"   Asunto:    {subj}")
    print(f"   Fecha:     {date}")
    print(f"   {'─'*50}")
    print(body[:2000])
    if len(body) > 2000:
        print(f"\n   ... ({len(body)-2000} caracteres más)")

def search_messages(query):
    creds = get_creds()
    svc = build('gmail', 'v1', credentials=creds)
    results = svc.users().messages().list(userId='me', q=query, maxResults=15).execute()
    save_creds(creds)
    msgs = results.get('messages', [])
    if not msgs:
        print(f"🔍 Sin resultados para: {query}")
        return
    print(f"🔍 {len(msgs)} resultados para \"{query}\":")
    for m in msgs[:15]:
        msg = svc.users().messages().get(userId='me', id=m['id'], format='metadata',
                                          metadataHeaders=['From','Subject','Date']).execute()
        headers = msg.get('payload', {}).get('headers', [])
        fr = get_header(headers, 'From')
        subj = get_header(headers, 'Subject') or '(sin asunto)'
        print(f"  • {fr[:30]:30s} | {subj[:50]:50s}")
    save_creds(svc._http.credentials)

def send_message(to, subject, body_text):
    creds = get_creds()
    svc = build('gmail', 'v1', credentials=creds)
    msg = EmailMessage()
    msg.set_content(body_text)
    msg['To'] = to
    msg['Subject'] = subject
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = svc.users().messages().send(userId='me', body={'raw': encoded}).execute()
    save_creds(creds)
    print(f"✅ Correo enviado a {to}")
    print(f"   Asunto: {subject}")
    print(f"   ID: {result.get('id', '?')}")

def create_draft(to, subject, body_text):
    creds = get_creds()
    svc = build('gmail', 'v1', credentials=creds)
    msg = EmailMessage()
    msg.set_content(body_text)
    msg['To'] = to
    msg['Subject'] = subject
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = svc.users().messages().draft().create(userId='me', body={'message': {'raw': encoded}}).execute()
    save_creds(creds)
    draft_id = result.get('id', '?')
    print(f"✅ Borrador creado para \"{subject}\" (ID: {draft_id})")

def list_labels():
    creds = get_creds()
    svc = build('gmail', 'v1', credentials=creds)
    results = svc.users().labels().list(userId='me').execute()
    save_creds(creds)
    labels = results.get('labels', [])
    print(f"🏷️  {len(labels)} etiquetas:")
    for l in sorted(labels, key=lambda x: x['name']):
        print(f"  • {l['name']:30s} ({l['type']})")

if __name__ == '__main__':
    actions = {
        'list': lambda: list_messages(int(sys.argv[2]) if len(sys.argv) > 2 else 10),
        'read': lambda: read_message(sys.argv[2]),
        'search': lambda: search_messages(' '.join(sys.argv[2:])),
        'send': lambda: send_message(sys.argv[2], sys.argv[3], ' '.join(sys.argv[4:])),
        'draft': lambda: create_draft(sys.argv[2], sys.argv[3], ' '.join(sys.argv[4:])),
        'labels': list_labels,
        'recent': lambda: list_messages(int(sys.argv[2]) if len(sys.argv) > 2 else 10),
    }

    if len(sys.argv) < 2 or sys.argv[1] not in actions:
        print(__doc__)
        sys.exit(0 if len(sys.argv) < 2 else 1)

    try:
        actions[sys.argv[1]]()
    except TypeError as e:
        print(f"❌ Argumentos insuficientes para '{sys.argv[1]}'. Revisa el uso.")
        print(f"   Error: {e}")
        sys.exit(1)
    except HttpError as e:
        print(f"❌ Error de API: {e}")
        sys.exit(1)
