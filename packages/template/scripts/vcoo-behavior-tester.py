#!/usr/bin/env python3
"""
vcoo-behavior-tester.py — Behavioral tests para VCOO Virtual
=============================================================
Uso: python3 vcoo-behavior-tester.py [opciones]

Ejecuta prompts en lenguaje natural contra el agente VCOO y evalúa
si el agente completa correctamente cada tarea (LLM judge + side effects).

Independiente del onboarding — solo necesita:
  - hermes CLI instalado y configurado
  - OPENROUTER_API_KEY en el entorno
  - Skills VCOO cargadas

Opciones:
  --json         Solo salida JSON (para consumo programático)
  --quiet        Sin output por terminal
  --id ID        Ejecutar solo un escenario específico
  --help         Este mensaje

Salida:
  - test-output/behavioral/report-{timestamp}.json
  - test-output/behavioral/logs/{test_id}.log
  - Resumen por terminal
"""

import os
import sys
import json
import subprocess
import datetime
import glob
import urllib.request
import traceback
import tempfile
import shutil
import re

# ─── Paths ──────────────────────────────────────────────────

TEMPLATE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Auto-detección de raíz (misma lógica que vcoo-tester.py)
_VCOO_ROOT_MARKERS = ['.vcoo-root', 'README.md', 'config.yaml', 'install.sh']
_KNOWN_TEMPLATE_LOCATIONS = [
    os.path.expanduser('~/versus/vcoo-template'),
    '/opt/vcoo-template',
    os.path.join(os.path.dirname(TEMPLATE_DIR), 'vcoo-template'),
]

def _find_template_root(start_dir):
    for marker in _VCOO_ROOT_MARKERS:
        if os.path.exists(os.path.join(start_dir, marker)):
            return start_dir
    for loc in _KNOWN_TEMPLATE_LOCATIONS:
        for marker in _VCOO_ROOT_MARKERS:
            if os.path.exists(os.path.join(loc, marker)):
                return loc
    return start_dir

TEMPLATE_DIR = _find_template_root(TEMPLATE_DIR)
TEST_OUTPUT = os.path.join(TEMPLATE_DIR, 'test-output', 'behavioral')
LOGS_DIR = os.path.join(TEST_OUTPUT, 'logs')
CONFIG_FILE = os.path.join(TEMPLATE_DIR, 'configs', 'behavioral-tests.yaml')

VERSION = "1.0.0"

# ─── Colores ────────────────────────────────────────────────

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

def c(status):
    if status == 'PASS': return f"{Colors.GREEN}✓{Colors.NC}"
    if status == 'FAIL': return f"{Colors.RED}✗{Colors.NC}"
    if status == 'SKIP': return f"{Colors.YELLOW}⊘{Colors.NC}"
    if status == 'WARN': return f"{Colors.YELLOW}⚠{Colors.NC}"
    return f"{Colors.BLUE}?{Colors.NC}"


# ─── Detección de secretos ─────────────────────────────────

def detect_secrets():
    """Detectar secretos disponibles (misma lógica que vcoo-tester.py)"""
    secrets = {}
    env_paths = [
        os.path.expanduser('~/.hermes/.env'),
        os.path.join(TEMPLATE_DIR, '.env'),
        os.path.join(TEMPLATE_DIR, '.env.test'),
    ]
    for path in env_paths:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        k, v = line.split('=', 1)
                        secrets[k.strip()] = v.strip().strip('"').strip("'")

    # Trello env
    trello_path = os.path.expanduser('~/versus/.env.trello')
    if os.path.exists(trello_path):
        with open(trello_path) as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    secrets[k.strip()] = v.strip().strip('"').strip("'")

    # Google OAuth token
    google_path = os.path.expanduser('~/.hermes/google_token.json')
    if os.path.exists(google_path):
        try:
            with open(google_path) as f:
                tok = json.load(f)
            if tok.get('access_token') or tok.get('refresh_token'):
                secrets['GOOGLE_OAUTH'] = 'configured'
                secrets['_GOOGLE_TOKEN_PATH'] = google_path
            else:
                secrets['GOOGLE_OAUTH'] = 'expired'
        except (json.JSONDecodeError, IOError):
            secrets['GOOGLE_OAUTH'] = 'corrupt'

    return secrets


