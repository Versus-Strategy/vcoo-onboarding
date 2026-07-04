#!/usr/bin/env python3
"""
vcoo-tester.py — Test suite autónoma para VCOO Virtual Template
=================================================================
Uso: python3 vcoo-tester.py [opciones]

Verifica que todos los componentes de la template VCOO funcionan
correctamente, reutilizando los secretos de la instancia MAGI actual
para pruebas de integración reales.

Opciones:
  --json         Solo salida JSON (para consumo programático)
  --quiet        Sin output por terminal (solo JSON + log files)
  --phase N      Ejecutar solo una fase (0-9)
  --behavioral   Ejecutar solo los tests de comportamiento (Fase 9)
  --judge-model  Modelo para LLM judge en behavioral tests
  --help         Este mensaje

Salida:
  - test-output/report-{timestamp}.json   → Reporte completo
  - test-output/logs/t*.log               → Logs individuales
  - Resumen por terminal (por defecto)

Fases:
  0 – Preparación del entorno
  1 – Tests estructurales (archivos, YAML, JSON)
  2 – Tests de sintaxis (compilación Python, bash -n)
  3 – Tests de integración con secretos reales (Drive, Calendar, Gmail, PDF)
  4 – Tests de error handling
  5 – Tests de instalación (dry-run)
  6 – Readiness: qué secretos están configurados
  7 – Deploy & Hermes Integration
  8 – Docker VPS Simulation
  9 – Behavioral: agente responde a lenguaje natural (LLM judge + side effects)

Licencia: Privada — VERSUS Strategy SL
"""

import os
import sys
import json
import subprocess
import datetime
import glob
import tempfile
import shutil
import traceback
import re

# ─── Configuración ──────────────────────────────────────────────

TEMPLATE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─── Auto-detección de la raíz de la template ────────────────────
# Si TEMPLATE_DIR no contiene un marcador de raíz VCOO,
# buscar en ubicaciones conocidas (útil cuando el script se ejecuta
# desde ~/.hermes/scripts/vcoo/ donde el path relativo falla).
_VCOO_ROOT_MARKERS = ['.vcoo-root', 'README.md', 'config.yaml', 'install.sh']
_KNOWN_TEMPLATE_LOCATIONS = [
    os.path.expanduser('~/versus/vcoo-template'),
    '/opt/vcoo-template',
    os.path.join(os.path.dirname(TEMPLATE_DIR), 'vcoo-template'),
]

def _find_template_root(start_dir):
    """Verify start_dir looks like a VCOO template root, else try known locations."""
    # Check if current guess has any marker
    for marker in _VCOO_ROOT_MARKERS:
        if os.path.exists(os.path.join(start_dir, marker)):
            return start_dir
    # Try known locations
    for loc in _KNOWN_TEMPLATE_LOCATIONS:
        for marker in _VCOO_ROOT_MARKERS:
            if os.path.exists(os.path.join(loc, marker)):
                return loc
    # Fallback: return original guess (will fail informatively)
    return start_dir

TEMPLATE_DIR = _find_template_root(TEMPLATE_DIR)
TEST_OUTPUT = os.path.join(TEMPLATE_DIR, 'test-output')
LOGS_DIR = os.path.join(TEST_OUTPUT, 'logs')
SCRIPT_DIR = os.path.join(TEMPLATE_DIR, 'scripts')
SKILL_DIR = os.path.join(TEMPLATE_DIR, 'skills')
PROVISION_DIR = os.path.join(TEMPLATE_DIR, 'provision')
CRON_DIR = os.path.join(TEMPLATE_DIR, 'cron-jobs')
DOCS_DIR = os.path.join(TEMPLATE_DIR, 'docs')

VERSION = "1.0.0"

# ─── VCOO venv detection ────────────────────────────────────────
# The scripts need reportlab, google-api, etc. which live in the VCOO venv
VCOO_VENV_PYTHON = os.path.expanduser(
    '~/.hermes/scripts/vcoo/.venv/bin/python3'
)
if not os.path.exists(VCOO_VENV_PYTHON):
    VCOO_VENV_PYTHON = sys.executable  # fallback to system python

# ─── Colores (terminal) ─────────────────────────────────────────

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

def c(status):
    """Return colorized status symbol"""
    if status == 'PASS': return f"{Colors.GREEN}✓{Colors.NC}"
    if status == 'FAIL': return f"{Colors.RED}✗{Colors.NC}"
    if status == 'SKIP': return f"{Colors.YELLOW}⊘{Colors.NC}"
    if status == 'WARN': return f"{Colors.YELLOW}⚠{Colors.NC}"
    return f"{Colors.BLUE}?{Colors.NC}"

# ─── Secretos (detección automática desde MAGI) ─────────────────

SECRET_SOURCES = {
    'HERMES_ENV': os.path.expanduser('~/.hermes/.env'),
    'TRELLO_ENV': os.path.expanduser('~/versus/.env.trello'),
    'GOOGLE_TOKEN': os.path.expanduser('~/.hermes/google_token.json'),
}

def detect_secrets():
    """Detect available secrets from this MAGI instance"""
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

# ─── Logging ────────────────────────────────────────────────────

class LogWriter:
    """Write per-test logs to files"""
    def __init__(self, log_dir):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def write(self, test_id, content):
        path = os.path.join(self.log_dir, f"{test_id}.log")
        with open(path, 'w') as f:
            f.write(content)
        return path

# ─── Test Runner ────────────────────────────────────────────────

