#!/usr/bin/env python3
"""
vcoo-trello.py — Interfaz unificada para Trello vía REST API
Uso: python3 vcoo-trello.py <acción> [args...]

Acciones:
  boards                          Listar tableros
  lists <board-id>                Listar listas
  cards <board-id>                Listar tarjetas
  card <card-id>                  Detalle de tarjeta
  create-card <list-id> <name>    Crear tarjeta
  move-card <card-id> <list-id>   Mover tarjeta
  comment <card-id> <text>        Comentar
  labels <board-id>               Listar etiquetas
  add-label <card-id> <label-id>  Poner etiqueta
  vs-cards                        Atajo para tarjetas de VERSUS_Project_Management
  vs-labels                       Atajo para etiquetas de VERSUS
  vs-lists                        Atajo para listas de VERSUS
"""

import json, os, sys
import urllib.parse, urllib.request, urllib.error

# ─── Cargar credenciales ─────────────────────────────────────────
ENV_FILE = os.path.expanduser("~/.env.trello")
if not os.path.exists(ENV_FILE):
    print(f"❌ No se encuentra {ENV_FILE}")
    sys.exit(1)

env = {}
with open(ENV_FILE) as f:
    for line in f:
        line = line.strip()
        if line and '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            env[k] = v

API_KEY = env.get('TRELLO_API_KEY', '')
TOKEN = env.get('TRELLO_TOKEN', '')
if not API_KEY or not TOKEN:
    print("❌ TRELLO_API_KEY o TRELLO_TOKEN no encontrados en .env.trello")
    sys.exit(1)

VERSUS_BOARD = "6a2342c874546dfd2f5aa5cd"
BASE = "https://api.trello.com/1"

# ─── Helpers ─────────────────────────────────────────────────────

def trello_get(path, params=None):
    """GET request a Trello API"""
    p = {'key': API_KEY, 'token': TOKEN}
    if params:
        p.update(params)
    qs = urllib.parse.urlencode(p)
    url = f"{BASE}{path}?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.reason}")
        body = e.read().decode()
        if body:
            print(f"   {body[:200]}")
        sys.exit(1)

def trello_post(path, data):
    """POST request a Trello API"""
    p = {'key': API_KEY, 'token': TOKEN}
    p.update(data)
    qs = urllib.parse.urlencode(p)
    url = f"{BASE}{path}?{qs}"
    try:
        req = urllib.request.Request(url, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.reason}")
        body = e.read().decode()
        if body:
            print(f"   {body[:200]}")
        sys.exit(1)

def trello_put(path, data):
    """PUT request a Trello API"""
    p = {'key': API_KEY, 'token': TOKEN}
    p.update(data)
    qs = urllib.parse.urlencode(p)
    url = f"{BASE}{path}?{qs}"
    try:
        req = urllib.request.Request(url, method='PUT')
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.reason}")
        body = e.read().decode()
        if body:
            print(f"   {body[:200]}")
        sys.exit(1)

# ─── Acciones ────────────────────────────────────────────────────

def boards():
    data = trello_get('/members/me/boards', {'fields': 'name,id,url'})
    print(f"📋 {len(data)} tableros:")
    for b in sorted(data, key=lambda x: x['name']):
        print(f"  • {b['name']}")
        print(f"    ID: {b['id']}")

def lists(board_id):
    data = trello_get(f'/boards/{board_id}/lists', {'fields': 'name,id'})
    print(f"📋 Listas ({len(data)}):")
    for l in data:
        print(f"  □ {l['name']:30s} {l['id']}")

def cards(board_id):
    data = trello_get(f'/boards/{board_id}/cards', {'fields': 'name,id,idList,due,labels,url'})
    print(f"📇 {len(data)} tarjetas:")
    for c in sorted(data, key=lambda x: x.get('dateLastActivity', x['id']), reverse=True):
        lbls = ', '.join(l.get('name','') for l in c.get('labels', []))
        due = c.get('due','')[:10] if c.get('due') else ''
        print(f"  • {c['name']:50s} {due:12s} [{lbls}]")
        print(f"    {c['url']}")

def card(card_id):
    data = trello_get(f'/cards/{card_id}', {'fields': 'name,desc,idList,due,labels,url,dateLastActivity'})
    print(json.dumps(data, indent=2, ensure_ascii=False))

def create_card(list_id, name, desc=''):
    data = {'idList': list_id, 'name': name}
    if desc:
        data['desc'] = desc
    result = trello_post('/cards', data)
    print(f"✅ Tarjeta creada: \"{result.get('name', '?')}\"")
    print(f"   URL: {result.get('url', '?')}")

def move_card(card_id, list_id):
    result = trello_put(f'/cards/{card_id}', {'idList': list_id})
    print(f"✅ Tarjeta movida: \"{result.get('name', '?')}\"")

def comment(card_id, text):
    trello_post(f'/cards/{card_id}/actions/comments', {'text': text})
    print(f"✅ Comentario añadido")

def labels(board_id):
    data = trello_get(f'/boards/{board_id}/labels', {'fields': 'name,id,color'})
    print(f"🏷️  {len(data)} etiquetas:")
    for l in data:
        n = l.get('name','') or '(sin nombre)'
        c = l.get('color','')
        print(f"  • {n:25s} color={c:10s} ID: {l['id']}")

def add_label(card_id, label_id):
    trello_post(f'/cards/{card_id}/idLabels', {'value': label_id})
    print(f"✅ Etiqueta añadida")

# ─── VS (VERSUS) atajos ─────────────────────────────────────────

def vs_cards():
    cards(VERSUS_BOARD)

def vs_lists():
    lists(VERSUS_BOARD)

def vs_labels():
    labels(VERSUS_BOARD)

# ─── Dispatch ────────────────────────────────────────────────────

if __name__ == '__main__':
    actions = {
        'boards': boards,
        'lists': lambda: lists(sys.argv[2]),
        'cards': lambda: cards(sys.argv[2]),
        'card': lambda: card(sys.argv[2]),
        'create-card': lambda: create_card(sys.argv[2], sys.argv[3], ' '.join(sys.argv[4:])),
        'move-card': lambda: move_card(sys.argv[2], sys.argv[3]),
        'comment': lambda: comment(sys.argv[2], ' '.join(sys.argv[3:])),
        'labels': lambda: labels(sys.argv[2]),
        'add-label': lambda: add_label(sys.argv[2], sys.argv[3]),
        'vs-cards': vs_cards,
        'vs-lists': vs_lists,
        'vs-labels': vs_labels,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in actions:
        print(__doc__)
        sys.exit(0 if len(sys.argv) < 2 else 1)

    action = sys.argv[1]
    try:
        actions[action]()
    except TypeError as e:
        print(f"❌ Argumentos insuficientes para '{action}'. Revisa el uso.")
        print(f"   Error: {e}")
        sys.exit(1)