def check_skip_condition(condition_key, secrets, skip_conditions):
    """Check if a scenario should be skipped based on its when_skip condition"""
    if condition_key is None or condition_key == 'null':
        return None  # No skip condition

    if condition_key == 'missing_openrouter':
        if not secrets.get('OPENROUTER_API_KEY') or '__TEST_PLACEHOLDER__' in str(secrets.get('OPENROUTER_API_KEY', '')):
            return skip_conditions.get('missing_openrouter', 'OPENROUTER_API_KEY no disponible')

    elif condition_key == 'missing_google_token':
        if secrets.get('GOOGLE_OAUTH') != 'configured':
            return skip_conditions.get('missing_google_token', 'Token de Google OAuth no disponible')

    elif condition_key == 'missing_trello':
        if not secrets.get('TRELLO_API_KEY') or not secrets.get('TRELLO_TOKEN'):
            return skip_conditions.get('missing_trello', 'Credenciales Trello no configuradas')

    elif condition_key == 'missing_hermes':
        if not shutil.which('hermes'):
            return skip_conditions.get('missing_hermes', 'hermes CLI no disponible')

    return None


def find_hermes():
    """Find hermes CLI in PATH or common installation locations"""
    path = shutil.which('hermes')
    if path:
        return path
    for loc in [
        os.path.expanduser('~/.local/bin/hermes'),
        os.path.expanduser('~/.hermes/scripts/vcoo/.venv/bin/hermes'),
        '/usr/local/bin/hermes',
    ]:
        if os.path.exists(loc):
            return loc
    return None


# ─── Side effects ──────────────────────────────────────────

class SideEffectChecker:
    """Verifica efectos secundarios de la acción del agente (creación de PDFs, etc.)"""

    # Directorios a escanear para side effects
    EXTRA_SCAN_DIRS = [
        '/tmp',
        os.path.expanduser('~'),
    ]

    def __init__(self, workdir):
        self.workdir = workdir
        self.before = {}

    def snapshot(self):
        """Tomar snapshot de archivos antes de la acción"""
        self.before = self._scan()

    def _scan(self):
        """Escanear archivos PDF en todos los directorios relevantes"""
        files = {}
        dirs_to_scan = [self.workdir] + self.EXTRA_SCAN_DIRS
        for d in dirs_to_scan:
            if not os.path.isdir(d):
                continue
            for f in glob.glob(os.path.join(d, '**/*.pdf'), recursive=True):
                try:
                    files[os.path.relpath(f, self.workdir)] = os.path.getsize(f)
                except OSError:
                    pass
        return files

    def check(self, side_effects_config):
        """Verificar side effects después de la acción"""
        if side_effects_config is None:
            return {'status': 'not_checked', 'detail': 'Sin side effects configurados'}

        after = self._scan()
        new_files = {}
        for path, size in after.items():
            if path not in self.before:
                new_files[path] = size

        if not new_files:
            return {
                'status': 'absent',
                'detail': 'No se encontraron archivos PDF nuevos tras la ejecución'
            }

        # Verificar nombre esperado
        name_pattern = side_effects_config.get('name_pattern', '')
        extension = side_effects_config.get('extension', '.pdf')
        min_size = side_effects_config.get('min_size_bytes', 0)

        matching = []
        for path, size in new_files.items():
            match_name = True
            if name_pattern and name_pattern.lower() not in path.lower():
                match_name = False
            match_size = size >= min_size

            if match_name and match_size:
                matching.append(path)

        if matching:
            return {
                'status': 'present',
                'detail': f"Archivos creados: {', '.join(matching)}",
                'files': matching
            }

        # Hubo archivos nuevos pero no cumplen criterios
        detail_parts = []
        if name_pattern:
            detail_parts.append(f"ninguno contenía '{name_pattern}'")
        if min_size:
            detail_parts.append(f"ninguno superaba {min_size} bytes")
        return {
            'status': 'mismatch',
            'detail': 'Archivos nuevos encontrados pero no cumplen criterios: ' + ', '.join(detail_parts),
            'files': list(new_files.keys())
        }


