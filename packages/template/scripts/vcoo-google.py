#!/usr/bin/env python3
"""
vcoo-google.py — Interfaz unificada para Google Workspace (Drive, Docs, Sheets)
Uso: python3 vcoo-google.py <servicio> <acción> [args...]

Servicios:
  drive list [query]           Listar archivos en Drive
  drive create-folder <name>   Crear carpeta
  drive upload <local-path> [mime]   Subir archivo
  drive search <query>         Buscar archivos
  drive export <file-id> <mime>  Exportar archivo (ej: application/pdf)
  
  docs create <title>          Crear documento
  docs view <doc-id>           Ver contenido
  docs append <doc-id> <text>  Añadir texto al final
  
  sheets create <title>        Crear hoja de cálculo
  sheets read <sheet-id> [range]  Leer celdas (range por defecto: A1:Z100)
  sheets write <sheet-id> <range> <json-values>  Escribir celdas
  sheets append <sheet-id> <range> <json-values>  Añadir filas
  
  calendar list [max]          Próximos eventos
"""

import json, sys, os, datetime

# ── Google API Setup ─────────────────────────────────────────────
TOKEN_PATH = os.path.expanduser("~/.hermes/google_token.json")

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_creds():
    with open(TOKEN_PATH) as f:
        tok = json.load(f)
    creds = Credentials.from_authorized_user_info(tok, scopes=tok.get('scopes', []))
    return creds

def save_creds(creds):
    with open(TOKEN_PATH, 'w') as f:
        json.dump(json.loads(creds.to_json()), f, indent=2)

# ── Drive ────────────────────────────────────────────────────────

def drive_list(query=None):
    creds = get_creds()
    svc = build('drive', 'v3', credentials=creds)
    q = query or "name != ''"
    results = svc.files().list(q=q, pageSize=20, fields="files(id, name, mimeType, size, createdTime)").execute()
    save_creds(creds)
    files = results.get('files', [])
    if not files:
        print("📂 No se encontraron archivos")
        return
    print(f"📂 {len(files)} archivos:")
    for f in files:
        mime = f['mimeType'].split('.')[-1] if '.' in f['mimeType'] else f['mimeType']
        size = f.get('size', '?')
        print(f"  [{mime:12s}] {f['name']:40s} ({f['id'][:20]}...)")

def drive_create_folder(name):
    creds = get_creds()
    svc = build('drive', 'v3', credentials=creds)
    meta = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
    f = svc.files().create(body=meta, fields='id,name').execute()
    save_creds(creds)
    print(f"✅ Carpeta creada: \"{f['name']}\" (ID: {f['id']})")

def drive_search(query):
    creds = get_creds()
    svc = build('drive', 'v3', credentials=creds)
    results = svc.files().list(q=f"name contains '{query}'", pageSize=15,
                                fields="files(id, name, mimeType)").execute()
    save_creds(creds)
    files = results.get('files', [])
    if not files:
        print(f"🔍 Sin resultados para: {query}")
        return
    print(f"🔍 Resultados para \"{query}\":")
    for f in files:
        print(f"  [{f['mimeType'].split('.')[-1]:12s}] {f['name']:40s} ({f['id'][:20]}...)")

# ── Docs ─────────────────────────────────────────────────────────

def docs_create(title):
    creds = get_creds()
    svc = build('docs', 'v1', credentials=creds)
    doc = svc.documents().create(body={'title': title}).execute()
    save_creds(creds)
    print(f"✅ Documento creado: \"{doc['title']}\"")
    print(f"   URL: https://docs.google.com/document/d/{doc['documentId']}")

def docs_view(doc_id):
    creds = get_creds()
    svc = build('docs', 'v1', credentials=creds)
    doc = svc.documents().get(documentId=doc_id).execute()
    save_creds(creds)
    print(f"📄 {doc['title']}")
    print(f"   ID: {doc['documentId']}")
    # Extract text content from document body
    body = doc.get('body', {}).get('content', [])
    text_parts = []
    for elem in body:
        for sub in elem.get('paragraph', {}).get('elements', []):
            tr = sub.get('textRun')
            if tr and tr.get('content'):
                text_parts.append(tr['content'])
    if text_parts:
        full = ''.join(text_parts)
        print(f"   {len(full)} caracteres totales")
        print("   --- Vista previa (primeros 500 chars) ---")
        print(full[:500])