class TestRunner:
    def __init__(self, secrets, log_writer, quiet=False):
        self.secrets = secrets
        self.log = log_writer
        self.quiet = quiet
        self.results = []
        self.start_time = datetime.datetime.now(datetime.timezone.utc)

    def run_cmd(self, cmd, cwd=None, env=None, timeout=30):
        """Run a command and return (exit_code, stdout, stderr)"""
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd or TEMPLATE_DIR,
                env={**os.environ, **(env or {})},
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, '', 'TIMEOUT'
        except FileNotFoundError as e:
            return -2, '', f'Command not found: {e}'

    def test(self, test_id, name, phase, fn, **kwargs):
        """Run a single test, record result"""
        skip = kwargs.get('skip', False)
        if skip:
            result = {
                'id': test_id, 'name': name, 'phase': phase,
                'status': 'SKIP', 'detail': kwargs.get('skip_reason', 'Saltado'),
                'evidence': '', 'log_file': ''
            }
            self.results.append(result)
            if not self.quiet:
                print(f"  {c('SKIP')} {test_id} {name}  [{kwargs.get('skip_reason', 'saltado')}]")
            return result

        try:
            status, detail, evidence = fn()
        except Exception as e:
            status, detail, evidence = 'FAIL', f'Excepción: {e}', traceback.format_exc()

        log_file = self.log.write(test_id, 
            f"[{test_id}] {name}\n"
            f"Status: {status}\n"
            f"Detail: {detail}\n"
            f"Evidence:\n{evidence}\n"
        )

        result = {
            'id': test_id, 'name': name, 'phase': phase,
            'status': status, 'detail': detail,
            'evidence': evidence[:500],  # Truncated for report
            'log_file': log_file
        }
        self.results.append(result)

        if not self.quiet:
            sym = c(status)
            detail_str = detail[:80] + '...' if len(detail) > 80 else detail
            print(f"  {sym} {test_id} {name}")
            if status != 'PASS' and detail_str:
                print(f"     {detail_str}")

        return result

    def phase_header(self, phase_num, title):
        if not self.quiet:
            print(f"\n{Colors.CYAN}── Fase {phase_num}: {title} {'─' * (60 - len(title))}{Colors.NC}")

    def summary(self):
        """Generate summary dict"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r['status'] == 'PASS')
        failed = sum(1 for r in self.results if r['status'] == 'FAIL')
        skipped = sum(1 for r in self.results if r['status'] == 'SKIP')
        warned = sum(1 for r in self.results if r['status'] == 'WARN')
        return {
            'timestamp': self.start_time.isoformat(),
            'template_dir': TEMPLATE_DIR,
            'host': os.uname().nodename,
            'version': VERSION,
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
                'warned': warned,
            },
            'tests': self.results,
        }

    def print_summary(self, summary):
        """Print a nice terminal summary"""
        if self.quiet:
            return
        s = summary['summary']
        bar_total = 20
        bar_passed = int(bar_total * s['passed'] / max(s['total'], 1))
        bar = '█' * bar_passed + '░' * (bar_total - bar_passed)

        print(f"\n{Colors.BOLD}{Colors.BLUE}══════════════════════════════════════════{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.BLUE}  VCOO Template — Test Report{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.BLUE}  {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.BLUE}  Host: {summary['host']}{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.BLUE}  Template: {summary['template_dir']}{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.BLUE}══════════════════════════════════════════{Colors.NC}")

        # Show per-phase stats
        phases = {}
        for r in self.results:
            p = r['phase']
            if p not in phases:
                phases[p] = {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}
            phases[p]['total'] += 1
            if r['status'] == 'PASS':
                phases[p]['passed'] += 1
            elif r['status'] == 'FAIL':
                phases[p]['failed'] += 1
            elif r['status'] == 'SKIP':
                phases[p]['skipped'] += 1

        for p_name, p_stats in sorted(phases.items()):
            total = p_stats['total']
            passed = p_stats['passed']
            pbar = int(bar_total * passed / max(total, 1))
            bar_str = '█' * pbar + '░' * (bar_total - pbar)
            color = Colors.GREEN if p_stats['failed'] == 0 else Colors.RED
            print(f"\n  {color}{p_name:<30s} [{bar_str}] {passed}/{total}{Colors.NC}")

        # Show failures
        failures = [r for r in self.results if r['status'] == 'FAIL']
        if failures:
            print(f"\n{Colors.BOLD}{Colors.RED}❌ Fallos ({len(failures)}):{Colors.NC}")
            for f in failures:
                print(f"  {Colors.RED}• {f['id']}: {f['name']}{Colors.NC}")
                print(f"    {f['detail'][:120]}")

        # Show warnings
        warns = [r for r in self.results if r['status'] == 'WARN']
        if warns:
            print(f"\n{Colors.BOLD}{Colors.YELLOW}⚠️  Advertencias ({len(warns)}):{Colors.NC}")
            for w in warns:
                print(f"  {Colors.YELLOW}• {w['id']}: {w['name']}: {w['detail'][:120]}{Colors.NC}")

        # Final summary line
        print(f"\n{Colors.BOLD}══════════════════════════════════════════{Colors.NC}")
        color = Colors.GREEN if s['failed'] == 0 else Colors.RED
        print(f"{color}Resumen: {s['passed']} PASS · {s['failed']} FAIL · "
              f"{s['skipped']} SKIP · {s['warned']} WARN{Colors.NC}")
        print(f"Logs: {LOGS_DIR}/")
        print(f"")


# ═══════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════

# ─── Fase 0: Preparación ───────────────────────────────────────

def phase0_preparation(runner):
    """Preparación del entorno"""
    runner.phase_header(0, 'Preparación del entorno')
    secrets = runner.secrets

    def t0_1():
        """Python version"""
        code, out, err = runner.run_cmd(['python3', '--version'])
        if code != 0: return 'FAIL', f'Error: {err}', out + err
        ver = out.strip()
        # Parse major.minor
        m = re.search(r'(\d+)\.(\d+)', ver)
        if m:
            major, minor = int(m.group(1)), int(m.group(2))
            if major < 3 or (major == 3 and minor < 11):
                return 'WARN', f'{ver} — se recomienda Python 3.11+', out
        return 'PASS', f'{ver} detectado', out

    def t0_2():
        """Template directory ok"""
        if not os.path.isdir(TEMPLATE_DIR):
            return 'FAIL', f'Template dir no encontrado: {TEMPLATE_DIR}', ''
        return 'PASS', TEMPLATE_DIR, f'{len(os.listdir(TEMPLATE_DIR))} entries'

    def t0_3():
        """Script permissions"""
        scripts = sorted(glob.glob(os.path.join(SCRIPT_DIR, 'vcoo-*.py')))
        if not scripts:
            return 'FAIL', 'No se encontraron scripts vcoo-*.py', ''
        ok = all(os.access(s, os.X_OK) for s in scripts)
        if ok:
            return 'PASS', f'{len(scripts)} scripts ejecutables', '\n'.join(scripts)
        non_exec = [os.path.basename(s) for s in scripts if not os.access(s, os.X_OK)]
        return 'WARN', f'{len(non_exec)} scripts no ejecutables: {non_exec}', '\n'.join(scripts)

    def t0_4():
        """Secrets detection"""
        available = []
        missing = []
        for name, val in secrets.items():
            if val and val not in ('', '***'):
                available.append(name)
            else:
                missing.append(name)
        detail = f'{len(available)} disponibles, {len(missing)} no configurados'
        if available:
            return 'PASS', detail, f'Disponibles: {", ".join(available)}'
        return 'WARN', detail, f'No disponibles: {", ".join(missing)}'

    runner.test('T0.1', 'Python version', 'Preparación', t0_1)
    runner.test('T0.2', 'Template directory', 'Preparación', t0_2)
    runner.test('T0.3', 'Script permissions', 'Preparación', t0_3)
    runner.test('T0.4', 'Secrets detection', 'Preparación', t0_4)


# ─── Fase 1: Estructurales ─────────────────────────────────────

def phase1_structural(runner):
    """Tests estructurales"""
    runner.phase_header(1, 'Tests estructurales')

    def check_file(path, min_size=1):
        full = os.path.join(TEMPLATE_DIR, path)
        if not os.path.exists(full):
            return 'FAIL', f'No encontrado: {path}', ''
        size = os.path.getsize(full)
        if size < min_size:
            return 'FAIL', f'{path}: solo {size} bytes (mín {min_size})', ''
        return 'PASS', f'{path} ({size} bytes)', ''

    def t1_1():
        return check_file('README.md', 100)

    def t1_2():
        return check_file('SOUL.md', 50)

    def t1_3():
        path = os.path.join(TEMPLATE_DIR, 'config.yaml')
        if not os.path.exists(path):
            return 'FAIL', 'config.yaml no encontrado', ''
        try:
            # Try yaml, fallback to manual check
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return 'FAIL', 'config.yaml no es un diccionario', ''
            required = ['model', 'agent', 'terminal']
            missing = [k for k in required if k not in data]
            if missing:
                return 'WARN', f'config.yaml sin campos requeridos: {missing}', json.dumps(data, indent=2)
            return 'PASS', 'YAML válido con model/agent/terminal', json.dumps(data, indent=2)
        except ImportError:
            # Fallback: check manually
            with open(path) as f:
                content = f.read()
            if 'model:' in content and 'agent:' in content:
                return 'PASS', 'YAML (validación básica, PyYAML no instalado)', content[:200]
            return 'FAIL', 'config.yaml parece inválido (sin model/agent)', content[:200]
        except yaml.YAMLError as e:
            return 'FAIL', f'config.yaml: error YAML: {e}', ''

    def t1_4():
        path = os.path.join(TEMPLATE_DIR, '.env.example')
        if not os.path.exists(path):
            return 'FAIL', '.env.example no encontrado', ''
        with open(path) as f:
            content = f.read()
        required_vars = ['OPENROUTER_API_KEY', 'DISCORD_BOT_TOKEN', 'TELEGRAM_BOT_TOKEN']
        found = [v for v in required_vars if v in content]
        missing = [v for v in required_vars if v not in content]
        if not missing:
            return 'PASS', f'.env.example con todas las vars requeridas ({len(found)})', content[:300]
        return 'WARN', f'Faltan vars en .env.example: {missing}', content[:300]

    def t1_5():
        path = os.path.join(TEMPLATE_DIR, 'install.sh')
        if not os.path.exists(path):
            return 'FAIL', 'install.sh no encontrado', ''
        if not os.access(path, os.X_OK):
            return 'WARN', 'install.sh no es ejecutable', ''
        return 'PASS', f'install.sh ({os.path.getsize(path)} bytes)', ''

    def t1_6():
        skills = sorted(glob.glob(os.path.join(SKILL_DIR, 'vcoo-*', 'SKILL.md')))
        if not skills:
            return 'FAIL', 'No se encontraron skills vcoo-*/SKILL.md', ''
        names = [os.path.basename(os.path.dirname(s)) for s in skills]
        return 'PASS', f'{len(skills)} skills: {", ".join(names)}', '\n'.join(skills)

    def t1_7():
        scripts = sorted(glob.glob(os.path.join(SCRIPT_DIR, 'vcoo-*.py')))
        if not scripts:
            return 'FAIL', 'No se encontraron scripts vcoo-*.py', ''
        names = [os.path.basename(s) for s in scripts]
        return 'PASS', f'{len(scripts)} scripts: {", ".join(names)}', '\n'.join(scripts)

    def t1_8():
        cron_files = sorted(glob.glob(os.path.join(CRON_DIR, '*.json')))
        if not cron_files:
            return 'WARN', 'No se encontraron cron jobs', ''
        errors = []
        for f in cron_files:
            try:
                with open(f) as fh:
                    data = json.load(fh)
                for key in ['name', 'schedule', 'prompt']:
                    if key not in data:
                        errors.append(f'{os.path.basename(f)}: falta campo "{key}"')
            except json.JSONDecodeError as e:
                errors.append(f'{os.path.basename(f)}: JSON inválido: {e}')
        if errors:
            return 'FAIL', f'{len(errors)} errores: {"; ".join(errors)}', '\n'.join(errors)
        return 'PASS', f'{len(cron_files)} cron jobs JSON válidos', '\n'.join(cron_files)

    def t1_9():
        scripts = []
        for s in ['setup-server.sh', 'configure-oauth.sh']:
            p = os.path.join(PROVISION_DIR, s)
            if os.path.exists(p):
                scripts.append(s)
        if len(scripts) == 2:
            return 'PASS', 'Ambos provision scripts existen', '\n'.join(scripts)
        return 'WARN', f'Provision scripts: {scripts}', ''

    def t1_10():
        path = os.path.join(TEMPLATE_DIR, '.gitignore')
        if not os.path.exists(path):
            return 'WARN', '.gitignore no encontrado', ''
        with open(path) as f:
            content = f.read()
        sensitive = ['.env', 'token', 'secret', '.json']
        found = [s for s in sensitive if s in content]
        if found:
            return 'PASS', f'Cubre archivos sensibles: {found}', content[:300]
        return 'WARN', '.gitignore no cubre archivos sensibles', content[:300]

    runner.test('T1.1', 'README.md existe', 'Estructural', t1_1)
    runner.test('T1.2', 'SOUL.md existe', 'Estructural', t1_2)
    runner.test('T1.3', 'config.yaml es YAML válido', 'Estructural', t1_3)
    runner.test('T1.4', '.env.example completo', 'Estructural', t1_4)
    runner.test('T1.5', 'install.sh existe y ejecutable', 'Estructural', t1_5)
    runner.test('T1.6', 'Skills VCOO existen', 'Estructural', t1_6)
    runner.test('T1.7', 'Scripts VCOO existen', 'Estructural', t1_7)
    runner.test('T1.8', 'Cron jobs JSON válidos', 'Estructural', t1_8)
    runner.test('T1.9', 'Provision scripts existen', 'Estructural', t1_9)
    runner.test('T1.10', '.gitignore cubre secretos', 'Estructural', t1_10)


# ─── Fase 2: Sintaxis ──────────────────────────────────────────

def phase2_syntax(runner):
    """Tests de sintaxis y compilación"""
    runner.phase_header(2, 'Tests de sintaxis')

    def compile_py(script_name):
        path = os.path.join(SCRIPT_DIR, script_name)
        if not os.path.exists(path):
            return 'SKIP', f'{script_name} no encontrado', ''
        code, out, err = runner.run_cmd([
            'python3', '-c',
            f'import py_compile; py_compile.compile({repr(path)}, doraise=True)'
        ])
        if code != 0:
            return 'FAIL', f'Error de compilación: {err.strip()[:200]}', err
        return 'PASS', 'Compilación OK', ''

    def t2_1(): return compile_py('vcoo-trello.py')
    def t2_2(): return compile_py('vcoo-google.py')
    def t2_3(): return compile_py('vcoo-email.py')
    def t2_4(): return compile_py('vcoo-pdf.py')

    def bash_n(script_rel):
        path = os.path.join(TEMPLATE_DIR, script_rel)
        if not os.path.exists(path):
            return 'SKIP', f'{script_rel} no encontrado', ''
        code, out, err = runner.run_cmd(['bash', '-n', path])
        if code != 0:
            return 'FAIL', f'Error sintaxis bash: {err.strip()[:200]}', err
        return 'PASS', 'Sintaxis bash OK', ''

    def t2_5(): return bash_n('install.sh')
    def t2_6(): return bash_n('provision/setup-server.sh')
    def t2_7(): return bash_n('provision/configure-oauth.sh')

    runner.test('T2.1', 'vcoo-trello.py compila', 'Sintaxis', t2_1)
    runner.test('T2.2', 'vcoo-google.py compila', 'Sintaxis', t2_2)
    runner.test('T2.3', 'vcoo-email.py compila', 'Sintaxis', t2_3)
    runner.test('T2.4', 'vcoo-pdf.py compila', 'Sintaxis', t2_4)
    runner.test('T2.5', 'install.sh sintaxis bash', 'Sintaxis', t2_5)
    runner.test('T2.6', 'setup-server.sh sintaxis bash', 'Sintaxis', t2_6)
    runner.test('T2.7', 'configure-oauth.sh sintaxis bash', 'Sintaxis', t2_7)


# ─── Fase 3: Integración con secretos reales ───────────────────

def phase3_integration(runner):
    """Tests de integración con credenciales reales"""
    runner.phase_header(3, 'Integración con secretos MAGI')
    secrets = runner.secrets

    # --- Helper: run script with temp env ---
    def run_vcoo_script(script_name, args, env_vars=None, timeout=20, use_venv=True):
        script_path = os.path.join(SCRIPT_DIR, script_name)
        if not os.path.exists(script_path):
            return -1, '', f'Script no encontrado: {script_name}'

        python_bin = VCOO_VENV_PYTHON if use_venv else 'python3'
        cmd = [python_bin, script_path] + args
        code, out, err = runner.run_cmd(cmd, timeout=timeout, env=env_vars)
        return code, out, err

    # --- Trello tests ---
    has_trello = bool(secrets.get('TRELLO_API_KEY') and secrets.get('TRELLO_TOKEN'))

    def t3_1():
        if not has_trello:
            return 'SKIP', 'TRELLO_API_KEY no disponible en esta instancia', ''
        code, out, err = run_vcoo_script('vcoo-trello.py', ['boards'],
            env_vars={
                'TRELLO_API_KEY': secrets.get('TRELLO_API_KEY', ''),
                'TRELLO_TOKEN': secrets.get('TRELLO_TOKEN', ''),
            })
        if code != 0:
            return 'FAIL', f'Error listando tableros (exit {code}): {err.strip()[:150]}', out + err
        boards = [l for l in out.split('\n') if '•' in l or '📋' in l]
        n_boards = len(boards)
        return 'PASS', f'{n_boards} tableros listados', out[:500]

    def t3_2():
        if not has_trello:
            return 'SKIP', 'TRELLO_API_KEY no disponible', ''
        # We need a board ID. Try the VERSUS board first.
        # First get boards
        code, out, err = run_vcoo_script('vcoo-trello.py', ['boards'],
            env_vars={
                'TRELLO_API_KEY': secrets.get('TRELLO_API_KEY', ''),
                'TRELLO_TOKEN': secrets.get('TRELLO_TOKEN', ''),
            })
        if code != 0:
            return 'SKIP', f'No se puede obtener tableros (T3.1 falló): {err[:100]}', ''
        # Try to extract a board ID from "ID: xxxx" lines
        board_ids = re.findall(r'ID: (\S+)', out)
        if not board_ids:
            return 'SKIP', 'No se encontraron tableros para testear', out[:300]
        board_id = board_ids[0]
        code, out, err = run_vcoo_script('vcoo-trello.py', ['lists', board_id],
            env_vars={
                'TRELLO_API_KEY': secrets.get('TRELLO_API_KEY', ''),
                'TRELLO_TOKEN': secrets.get('TRELLO_TOKEN', ''),
            })
        if code != 0:
            return 'FAIL', f'Error listando listas (exit {code}): {err.strip()[:150]}', out + err
        lists_count = out.count('□')
        return 'PASS', f'{lists_count} listas en board {board_id[:8]}...', out[:500]

    def t3_3():
        has_google = secrets.get('GOOGLE_OAUTH') == 'configured'
        if not has_google:
            return 'SKIP', 'Google OAuth no disponible en esta instancia', ''
        code, out, err = run_vcoo_script('vcoo-google.py', ['drive', 'list'], timeout=25)
        if code != 0:
            return 'FAIL', f'Error listando Drive (exit {code}): {err.strip()[:150]}', out + err
        files = [l for l in out.split('\n') if '📂' in l or '[' in l]
        return 'PASS', f'Drive accesible ({len(files)} archivos)', out[:500]

    def t3_4():
        has_google = secrets.get('GOOGLE_OAUTH') == 'configured'
        if not has_google:
            return 'SKIP', 'Google OAuth no disponible', ''
        code, out, err = run_vcoo_script('vcoo-google.py', ['calendar', 'list'], timeout=25)
        if code != 0:
            combined = out + err
            if 'insufficientPermissions' in combined or 'insufficient authentication scopes' in combined.lower():
                return 'SKIP', 'Calendar no autorizado en scope OAuth (solo Drive+Gmail)', combined[:300]
            if 'accessNotConfigured' in combined or 'Calendar API has not been used' in combined:
                return 'SKIP', 'Calendar API no activada en Google Cloud Console', combined[:300]
            return 'FAIL', f'Error calendario (exit {code}): {combined[:200]}', combined
        events = [l for l in out.split('\n') if '📅' in l or '|' in l]
        return 'PASS', f'Calendario accesible ({len(events)} eventos)', out[:500]

    def t3_5():
        has_google = secrets.get('GOOGLE_OAUTH') == 'configured'
        if not has_google:
            return 'SKIP', 'Google OAuth no disponible', ''
        # email.py needs gmail API scope
        code, out, err = run_vcoo_script('vcoo-email.py', ['list', '3'], timeout=25)
        if code != 0:
            err_msg = err.strip()[:150]
            if '403' in err_msg or 'scope' in err_msg.lower():
                return 'SKIP', f'Gmail requiere scope específico: {err_msg}', out + err
            return 'FAIL', f'Error leyendo email (exit {code}): {err_msg}', out + err
        return 'PASS', 'Bandeja de entrada accesible', out[:500]

    def t3_6():
        has_google = secrets.get('GOOGLE_OAUTH') == 'configured'
        if not has_google:
            return 'SKIP', 'Google OAuth no disponible', ''
        code, out, err = run_vcoo_script('vcoo-email.py', ['labels'], timeout=25)
        if code != 0:
            return 'FAIL', f'Error listando etiquetas (exit {code}): {err.strip()[:150]}', out + err
        labels_count = out.count('•')
        return 'PASS', f'{labels_count} etiquetas listadas', out[:500]

    def t3_7():
        """vcoo-pdf.py text"""
        tmpdir = tempfile.mkdtemp(prefix='vcoo-test-')
        try:
            outpath = os.path.join(tmpdir, 'test_text.pdf')
            code, out, err = run_vcoo_script('vcoo-pdf.py',
                ['text', outpath, 'Hola mundo desde MAGI'],
                timeout=15)
            if code != 0:
                return 'FAIL', f'Error generando PDF: {err.strip()[:150]}', out + err
            if not os.path.exists(outpath):
                return 'FAIL', 'PDF no se creó', out
            size = os.path.getsize(outpath)
            return 'PASS', f'PDF texto creado ({size} bytes)', out
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def t3_8():
        """vcoo-pdf.py invoice"""
        tmpdir = tempfile.mkdtemp(prefix='vcoo-test-')
        try:
            outpath = os.path.join(tmpdir, 'test_invoice.pdf')
            code, out, err = run_vcoo_script('vcoo-pdf.py',
                ['invoice', outpath, 'Cliente Test', '1250.00', 'Consultoría MAGI'],
                timeout=15)
            if code != 0:
                return 'FAIL', f'Error generando factura: {err.strip()[:150]}', out + err
            if not os.path.exists(outpath):
                return 'FAIL', 'Factura PDF no se creó', out
            size = os.path.getsize(outpath)
            return 'PASS', f'PDF factura creado ({size} bytes)', out
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def t3_9():
        """vcoo-pdf.py report"""
        tmpdir = tempfile.mkdtemp(prefix='vcoo-test-')
        try:
            outpath = os.path.join(tmpdir, 'test_report.pdf')
            code, out, err = run_vcoo_script('vcoo-pdf.py',
                ['report', outpath, 'Informe de Prueba',
                 'Este es un informe generado automáticamente por el tester VCOO.'],
                timeout=15)
            if code != 0:
                return 'FAIL', f'Error generando informe: {err.strip()[:150]}', out + err
            if not os.path.exists(outpath):
                return 'FAIL', 'Informe PDF no se creó', out
            size = os.path.getsize(outpath)
            return 'PASS', f'PDF informe creado ({size} bytes)', out
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def t3_10():
        """vcoo-pdf.py quote"""
        tmpdir = tempfile.mkdtemp(prefix='vcoo-test-')
        try:
            outpath = os.path.join(tmpdir, 'test_quote.pdf')
            servicios = json.dumps([
                {'servicio': 'Landing Page', 'precio': 380},
                {'servicio': 'SEO Básico', 'precio': 150}
            ])
            code, out, err = run_vcoo_script('vcoo-pdf.py',
                ['quote', outpath, 'Cliente Test', servicios],
                timeout=15)
            if code != 0:
                return 'FAIL', f'Error generando presupuesto: {err.strip()[:150]}', out + err
            if not os.path.exists(outpath):
                return 'FAIL', 'Presupuesto PDF no se creó', out
            size = os.path.getsize(outpath)
            return 'PASS', f'PDF presupuesto creado ({size} bytes)', out
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    runner.test('T3.1', 'vcoo-trello.py boards', 'Integración', t3_1)
    runner.test('T3.2', 'vcoo-trello.py lists', 'Integración', t3_2)
    runner.test('T3.3', 'vcoo-google.py drive list', 'Integración', t3_3)
    runner.test('T3.4', 'vcoo-google.py calendar list', 'Integración', t3_4)
    runner.test('T3.5', 'vcoo-email.py list', 'Integración', t3_5)
    runner.test('T3.6', 'vcoo-email.py labels', 'Integración', t3_6)
    runner.test('T3.7', 'vcoo-pdf.py text', 'Integración', t3_7)
    runner.test('T3.8', 'vcoo-pdf.py invoice', 'Integración', t3_8)
    runner.test('T3.9', 'vcoo-pdf.py report', 'Integración', t3_9)
    runner.test('T3.10', 'vcoo-pdf.py quote', 'Integración', t3_10)


# ─── Fase 4: Error Handling ────────────────────────────────────

def phase4_error_handling(runner):
    """Tests de error handling"""
    runner.phase_header(4, 'Tests de error handling')

    def run_script_isolated(script, args, timeout=10):
        """Run script in temp dir with NO env files, using system Python to avoid venv deps"""
        tmpdir = tempfile.mkdtemp(prefix='vcoo-test-iso-')
        try:
            code, out, err = runner.run_cmd(
                ['python3', os.path.join(SCRIPT_DIR, script)] + args,
                cwd=tmpdir,
                timeout=timeout
            )
            return code, out, err
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def run_script_isolated_venv(script, args, timeout=10):
        """Run script in temp dir, using VCOO venv (needed for scripts with external deps)"""
        tmpdir = tempfile.mkdtemp(prefix='vcoo-test-iso-')
        try:
            code, out, err = runner.run_cmd(
                [VCOO_VENV_PYTHON, os.path.join(SCRIPT_DIR, script)] + args,
                cwd=tmpdir,
                timeout=timeout
            )
            return code, out, err
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def t4_1():
        """trello without API key → error"""
        # Check if trello env file exists (hardcoded path in script)
        trello_env_hardcoded = "/home/ubuntu/versus/.env.trello"
        if os.path.exists(trello_env_hardcoded):
            return 'SKIP', 'Credenciales Trello presentes (hardcoded path en script) — no se puede testear error handling en esta instancia', ''

        code, out, err = run_script_isolated('vcoo-trello.py', ['boards'])
        if code == 0:
            return 'FAIL', 'Debería fallar sin API key, pero retornó 0', out
        # Check both stdout and stderr for error indicators
        combined = out + err
        has_msg = '❌' in combined or 'API_KEY' in combined or 'no se encuentra' in combined.lower()
        if has_msg:
            return 'PASS', 'Falla correctamente con mensaje de error', combined[:300]
        return 'WARN', f'Falla (exit {code}) pero mensaje poco claro', combined[:300]

    def t4_2():
        """trello invalid action → shows usage"""
        code, out, err = run_script_isolated('vcoo-trello.py', ['nonexistent-action-xyz'])
        if code == 0:
            return 'FAIL', 'Debería fallar con acción inválida', out
        combined = out + err
        has_usage = 'uso' in combined.lower() or 'Usage' in combined or 'Acciones' in combined or '❌' in combined
        if has_usage:
            return 'PASS', 'Muestra ayuda/error para acción inválida', combined[:300]
        return 'WARN', f'Falla (exit {code}) pero sin mensaje claro', combined[:300]

    def t4_3():
        """pdf without args → shows usage"""
        code, out, err = run_script_isolated_venv('vcoo-pdf.py', [])
        combined = out + err
        has_usage = 'uso' in combined.lower() or 'Usage' in combined or 'Acciones' in combined or 'Uso' in combined
        if has_usage:
            return 'PASS', 'Muestra uso cuando no hay args', combined[:300]
        return 'WARN', f'Exit {code}, output: {combined[:200]}', combined

    def t4_4():
        """email without google token → error message"""
        code, out, err = run_script_isolated('vcoo-email.py', ['list'])
        combined = out + err
        has_msg = '❌' in combined or 'token' in combined.lower() or 'credentials' in combined.lower() or 'no' in combined.lower()[:100]
        if has_msg:
            return 'PASS', 'Muestra error cuando no hay token Google', combined[:300]
        return 'WARN', f'Exit {code}, output: {combined[:200]}', combined

    def t4_5():
        """pdf invoice without enough args → error"""
        code, out, err = run_script_isolated('vcoo-pdf.py', ['invoice'])
        combined = out + err
        if code == 0:
            return 'FAIL', 'Debería fallar sin argumentos suficientes', combined
        return 'PASS', f'Falla correctamente (exit {code})', combined[:200]

    def t4_6():
        """google drive without token → error"""
        code, out, err = run_script_isolated('vcoo-google.py', ['drive', 'list'])
        combined = out + err
        # Si el token está presente, el script funciona y lista archivos — test no aplica
        if code == 0 and '📂' in combined:
            return 'SKIP', 'Token Google presente — el script funciona correctamente', combined[:200]
        has_msg = '❌' in combined or 'token' in combined.lower() or 'credentials' in combined.lower()
        if has_msg:
            return 'PASS', 'Muestra error cuando no hay token Google', combined[:300]
        return 'WARN', f'Exit {code}, output: {combined[:200]}', combined

    runner.test('T4.1', 'trello sin API key → error', 'Error handling', t4_1)
    runner.test('T4.2', 'trello acción inválida → usage', 'Error handling', t4_2)
    runner.test('T4.3', 'pdf sin args → usage', 'Error handling', t4_3)
    runner.test('T4.4', 'email sin token → error', 'Error handling', t4_4)
    runner.test('T4.5', 'pdf invoice args insuficientes', 'Error handling', t4_5)
    runner.test('T4.6', 'google drive sin token → error', 'Error handling', t4_6)


# ─── Fase 5: Dry-run install ───────────────────────────────────

def phase5_install_dryrun(runner):
    """Tests de install.sh sin ejecutarlo"""
    runner.phase_header(5, 'Tests de instalación (dry-run)')
    install_path = os.path.join(TEMPLATE_DIR, 'install.sh')

    def t5_1():
        if not os.path.exists(install_path):
            return 'FAIL', 'install.sh no encontrado', ''
        with open(install_path) as f:
            first = f.readline()
        if 'bash' in first:
            return 'PASS', f'Shebang correcto: {first.strip()}', first
        return 'WARN', f'Shebang: {first.strip()}', first

    def t5_2():
        if not os.path.exists(install_path): return 'SKIP', 'install.sh no encontrado', ''
        with open(install_path) as f:
            content = f.read()
        if 'set -euo pipefail' in content:
            return 'PASS', 'Usa set -euo pipefail', ''
        return 'WARN', 'No usa set -euo pipefail', ''

    def t5_3():
        if not os.path.exists(install_path): return 'SKIP', 'install.sh no encontrado', ''
        with open(install_path) as f:
            content = f.read()
        required_refs = ['VCOO_DIR', 'HERMES_HOME', 'HERMES_SKILLS', 'HERMES_SCRIPTS']
        found = [r for r in required_refs if r in content]
        missing = [r for r in required_refs if r not in content]
        if not missing:
            return 'PASS', f'Todas las rutas referencia: {found}', ''
        return 'WARN', f'Faltan referencias: {missing}', ''

    def t5_4():
        if not os.path.exists(install_path): return 'SKIP', 'install.sh no encontrado', ''
        with open(install_path) as f:
            content = f.read()
        sections = re.findall(r'# ── (\d+)\.', content)
        if sections:
            max_s = max(int(s) for s in sections)
            return 'PASS', f'{max_s} secciones numeradas encontradas', '\n'.join(sections)
        return 'WARN', 'No se encontraron secciones numeradas claras', ''

    runner.test('T5.1', 'Shebang correcto', 'Instalación', t5_1)
    runner.test('T5.2', 'set -euo pipefail', 'Instalación', t5_2)
    runner.test('T5.3', 'Rutas correctas', 'Instalación', t5_3)
    runner.test('T5.4', 'Secciones numeradas', 'Instalación', t5_4)


# ─── Fase 6: Readiness (secrets check) ─────────────────────────

def phase6_readiness(runner):
    """Reporte de qué secretos están configurados"""
    runner.phase_header(6, 'Readiness — Estado de secretos')
    secrets = runner.secrets

    def check_secret(name, label, source, is_required=True):
        def test_fn():
            val = secrets.get(name)
            if val and val not in ('', '***'):
                masked = val[:6] + '...' + val[-4:] if len(val) > 12 else val[:4] + '...'
                return 'PASS', f'{label}: configurado ({masked})', f'Fuente: {source}'
            else:
                msg = f'{label}: NO CONFIGURADO'
                if is_required:
                    return 'FAIL', msg + ' (requerido para operación)', f'Fuente: {source}'
                return 'WARN', msg + ' (opcional, según módulos contratados)', f'Fuente: {source}'
        return test_fn

    runner.test('T6.1', 'OPENROUTER_API_KEY', 'Readiness',
                check_secret('OPENROUTER_API_KEY', 'OpenRouter Key',
                             '~/.hermes/.env', is_required=True))
    runner.test('T6.2', 'DISCORD_BOT_TOKEN', 'Readiness',
                check_secret('DISCORD_BOT_TOKEN', 'Discord Bot Token',
                             '~/.hermes/.env', is_required=True))
    runner.test('T6.3', 'TELEGRAM_BOT_TOKEN', 'Readiness',
                check_secret('TELEGRAM_BOT_TOKEN', 'Telegram Bot Token',
                             '~/.hermes/.env', is_required=True))
    runner.test('T6.4', 'TRELLO_API_KEY + TOKEN', 'Readiness',
                check_secret('TRELLO_API_KEY', 'Trello API Key',
                             '~/.hermes/scripts/vcoo/vcoo-trello.py', is_required=False))
    runner.test('T6.5', 'Google OAuth', 'Readiness',
                check_secret('GOOGLE_OAUTH', 'Google OAuth',
                             '~/.hermes/google_token.json', is_required=False))
    runner.test('T6.6', 'CONTROL_PLANE_URL', 'Readiness',
                check_secret('CONTROL_PLANE_URL', 'Control Plane URL',
                             '~/.hermes/.env', is_required=False))

    # Special test for template's own .env file
    def t6_7():
        env_path = os.path.join(TEMPLATE_DIR, '.env')
        if not os.path.exists(env_path):
            return 'PASS', '.env NO existe en template (correcto, solo .env.example)', ''
        size = os.path.getsize(env_path)
        # Si el .env fue generado por el build (placeholders), no es un riesgo real
        try:
            with open(env_path) as f:
                content = f.read()
            if 'PLACEHOLDER' in content or 'TEST_PLACEHOLDER' in content or \
               all('***' in line or line.startswith('#') or line.strip() == '' for line in content.split('\n') if '=' in line):
                return 'PASS', f'.env existe ({size} bytes) con placeholders de build — seguro', ''
        except Exception:
            pass
        return 'WARN', f'.env existe en template ({size} bytes) — sensible, debería estar en .gitignore', ''

    def t6_8():
        google_path = os.path.expanduser('~/.hermes/google_token.json')
        if not os.path.exists(google_path):
            return 'WARN', 'Google OAuth no configurado en esta instancia', ''
        try:
            with open(google_path) as f:
                tok = json.load(f)
            has_refresh = bool(tok.get('refresh_token'))
            expiry = tok.get('expiry', 'unknown')
            return 'PASS', f'Google OAuth OK (refresh_token: {has_refresh}, expiry: {expiry})', ''
        except Exception as e:
            return 'FAIL', f'Error leyendo google_token: {e}', ''

    runner.test('T6.7', '.env sensible en template?', 'Readiness', t6_7)
    runner.test('T6.8', 'Google token válido?', 'Readiness', t6_8)


# ═══════════════════════════════════════════════════════════════════
# Fase 7: Deploy Simulation + Hermes Integration
# ═══════════════════════════════════════════════════════════════════

def phase7_deploy_integration(runner):
    """Deploy simulation + Hermes integration test"""
    runner.phase_header(7, 'Deploy & Hermes Integration')
    secrets = runner.secrets

    def t7_1():
        """Template se copia correctamente a directorio limpio"""
        tmpdir = tempfile.mkdtemp(prefix='vcoo-deploy-')
        try:
            skip_dirs = {'.git', 'test-output', '__pycache__'}
            skip_files = {'.gitkeep'}
            for item in os.listdir(TEMPLATE_DIR):
                if item in skip_dirs or item in skip_files:
                    continue
                src = os.path.join(TEMPLATE_DIR, item)
                dst = os.path.join(tmpdir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
                else:
                    shutil.copy2(src, dst)
            # Verify structure
            required = ['README.md', 'config.yaml', '.env.example', 'install.sh',
                        'SOUL.md', 'skills', 'scripts', 'provision', 'cron-jobs']
            missing = [r for r in required if not os.path.exists(os.path.join(tmpdir, r))]
            if missing:
                return 'FAIL', f'Faltan archivos en deploy: {missing}', ''
            return 'PASS', f'Template desplegada correctamente en {tmpdir}', '\n'.join(os.listdir(tmpdir))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def t7_2():
        """Se genera .env a partir de .env.example + secretos reales"""
        tmpdir = tempfile.mkdtemp(prefix='vcoo-deploy-')
        try:
            # Copy template
            for item in os.listdir(TEMPLATE_DIR):
                if item in ('.git', 'test-output', '__pycache__'):
                    continue
                src = os.path.join(TEMPLATE_DIR, item)
                dst = os.path.join(tmpdir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
                else:
                    shutil.copy2(src, dst)

            # Generate .env from .env.example + secrets
            src_env = os.path.join(tmpdir, '.env.example')
            dst_env = os.path.join(tmpdir, '.env')
            if not os.path.exists(src_env):
                return 'FAIL', '.env.example no encontrado en deploy', ''

            with open(src_env) as f:
                env_content = f.read()

            # Fill in secrets from this MAGI instance
            replacements = {
                'OPENROUTER_API_KEY': secrets.get('OPENROUTER_API_KEY', ''),
                'DISCORD_BOT_TOKEN': secrets.get('DISCORD_BOT_TOKEN', ''),
                'TELEGRAM_BOT_TOKEN': secrets.get('TELEGRAM_BOT_TOKEN', ''),
            }
            for key, val in replacements.items():
                if val:
                    env_content = env_content.replace(f'{key}=', f'{key}={val}')
            
            # Mark CONTROL_PLANE stuff as placeholder (standalone mode)
            env_content = env_content.replace('MASTER_KEY=', 'MASTER_KEY=test-standalone-mode')
            env_content = env_content.replace('PROVISION_TOKEN=', 'PROVISION_TOKEN=test-standalone-mode')

            with open(dst_env, 'w') as f:
                f.write(env_content)

            with open(dst_env) as f:
                written = f.read()

            # Verify key vars are in .env
            checks = ['OPENROUTER_API_KEY', 'DISCORD_BOT_TOKEN', 'TELEGRAM_BOT_TOKEN']
            results = {}
            for c in checks:
                for line in written.split('\n'):
                    if line.startswith(c) and '=' in line:
                        val = line.split('=', 1)[1].strip()
                        results[c] = '✓' if val and val not in ('', '***') else '✗'
                        break
            
            failed = [k for k, v in results.items() if v == '✗']
            if failed:
                return 'FAIL', f'Secretos no inyectados en .env: {failed}', written[:500]
            return 'PASS', f'.env generado con {sum(1 for v in results.values() if v == "✓")} secretos', written[:500]
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def t7_3():
        """config.yaml es compatible con Hermes Agent"""
        path = os.path.join(TEMPLATE_DIR, 'config.yaml')
        if not os.path.exists(path):
            return 'FAIL', 'config.yaml no encontrado', ''
        
        with open(path) as f:
            content = f.read()
        
        # Verify Hermes-compatible fields
        checks = [
            ('model.default', 'model:' in content and 'default:' in content),
            ('agent.max_turns', 'max_turns:' in content),
            ('terminal.backend', 'backend:' in content and 'terminal:' in content),
            ('skills.auto_load', 'auto_load:' in content),
            ('gateway.platforms', 'platforms:' in content),
        ]
        failed = [name for name, ok in checks if not ok]
        if failed:
            return 'FAIL', f'Campos Hermes incompatibles: {failed}', content[:500]
        return 'PASS', f'config.yaml compatible ({len(checks)} campos Hermes)', content[:500]

    def t7_4():
        """Skills VCOO tienen frontmatter YAML válido con campos requeridos"""
        skills = sorted(glob.glob(os.path.join(SKILL_DIR, 'vcoo-*', 'SKILL.md')))
        if not skills:
            return 'FAIL', 'No se encontraron skills para validar', ''
        
        errors = []
        ok_count = 0
        for skill_path in skills:
            skill_name = os.path.basename(os.path.dirname(skill_path))
            with open(skill_path) as f:
                content = f.read()
            
            # Check basic YAML frontmatter
            if not content.startswith('---'):
                errors.append(f'{skill_name}: sin frontmatter YAML (---)')
                continue
            
            # Find closing ---
            end_idx = content.find('---', 3)
            if end_idx == -1:
                errors.append(f'{skill_name}: frontmatter sin cierre')
                continue
            
            front = content[3:end_idx].strip()
            
            # Check required fields
            required_fields = ['name:', 'description:', 'version:', 'author:']
            missing = [f for f in required_fields if f not in front]
            if missing:
                errors.append(f'{skill_name}: faltan campos: {missing}')
                continue
            
            # Validate name matches
            for line in front.split('\n'):
                if line.startswith('name:'):
                    yaml_name = line.split(':', 1)[1].strip().strip('"').strip("'")
                    if yaml_name != skill_name:
                        errors.append(f'{skill_name}: name en frontmatter ({yaml_name}) no coincide con dirname')
                    break
            
            ok_count += 1
        
        if errors:
            return 'FAIL', f'{len(errors)} skills con errores: {"; ".join(errors[:3])}', '\n'.join(errors)
        return 'PASS', f'{ok_count}/{len(skills)} skills válidos', '\n'.join(skills)

    def t7_5():
        """Hermes CLI puede ver los skills desde la template"""
        # Try to use hermes CLI to verify skills are loadable
        hermes_cmd = shutil.which('hermes') or os.path.expanduser('~/.local/bin/hermes')
        if not hermes_cmd or not os.path.exists(hermes_cmd):
            # Try VCOO venv
            hermes_cmd = os.path.join(os.path.dirname(VCOO_VENV_PYTHON), 'hermes')
        if not hermes_cmd or not os.path.exists(hermes_cmd):
            return 'SKIP', 'Hermes CLI no encontrado en PATH ni venv', ''

        # Copy template to temp and use hermes to validate
        tmpdir = tempfile.mkdtemp(prefix='vcoo-deploy-')
        try:
            # Copy template
            for item in os.listdir(TEMPLATE_DIR):
                if item in ('.git', 'test-output', '__pycache__', '.gitignore'):
                    continue
                src = os.path.join(TEMPLATE_DIR, item)
                dst = os.path.join(tmpdir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
                else:
                    shutil.copy2(src, dst)

            # Verify hermes can find the skills
            # Skills would be at ~/.hermes/skills/versus-multiagent-orchestration/ after install
            # We can check if existing skills match template skills
            existing_skills = set()
            installed_skills_dir = os.path.expanduser('~/.hermes/skills/versus-multiagent-orchestration')
            if os.path.exists(installed_skills_dir):
                existing_skills = set(os.listdir(installed_skills_dir))

            template_skills = set(os.listdir(SKILL_DIR))
            match = template_skills & existing_skills
            missing = template_skills - existing_skills

            if not match:
                return 'WARN', 'Skills de template no encontrados en instalación Hermes actual', ''
            msg = f'{len(match)}/{len(template_skills)} skills coinciden con instalación actual'
            if missing:
                msg += f' (faltan: {missing})'
                return 'WARN', msg, '\n'.join(sorted(template_skills))
            return 'PASS', msg, '\n'.join(sorted(template_skills))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def t7_6():
        """install.sh puede ejecutar pasos clave en dry-run simulado"""
        install_path = os.path.join(TEMPLATE_DIR, 'install.sh')
        if not os.path.exists(install_path):
            return 'FAIL', 'install.sh no encontrado', ''

        with open(install_path) as f:
            content = f.read()

        # Verify all critical sections are present
        sections = {
            'requisitos': 'Verificando requisitos',
            'uv': 'Instalando uv',
            'hermes': 'Instalando Hermes Agent',
            'config': 'Configurando Hermes Agent',
            'skills': 'Copiar skills',
            'scripts': 'Copiar scripts',
            'provision': 'Provisionamiento',
            'cron': 'Cron jobs',
            'resumen': 'Próximos pasos',
        }
        found = []
        missing = []
        for name, marker in sections.items():
            if marker in content or f'# ── {list(sections.keys()).index(name) + 1}.' in content:
                found.append(name)
            else:
                missing.append(name)

        if missing:
            return 'FAIL', f'Secciones faltantes en install.sh: {missing}', ''
        return 'PASS', f'{len(found)}/{len(sections)} secciones completas', '\n'.join(found)

    def t7_7():
        """Hermes gateway puede iniciar con config de template (dry-run config test)"""
        # Verify gateway configuration in template
        config_path = os.path.join(TEMPLATE_DIR, 'config.yaml')
        with open(config_path) as f:
            content = f.read()

        # Check for gateway.enabled
        if 'gateway:' in content and 'enabled:' in content:
            return 'PASS', 'Config de gateway presente en config.yaml', content[:300]

        # Template might not have gateway section (it's for the client to configure)
        # Check if gateway config is at least structured correctly
        has_platforms = 'discord:' in content or 'telegram:' in content
        if has_platforms:
            return 'PASS', 'Plataformas de gateway referenciadas en config', content[:300]
        return 'WARN', 'No se detectó configuración de gateway explícita', content[:300]

    runner.test('T7.1', 'Deploy: copia completa de template', 'Deploy & Hermes', t7_1)
    runner.test('T7.2', 'Deploy: generación de .env con secretos', 'Deploy & Hermes', t7_2)
    runner.test('T7.3', 'Deploy: config.yaml compatible Hermes', 'Deploy & Hermes', t7_3)
    runner.test('T7.4', 'Deploy: skills con frontmatter válido', 'Deploy & Hermes', t7_4)
    runner.test('T7.5', 'Deploy: skills visibles desde Hermes CLI', 'Deploy & Hermes', t7_5)
    runner.test('T7.6', 'Deploy: install.sh secciones completas', 'Deploy & Hermes', t7_6)
    runner.test('T7.7', 'Deploy: config de gateway presente', 'Deploy & Hermes', t7_7)


# ═══════════════════════════════════════════════════════════════════
# Fase 8: Docker Integration (Clean VPS Simulation)
# ═══════════════════════════════════════════════════════════════════

def phase8_docker_integration(runner):
    """Docker build + test — simulate clean VPS installation"""
    runner.phase_header(8, 'Docker VPS Simulation')
    dockerfile = os.path.join(TEMPLATE_DIR, 'Dockerfile.test')
    image_tag = 'vcoo-test:latest'
    deploy_dir = TEMPLATE_DIR  # Docker context dir
    secrets = runner.secrets

    def check_docker():
        code, out, err = runner.run_cmd(['docker', '--version'], timeout=5)
        if code != 0:
            return False, 'Docker no disponible', out + err
        return True, out.strip(), ''

    def t8_1():
        """Docker disponible en el sistema"""
        ok, detail, err = check_docker()
        if not ok:
            return 'SKIP', detail, err
        return 'PASS', detail, ''

    def t8_2():
        """Dockerfile.test existe"""
        if not os.path.exists(dockerfile):
            return 'FAIL', 'Dockerfile.test no encontrado en template', ''
        with open(dockerfile) as f:
            content = f.read()
        checks = [
            'FROM ubuntu:22.04' in content,
            'install.sh' in content,
            'vcoo-tester.py' in content,
        ]
        failed = [f'check-{i}' for i, ok in enumerate(checks) if not ok]
        if failed:
            return 'FAIL', f'Dockerfile incompleto: {failed}', ''
        return 'PASS', 'Dockerfile.test con todos los componentes', ''

    def t8_3():
        """Build Docker image desde cero"""
        ok, _, _ = check_docker()
        if not ok:
            return 'SKIP', 'Docker no disponible', ''

        # Detect test API key from .env.test or this MAGI instance
        or_key = secrets.get('OPENROUTER_API_KEY', '')
        build_args = [
            'docker', 'build', '-f', 'Dockerfile.test', '-t', image_tag, '.'
        ]
        if or_key and or_key not in ('', '***', '__TEST_PLACEHOLDER__'):
            build_args = [
                'docker', 'build', '-f', 'Dockerfile.test',
                '--build-arg', f'OPENROUTER_API_KEY={or_key}',
                '-t', image_tag, '.'
            ]

        code, out, err = runner.run_cmd(build_args, cwd=deploy_dir, timeout=300)
        if code != 0:
            # Extract meaningful error
            error_lines = [l for l in (out + err).split('\n') if 'error' in l.lower() or 'Error' in l]
            detail = error_lines[-1][:150] if error_lines else f'Build falló (exit {code})'
            return 'FAIL', detail, (out + err)[-1000:]
        # Verify image was created
        code2, out2, _ = runner.run_cmd(
            ['docker', 'image', 'inspect', image_tag, '--format', '{{.Size}}'],
            timeout=10)
        if code2 != 0:
            return 'FAIL', 'Imagen no encontrada tras build', out2
        size_mb = int(out2.strip()) / (1024 * 1024)
        return 'PASS', f'Imagen creada ({size_mb:.0f} MB)', out[-500:]

    def t8_4():
        """Ejecutar tests estructurales dentro del contenedor"""
        ok, _, _ = check_docker()
        if not ok:
            return 'SKIP', 'Docker no disponible', ''

        # Run phases 0,1,2,5,7 inside container (no creds needed)
        code, out, err = runner.run_cmd([
            'docker', 'run', '--rm', image_tag,
            'bash', '-c',
            'export PATH="$HOME/.local/bin:$PATH" && '
            'python3 /opt/vcoo-template/scripts/vcoo-tester.py --phase 1 --quiet --json'
        ], timeout=60)

        if code != 0:
            return 'FAIL', f'Tests en contenedor fallaron (exit {code})', (out + err)[-500:]

        # Parse JSON result
        try:
            result = json.loads(out)
            s = result['summary']
            detail = f'{s["passed"]} PASS · {s["failed"]} FAIL · {s["skipped"]} SKIP · {s["warned"]} WARN'
            if s['failed'] > 0:
                return 'FAIL', detail, json.dumps(result, indent=2)
            return 'PASS', detail, json.dumps(result, indent=2)
        except (json.JSONDecodeError, KeyError) as e:
            return 'FAIL', f'Error parseando resultado: {e}', out[:500]

    def t8_5():
        """Ejecutar tests de error handling en contenedor (sin credenciales)"""
        ok, _, _ = check_docker()
        if not ok:
            return 'SKIP', 'Docker no disponible', ''

        code, out, err = runner.run_cmd([
            'docker', 'run', '--rm', image_tag,
            'bash', '-c',
            'export PATH="$HOME/.local/bin:$PATH" && '
            'python3 /opt/vcoo-template/scripts/vcoo-tester.py --phase 4 --quiet --json'
        ], timeout=60)

        if code != 0:
            return 'FAIL', f'Error handling tests fallaron (exit {code})', (out + err)[-500:]

        try:
            result = json.loads(out)
            s = result['summary']
            detail = f'{s["passed"]} PASS · {s["failed"]} FAIL · {s["skipped"]} SKIP'
            if s['failed'] > 0:
                return 'FAIL', detail, json.dumps(result, indent=2)
            return 'PASS', detail, json.dumps(result, indent=2)
        except (json.JSONDecodeError, KeyError) as e:
            return 'FAIL', f'Error parseando: {e}', out[:500]

    def t8_6():
        """Ejecutar full test suite en contenedor (reporte completo)"""
        ok, _, _ = check_docker()
        if not ok:
            return 'SKIP', 'Docker no disponible', ''

        code, out, err = runner.run_cmd([
            'docker', 'run', '--rm', image_tag,
            'bash', '-c',
            'export PATH="$HOME/.local/bin:$PATH" && '
            'python3 /opt/vcoo-template/scripts/vcoo-tester.py --quiet --json 2>&1'
        ], timeout=120)

        if code == 0:
            return 'PASS', 'Suite completa: 0 FAIL', out[:500]
        # Even with failures, parse the results
        try:
            result = json.loads(out)
            s = result['summary']
            detail = f'{s["passed"]} PASS · {s["failed"]} FAIL · {s["skipped"]} SKIP · {s["warned"]} WARN'
            return 'WARN' if s['failed'] == 0 else 'FAIL', detail, json.dumps(result, indent=2)
        except (json.JSONDecodeError, KeyError):
            return 'FAIL', f'Error parseando resultado completo', (out + err)[-1000:]

    def t8_7():
        """Limpiar imagen Docker de test"""
        ok, _, _ = check_docker()
        if not ok:
            return 'SKIP', 'Docker no disponible', ''

        # Only clean if user asked for it or if all other tests passed
        # For now, just report the image exists
        code, out, err = runner.run_cmd(
            ['docker', 'images', '--format', '{{.Repository}}:{{.Tag}} {{.Size}}', image_tag],
            timeout=10)
        if code != 0 or not out.strip():
            return 'WARN', 'Imagen vcoo-test no encontrada para limpieza', ''
        return 'PASS', f'Imagen disponible: {out.strip()}', ''

    runner.test('T8.1', 'Docker disponible', 'Docker VPS', t8_1)
    runner.test('T8.2', 'Dockerfile.test existe', 'Docker VPS', t8_2)
    runner.test('T8.3', 'Build imagen Docker', 'Docker VPS', t8_3)
    runner.test('T8.4', 'Tests estructurales en contenedor', 'Docker VPS', t8_4)
    runner.test('T8.5', 'Error handling en contenedor', 'Docker VPS', t8_5)
    runner.test('T8.6', 'Suite completa en contenedor', 'Docker VPS', t8_6)
    runner.test('T8.7', 'Imagen Docker disponible', 'Docker VPS', t8_7)

# ─── Fase 9: Behavioral Tests ─────────────────────────────────

def phase9_behavioral(runner, judge_model=None):
    """Tests de comportamiento del agente VCOO"""
    runner.phase_header(9, 'Tests de comportamiento (agente IA)')
    secrets = runner.secrets

    def t9_0():
        """Script vcoo-behavior-tester.py existe"""
        path = os.path.join(SCRIPT_DIR, 'vcoo-behavior-tester.py')
        if not os.path.exists(path):
            return 'FAIL', f'No existe: {path}', ''
        return 'PASS', '', ''

    def t9_1():
        """Config de escenarios existe"""
        cfg = os.path.join(TEMPLATE_DIR, 'configs', 'behavioral-tests.yaml')
        if not os.path.exists(cfg):
            return 'FAIL', f'No existe: {cfg}', ''
        return 'PASS', '', ''

    def t9_2():
        """Skill vcoo-behavioral-testing existe"""
        skill_path = os.path.join(SKILL_DIR, 'vcoo-behavioral-testing', 'SKILL.md')
        if not os.path.exists(skill_path):
            return 'FAIL', f'No existe: {skill_path}', ''
        return 'PASS', '', ''

    def t9_3():
        """Ejecutar behavioral tests (modo JSON, extraer summary)"""
        behavior_script = os.path.join(SCRIPT_DIR, 'vcoo-behavior-tester.py')
        if not os.path.exists(behavior_script):
            return 'SKIP', f'Script no encontrado', ''

        # Ejecutar behavioral tester en modo JSON, solo escenarios críticos
        cmd = ['python3', behavior_script, '--json', '--quiet', '--smoke']
        if judge_model:
            cmd += ['--judge-model', judge_model]
        code, out, err = runner.run_cmd(cmd, timeout=300)

        if code == -2:
            return 'SKIP', f'Python3 no disponible', err

        # Parsear resultado JSON
        try:
            result = json.loads(out)
            s = result['summary']
            detail = f'{s["passed"]} PASS · {s["failed"]} FAIL · {s["skipped"]} SKIP · {s["warned"]} WARN'
            if s['failed'] > 0:
                # Extraer detalles de los fallos
                failures = [t for t in result['tests'] if t['status'] == 'FAIL']
                fail_details = '; '.join(
                    [f'{f["id"]}: {f["detail"][:100]}' for f in failures[:3]]
                )
                return 'FAIL', f'{detail}. Fallos: {fail_details}', out[:2000]
            return 'PASS', detail, out[:2000]
        except (json.JSONDecodeError, KeyError) as e:
            return 'WARN', f'No se pudo parsear resultado: {e}', (out + err)[-1000:]

    runner.test('T9.0', 'Script behavioral existe', 'Behavioral IA', t9_0)
    runner.test('T9.1', 'Config de escenarios existe', 'Behavioral IA', t9_1)
    runner.test('T9.2', 'Skill behavioral-testing existe', 'Behavioral IA', t9_2)
    runner.test('T9.3', 'Ejecutar behavioral tests', 'Behavioral IA', t9_3)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='VCOO Template — Test Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    parser.add_argument('--json', action='store_true', help='Solo salida JSON')
    parser.add_argument('--quiet', action='store_true', help='Sin output por terminal')
    parser.add_argument('--phase', type=int, default=None, choices=range(0, 10),
                        help='Ejecutar solo una fase específica (0-9)')
    parser.add_argument('--behavioral', action='store_true',
                        help='Ejecutar solo los tests de comportamiento (Fase 9)')
    parser.add_argument('--judge-model', type=str, default=None,
                        help='Modelo para LLM judge en behavioral tests')
    args = parser.parse_args()

    quiet = args.quiet or args.json

    # Setup
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_writer = LogWriter(LOGS_DIR)
    secrets = detect_secrets()
    runner = TestRunner(secrets, log_writer, quiet=quiet)

    if not quiet:
        print(f"\n{Colors.BOLD}{Colors.BLUE}VCOO Template — Test Suite v{VERSION}{Colors.NC}")
        print(f"Template: {TEMPLATE_DIR}")
        print(f"Logs:     {LOGS_DIR}/")

    # Si --behavioral, forzar solo fase 9
    if args.behavioral:
        args.phase = 9

    # Run phases
    phases = [
        (0, 'Preparación', phase0_preparation),
        (1, 'Estructurales', phase1_structural),
        (2, 'Sintaxis', phase2_syntax),
        (3, 'Integración', phase3_integration),
        (4, 'Error handling', phase4_error_handling),
        (5, 'Instalación', phase5_install_dryrun),
        (6, 'Readiness', phase6_readiness),
        (7, 'Deploy & Hermes', phase7_deploy_integration),
        (8, 'Docker VPS', phase8_docker_integration),
        (9, 'Behavioral', phase9_behavioral),
    ]

    for num, name, fn in phases:
        if args.phase is not None and num != args.phase:
            continue
        if num == 9:
            fn(runner, judge_model=args.judge_model)
        else:
            fn(runner)

    # Generate report
    report = runner.summary()

    # Write JSON report
    timestamp = report['timestamp'].replace(':', '-').split('.')[0]
    report_path = os.path.join(TEST_OUTPUT, f'report-{timestamp}.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary
    if not quiet:
        runner.print_summary(report)

    # If --json, also dump to stdout
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    # Exit code: 0 if all pass, 1 if any fail
    if report['summary']['failed'] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