# ─── LLM Judge ─────────────────────────────────────────────

class LLMJudge:
    """Evalúa la respuesta del agente usando un LLM (OpenRouter)"""

    JUDGE_SYSTEM_PROMPT = """Eres un evaluador riguroso de asistentes AI. Tu tarea es determinar si el asistente completó correctamente la tarea solicitada por el usuario.

CRITERIOS DE EVALUACIÓN:

ÉXITO (completed=true):
- El asistente ejecutó la acción solicitada y PRESENTÓ resultados concretos.
- Para calendario: lista eventos con fechas, horas, nombres.
- Para email: muestra remitentes, asuntos, fragmentos de correos.
- Para PDFs: confirma que generó el archivo, dice el nombre y/o la ruta.
- Para Drive: lista archivos con nombres y tipos.
- Para Trello: lista tableros o tarjetas con nombres.
- Para búsqueda web: devuelve información actualizada con fuentes.

FALLO (completed=false):
- El asistente dice "no puedo", "lo siento", "no tengo acceso", "no tengo permiso", "no estoy configurado para".
- El asistente dice "puedo ayudarte a crear" o "te recomiendo que" sin ejecutar.
- El asistente responde con una explicación genérica sin datos concretos.
- El asistente da un saludo o respuesta evasiva sin relación con la tarea.
- El asistente describe lo que HARÍA pero no muestra resultados.

Responde ÚNICAMENTE con un JSON de una línea:
{"completed": true, "explanation": "Razón breve del veredicto"}
O:
{"completed": false, "explanation": "Razón breve del fallo"}"""

    def __init__(self, api_key, judge_model=None):
        self.api_key = api_key
        self.judge_model = judge_model or "openai/gpt-4o-mini"
        self.last_raw = ""

    def judge(self, task_prompt, agent_response):
        """Evaluar si la respuesta del agente completa correctamente la tarea"""
        user_prompt = f"""TAREA DEL USUARIO (lo que pidió): {task_prompt}

RESPUESTA DEL ASISTENTE (lo que respondió): {agent_response}"""

        data = json.dumps({
            "model": self.judge_model,
            "messages": [
                {"role": "system", "content": self.JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0,
            "max_tokens": 300
        }).encode()

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://vcoo.versus.strategy",
                "X-Title": "VCOO Behavioral Tester"
            }
        )

        try:
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read())
            content = result['choices'][0]['message']['content'].strip()
            self.last_raw = content

            # Parsear JSON de la respuesta
            match = re.search(r'\{[^}]*\}', content)
            if match:
                parsed = json.loads(match.group())
                return {
                    'completed': parsed.get('completed', False),
                    'explanation': parsed.get('explanation', content)
                }
            return {'completed': False, 'explanation': f'No se pudo parsear respuesta del juez: {content}'}

        except Exception as e:
            return {'completed': False, 'explanation': f'Error del juez LLM: {e}'}


# ─── Motor de tests ────────────────────────────────────────