def docs_append(doc_id, text):
    creds = get_creds()
    svc = build('docs', 'v1', credentials=creds)
    # Get document to find end position
    doc = svc.documents().get(documentId=doc_id).execute()
    end_index = doc.get('body', {}).get('content', [{}])[-1].get('endIndex', 1)
    
    requests = [{
        'insertText': {
            'location': {'index': end_index - 1},
            'text': '\n' + text
        }
    }]
    svc.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
    save_creds(creds)
    print(f"✅ Texto añadido al documento (índice {end_index})")

# ── Sheets ───────────────────────────────────────────────────────

def sheets_create(title):
    creds = get_creds()
    svc = build('sheets', 'v4', credentials=creds)
    spreadsheet = {'properties': {'title': title}}
    sheet = svc.spreadsheets().create(body=spreadsheet, fields='spreadsheetId,properties.title').execute()
    save_creds(creds)
    print(f"✅ Hoja creada: \"{sheet['properties']['title']}\"")
    print(f"   URL: https://docs.google.com/spreadsheets/d/{sheet['spreadsheetId']}")

def sheets_read(sheet_id, range_='A1:Z100'):
    creds = get_creds()
    svc = build('sheets', 'v4', credentials=creds)
    result = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range=range_).execute()
    save_creds(creds)
    values = result.get('values', [])
    if not values:
        print("📊 Hoja vacía")
        return
    print(f"📊 {len(values)} filas × {max(len(r) for r in values)} columnas:")
    for i, row in enumerate(values[:15]):
        print(f"  Fila {i+1}: {' | '.join(str(c)[:30] for c in row)}")
    if len(values) > 15:
        print(f"  ... y {len(values)-15} filas más")

def sheets_write(sheet_id, range_, values_json):
    creds = get_creds()
    svc = build('sheets', 'v4', credentials=creds)
    values = json.loads(values_json) if isinstance(values_json, str) else values_json
    body = {'values': values}
    result = svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=range_,
        valueInputOption='USER_ENTERED', body=body
    ).execute()
    save_creds(creds)
    print(f"✅ {result.get('updatedCells', 0)} celdas actualizadas en {range_}")

def sheets_append(sheet_id, range_, values_json):
    creds = get_creds()
    svc = build('sheets', 'v4', credentials=creds)
    values = json.loads(values_json) if isinstance(values_json, str) else values_json
    body = {'values': values}
    result = svc.spreadsheets().values().append(
        spreadsheetId=sheet_id, range=range_,
        valueInputOption='USER_ENTERED', insertDataOption='INSERT_ROWS', body=body
    ).execute()
    save_creds(creds)
    print(f"✅ {result.get('updates', {}).get('updatedCells', 0)} celdas añadidas")

# ── Calendar ─────────────────────────────────────────────────────

def calendar_list(max_=10):
    creds = get_creds()
    svc = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events = svc.events().list(calendarId='primary', timeMin=now,
                                maxResults=max_, singleEvents=True,
                                orderBy='startTime').execute()
    save_creds(creds)
    items = events.get('items', [])
    if not items:
        print("📅 No hay próximos eventos")
        return
    print(f"📅 {len(items)} próximos eventos:")
    for e in items:
        start = e['start'].get('dateTime', e['start'].get('date'))
        print(f"  {start[:16]:16s} | {e.get('summary', 'Sin título')}")

# ── Main Dispatch ────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    service = sys.argv[1]
    action = sys.argv[2]
    args = sys.argv[3:]
    
    try:
        if service == 'drive':
            if action == 'list':
                drive_list(args[0] if args else None)
            elif action == 'create-folder':
                drive_create_folder(args[0])
            elif action == 'search':
                drive_search(' '.join(args))
            elif action == 'export':
                print("drive export: pendiente de implementar")
            else:
                print(f"❌ Acción desconocida: drive {action}")
        
        elif service == 'docs':
            if action == 'create':
                docs_create(' '.join(args))
            elif action == 'view':
                docs_view(args[0])
            elif action == 'append':
                docs_append(args[0], ' '.join(args[1:]))
            else:
                print(f"❌ Acción desconocida: docs {action}")
        
        elif service == 'sheets':
            if action == 'create':
                sheets_create(' '.join(args))
            elif action == 'read':
                sheets_read(args[0], args[1] if len(args) > 1 else 'A1:Z100')
            elif action == 'write':
                sheets_write(args[0], args[1], ' '.join(args[2:]))
            elif action == 'append':
                sheets_append(args[0], args[1], ' '.join(args[2:]))
            else:
                print(f"❌ Acción desconocida: sheets {action}")
        
        elif service == 'calendar':
            if action == 'list':
                calendar_list(int(args[0]) if args else 10)
            else:
                print(f"❌ Acción desconocida: calendar {action}")
        
        else:
            print(f"❌ Servicio desconocido: {service}")
            sys.exit(1)
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