class BehaviorTestRunner:
    """Ejecuta los escenarios de test comportamental"""

    def __init__(self, scenarios, secrets, quiet=False, judge_model=None, ci=False):
        self.scenarios = scenarios
        self.secrets = secrets
        self.quiet = quiet
        self.ci = ci
        self.results = []
        self.start_time = datetime.datetime.now(datetime.timezone.utc)

        # Inicializar judge si hay API key
        api_key = secrets.get('OPENROUTER_API_KEY', '')
        if api_key and '__TEST_PLACEHOLDER__' not in api_key:
            self.judge = LLMJudge(api_key, judge_model)
        else:
            self.judge = None

        # Preparar directorios de output
        os.makedirs(LOGS_DIR, exist_ok=True)

    def log(self, test_id, content):
        path = os.path.join(LOGS_DIR, f"{test_id}.log")
        with open(path, 'w') as f:
            f.write(content)
        return path

    def _get_hermes_env(self):
        """Preparar entorno para hermes -z"""
        env = os.environ.copy()
        # Asegurar que OPENROUTER_API_KEY está en el entorno
        if self.secrets.get('OPENROUTER_API_KEY'):
            env['OPENROUTER_API_KEY'] = self.secrets['OPENROUTER_API_KEY']
        return env

    def run_scenario(self, scenario):
        """Ejecutar un escenario completo"""
        sid = scenario['id']
        name = scenario['name']
        prompt = scenario['prompt']
        severity = scenario.get('severity', 'medium')
        side_effects_config = scenario.get('side_effects')
        skip_condition = scenario.get('when_skip')

        if not self.quiet:
            print(f"\n{Colors.CYAN}── Escenario: {name}{Colors.NC}")

        # ── 1. Verificar skip condition ──────────────────────
        skip_reason = check_skip_condition(
            skip_condition, self.secrets,
            self.scenarios.get('skip_conditions', {})
        )
        if skip_reason:
            result = {
                'id': sid, 'name': name, 'prompt': prompt,
                'status': 'SKIP', 'severity': severity,
                'detail': skip_reason,
                'judge_verdict': None, 'side_effect': None,
                'agent_response': '',
                'log_file': '',
            }
            log_content = f"[{sid}] {name}\nStatus: SKIP\nReason: {skip_reason}\n"
            result['log_file'] = self.log(sid, log_content)
            self.results.append(result)
            if not self.quiet:
                print(f"  {c('SKIP')} {skip_reason}")
            return result

        # ── 2. Verificar que hermes CLI existe ────────────────
        hermes_path = find_hermes()
        if not hermes_path:
            result = {
                'id': sid, 'name': name, 'prompt': prompt,
                'status': 'SKIP', 'severity': severity,
                'detail': 'hermes CLI no disponible en el PATH ni en ubicaciones comunes',
                'judge_verdict': None, 'side_effect': None,
                'agent_response': '',
                'log_file': '',
            }
            log_content = f"[{sid}] {name}\nStatus: SKIP\nReason: hermes CLI no disponible\n"
            result['log_file'] = self.log(sid, log_content)
            self.results.append(result)
            if not self.quiet:
                print(f"  {c('SKIP')} hermes CLI no instalado")
            return result

        # ── 3. Snapshot previo (side effects) ────────────────
        side_checker = SideEffectChecker(TEMPLATE_DIR)
        if side_effects_config:
            side_checker.snapshot()

        # ── 4. Ejecutar prompt contra el agente ──────────────
        if not self.quiet:
            print(f"  Prompt: \"{prompt[:80]}{'...' if len(prompt) > 80 else ''}\"")
            print(f"  Ejecutando agente... ", end='')

        try:
            proc = subprocess.run(
                [hermes_path, '-z', prompt, '--yolo'],
                capture_output=True, text=True, timeout=120,
                env=self._get_hermes_env()
            )
            agent_response = proc.stdout.strip()
            agent_stderr = proc.stderr.strip()

            if not self.quiet:
                if agent_response:
                    preview = agent_response[:100].replace('\n', ' ')
                    print(f"Responde: \"{preview}{'...' if len(agent_response) > 100 else ''}\"")
                else:
                    print("(respuesta vacía)")

        except subprocess.TimeoutExpired:
            agent_response = ''
            agent_stderr = 'TIMEOUT'
            if not self.quiet:
                print(f"{Colors.RED}TIMEOUT{Colors.NC}")
        except FileNotFoundError:
            agent_response = ''
            agent_stderr = 'hermes CLI no encontrado'
            result = {
                'id': sid, 'name': name, 'prompt': prompt,
                'status': 'SKIP', 'severity': severity,
                'detail': 'hermes CLI no encontrado',
                'judge_verdict': None, 'side_effect': None,
                'agent_response': '',
                'log_file': '',
            }
            log_content = f"[{sid}] {name}\nStatus: SKIP\nReason: hermes CLI no encontrado\n"
            result['log_file'] = self.log(sid, log_content)
            self.results.append(result)
            return result

        # ── 5. Verificar side effects ────────────────────────
        side_result = None
        if side_effects_config:
            side_result = side_checker.check(side_effects_config)
            if not self.quiet:
                detail = side_result['detail'][:80]
                icon = c('PASS') if side_result['status'] == 'present' else c('FAIL')
                print(f"  Side effect: {icon} {detail}")

        # ── 6. Evaluar con LLM judge ─────────────────────────
        judge_verdict = None
        if self.judge and agent_response:
            if not self.quiet:
                print(f"  Evaluando con juez LLM... ", end='')

            judge_verdict = self.judge.judge(prompt, agent_response)
            if not self.quiet:
                icon = c('PASS') if judge_verdict['completed'] else c('FAIL')
                print(f"{icon} {judge_verdict['explanation'][:80]}")
        elif not agent_response:
            judge_verdict = {'completed': False, 'explanation': 'Respuesta vacía del agente'}
        else:
            judge_verdict = {'completed': False, 'explanation': 'Juez LLM no disponible (sin API key)'}

        # ── 7. Veredicto final ──────────────────────────────
        final_status, final_detail = self._decide_verdict(judge_verdict, side_result)

        # ── 8. Reintento si falló (LLM no determinista) ────
        if final_status in ('FAIL', 'WARN'):
            if not self.quiet:
                print(f"  ↻ Falló en 1er intento. Reintentando... ", end='')
            
            # Tomar nuevo snapshot si hay side effects
            if side_effects_config:
                side_checker.snapshot()
            
            # Re-ejecutar prompt
            try:
                proc = subprocess.run(
                    [hermes_path, '-z', prompt, '--yolo'],
                    capture_output=True, text=True, timeout=120,
                    env=self._get_hermes_env()
                )
                agent_response_retry = proc.stdout.strip()
            except subprocess.TimeoutExpired:
                agent_response_retry = ''
            
            # Re-evaluar
            side_result_retry = None
            if side_effects_config:
                side_result_retry = side_checker.check(side_effects_config)
            
            judge_verdict_retry = None
            if self.judge and agent_response_retry:
                judge_verdict_retry = self.judge.judge(prompt, agent_response_retry)
            elif not agent_response_retry:
                judge_verdict_retry = {'completed': False, 'explanation': 'Respuesta vacía (reintento)'}
            else:
                judge_verdict_retry = {'completed': False, 'explanation': 'Juez no disponible (reintento)'}
            
            # Decidir veredicto final (el mejor de los dos intentos)
            retry_status, retry_detail = self._decide_verdict(judge_verdict_retry, side_result_retry)
            
            if retry_status == 'PASS':
                final_status = 'PASS'
                final_detail = f"✅ al reintentar: {retry_detail}"
                judge_verdict = judge_verdict_retry
                side_result = side_result_retry
                if agent_response_retry:
                    agent_response = agent_response_retry
                if not self.quiet:
                    print(f"{c('PASS')}")
            else:
                if not self.quiet:
                    print(f"{c('FAIL')} (también falló en reintento)")
        
        # ── 9. Registrar resultado ─────────────────────────
        result = {
            'id': sid, 'name': name, 'prompt': prompt,
            'status': final_status, 'severity': severity,
            'detail': final_detail,
            'judge_verdict': judge_verdict,
            'side_effect': side_result,
            'agent_response': agent_response[:2000],  # truncado para reporte
            'agent_stderr': agent_stderr[:500],
            'log_file': '',
        }

        # Escribir log detallado
        log_lines = [
            f"[{sid}] {name}",
            f"Prompt: {prompt}",
            f"Status: {final_status}",
            f"Detail: {final_detail}",
            f"Judge: {json.dumps(judge_verdict)}",
            f"Side effect: {json.dumps(side_result)}",
            f"--- Agent Response ---",
            agent_response,
            f"--- Agent Stderr ---",
            agent_stderr,
        ]
        result['log_file'] = self.log(sid, '\n'.join(log_lines))

        self.results.append(result)

        if not self.quiet:
            print(f"  {Colors.BOLD}→ Resultado: {c(final_status)} {final_detail}{Colors.NC}")

        return result

    def _decide_verdict(self, judge_verdict, side_result):
        """Decidir veredicto final combinando judge + side effects"""
        if side_result and side_result['status'] == 'present':
            # Side effect positivo: el archivo se creó
            # Incluso si el judge duda, el side effect lo confirma
            return 'PASS', f"✅ Archivo creado: {', '.join(side_result.get('files', []))}"

        if side_result and side_result['status'] == 'absent':
            # No se creó archivo esperado
            if judge_verdict and judge_verdict.get('completed'):
                return 'FAIL', f"El agente dijo haberlo hecho pero no hay archivo: {side_result['detail']}"
            return 'FAIL', f"No se creó archivo. Judge: {judge_verdict.get('explanation', '')}"

        if judge_verdict is None:
            return 'WARN', 'No se pudo evaluar la respuesta (juez no disponible)'

        if judge_verdict.get('completed'):
            return 'PASS', judge_verdict.get('explanation', 'Tarea completada')
        else:
            return 'FAIL', judge_verdict.get('explanation', 'Tarea no completada')

    def summary(self):
        """Generar resumen completo"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r['status'] == 'PASS')
        failed = sum(1 for r in self.results if r['status'] == 'FAIL')
        skipped = sum(1 for r in self.results if r['status'] == 'SKIP')
        warned = sum(1 for r in self.results if r['status'] == 'WARN')

        return {
            'timestamp': self.start_time.isoformat(),
            'template_dir': TEMPLATE_DIR,
            'version': VERSION,
            'hermes_available': find_hermes() is not None,
            'judge_available': self.judge is not None,
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
                'warned': warned,
            },
            'tests': self.results,
        }

    def print_summary(self, report):
        """Imprimir resumen formateado"""
        if self.quiet:
            return

        s = report['summary']

        if self.ci:
            # GitHub Actions compatible output
            print(f"::group::🧪 VCOO Behavioral Tests ({s['passed']}/{s['total']} PASS)")
            for r in self.results:
                icon = '✅' if r['status'] == 'PASS' else '❌' if r['status'] == 'FAIL' else '⏭️'
                print(f"  {icon} {r['id']}: {r['status']} — {r['detail'][:80]}")
                if r['status'] == 'FAIL':
                    print(f"  ::error file=behavioral-tests.yaml,title={r['id']}::{r['name']}: {r['detail'][:200]}")
            print(f"::endgroup::")
            print(f"Resultado: {s['passed']} PASS · {s['failed']} FAIL · {s['skipped']} SKIP · {s['warned']} WARN")
            if s['failed'] > 0:
                print(f"::warning::Behavioral tests: {s['failed']} escenarios fallaron")
            return

        print(f"\n{Colors.BOLD}{Colors.CYAN}══════════════════════════════════════════════════{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}  VCOO Behavioral Test Report{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}  {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}══════════════════════════════════════════════════{Colors.NC}")

        print(f"\n{Colors.BOLD}Escenarios ejecutados:{Colors.NC}")
        for r in self.results:
            icon = c(r['status'])
            # Truncar detail
            detail = r['detail'][:80] + '...' if len(r.get('detail', '')) > 80 else r.get('detail', '')
            print(f"  {icon} {r['id']:25s} {r['name'][:40]:40s}  {detail}")

        print(f"\n{Colors.BOLD}Resumen:{Colors.NC}")
        color = Colors.GREEN if s['failed'] == 0 else Colors.RED
        print(f"  {color}{s['passed']} PASS · {s['failed']} FAIL · {s['skipped']} SKIP · {s['warned']} WARN{Colors.NC}")

        if s['failed'] > 0:
            print(f"\n{Colors.BOLD}{Colors.RED}❌ Fallos:{Colors.NC}")
            for r in self.results:
                if r['status'] == 'FAIL':
                    print(f"  {Colors.RED}• {r['id']}: {r['name']}{Colors.NC}")
                    print(f"    {r['detail'][:150]}")

        print(f"\nLogs: {LOGS_DIR}/")
        print(f"{Colors.CYAN}{'─' * 55}{Colors.NC}")


# ─── Cargar escenarios ─────────────────────────────────────

def load_scenarios(config_path):
    """Cargar escenarios desde behavioral-tests.yaml (o .json como fallback)"""
    # Intentar YAML primero
    yaml_available = False
    try:
        import yaml as _yaml_mod
        yaml_available = True
    except ImportError:
        pass

    if yaml_available and os.path.exists(config_path):
        with open(config_path) as f:
            data = _yaml_mod.safe_load(f)
        if data and 'scenarios' in data:
            return data

    # Fallback: JSON
    json_path = config_path.replace('.yaml', '.json')
    if os.path.exists(json_path):
        with open(json_path) as f:
            data = json.load(f)
        if data and 'scenarios' in data:
            return data

    # Si no hay ninguno, error
    print(f"{Colors.RED}✗ No se pudo cargar config: busca {config_path} o {json_path}{Colors.NC}", file=sys.stderr)
    return None


# ─── Main ──────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='VCOO Behavioral Test Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    parser.add_argument('--json', action='store_true', help='Solo salida JSON')
    parser.add_argument('--quiet', action='store_true', help='Sin output por terminal')
    parser.add_argument('--id', type=str, default=None, help='Ejecutar solo un escenario')
    parser.add_argument('--judge-model', type=str, default=None, help='Modelo para LLM judge (default: openai/gpt-4o-mini)')
    parser.add_argument('--smoke', action='store_true', help='Solo escenarios critical/high (rápido)')
    parser.add_argument('--ci', action='store_true', help='Salida compatible GitHub Actions (::group::, ::error::)')
    args = parser.parse_args()

    quiet = args.quiet or args.json

    # Cargar escenarios
    scenarios_data = load_scenarios(CONFIG_FILE)
    if scenarios_data is None:
        sys.exit(1)

    scenarios_list = scenarios_data['scenarios']
    skip_conditions = scenarios_data.get('skip_conditions', {})

    # Filtrar por ID si se especifica
    if args.id:
        scenarios_list = [s for s in scenarios_list if s['id'] == args.id]
        if not scenarios_list:
            print(f"No se encontró escenario con id '{args.id}'")
            sys.exit(1)

    # Filtrar por smoke (solo critical/high)
    if args.smoke:
        smoke_list = [s for s in scenarios_list if s.get('severity', 'low') in ('critical', 'high')]
        if not smoke_list:
            print("No hay escenarios critical/high. Usando todos.")
        else:
            scenarios_list = smoke_list
            if not quiet:
                print(f"Modo smoke: {len(scenarios_list)} escenarios (critical/high)")

    # Inyectar skip_conditions en el primer elemento para que run_scenario acceda
    scenarios_data_flat = dict(scenarios_data)
    scenarios_list_meta = scenarios_data_flat.copy()
    scenarios_list_meta['skip_conditions'] = skip_conditions

    if not quiet:
        print(f"\n{Colors.BOLD}{Colors.CYAN}VCOO Behavioral Test Suite v{VERSION}{Colors.NC}")
        print(f"Template: {TEMPLATE_DIR}")
        print(f"Escenarios: {len(scenarios_list)}")
        print(f"Config: {CONFIG_FILE}")
        print(f"Logs: {LOGS_DIR}/")
        if args.id:
            print(f"Modo: solo escenario '{args.id}'")

        herm = find_hermes()
        print(f"Hermes CLI: {'✅ ' + herm if herm else '❌ no disponible'}")
        print(f"Juez LLM: {'✅ OpenRouter' if detect_secrets().get('OPENROUTER_API_KEY') else '❌ no disponible'}")

    # Detectar secretos
    secrets = detect_secrets()

    # Inicializar runner con los datos completos (incluyendo skip_conditions)
    # Inicializar runner con los datos completos (incluyendo skip_conditions)
    runner = BehaviorTestRunner(
        scenarios_data, secrets, quiet=quiet,
        judge_model=args.judge_model,
        ci=args.ci
    )

    # Ejecutar cada escenario
    for scenario in scenarios_list:
        # Pasar referencia a skip_conditions dentro de scenario para uso interno
        if 'skip_conditions' not in scenario:
            scenario['skip_conditions'] = scenarios_data_flat.get('skip_conditions', {})
        runner.run_scenario(scenario)

    # Generar reporte
    report = runner.summary()

    # Escribir JSON
    os.makedirs(os.path.dirname(TEST_OUTPUT), exist_ok=True)
    timestamp = report['timestamp'].replace(':', '-').split('.')[0]
    report_path = os.path.join(TEST_OUTPUT, f'report-{timestamp}.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Imprimir resumen
    if not quiet:
        runner.print_summary(report)

    # Si --json, dump a stdout
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    # Exit code
    if report['summary']['failed'] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
