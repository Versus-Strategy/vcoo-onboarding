import sys, os as _os
_sys_path = _os.path.dirname(__file__)
if _sys_path not in sys.path:
    sys.path.insert(0, _sys_path)

from dotenv import load_dotenv
load_dotenv(_os.path.join(_sys_path, '.env'))

from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session
import db
from db import engine, Base, SessionLocal
import models, crud, auth, schemas, ratelimit
from typing import Any
from ws_routes import register_ws_routes
import json
import os as _os


# ── URLs de producción (por defecto si no hay variable de entorno) ──────────

_CONTROL_PLANE_PROD = "https://vcoo-onboarding.vercel.app"
_DASHBOARD_PROD = "https://vcoo-dashboard.vercel.app"

# Comandos de verificación válidos para agentes (compartido entre poll y tick)
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _safe_read_file(path: str) -> str:
    """Lee un archivo con límite de tamaño para evitar DoS."""
    size = _os.path.getsize(path)
    if size > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande")
    with open(path, 'r') as f:
        return f.read()


def _install_command(control_plane: str, token: str) -> str:
    """Construye el comando curl para instalar el agente."""
    return f"curl -sSL {control_plane}/install.sh | CONTROL_PLANE={control_plane} PROVISION_TOKEN={token} bash -"


def _check_client_owns_vcoo(db: Session, client_email: str, vcoo_id: str) -> bool:
    """Verifica que un cliente sea dueño del VCOO."""
    client_obj = crud.get_client_by_email(db, client_email)
    return bool(client_obj and client_obj.vcoo_id and str(client_obj.vcoo_id) == vcoo_id)
_VALID_AGENT_COMMANDS = {
    "verify-bootstrap", "verify-google", "verify-trello", "verify-email",
    "verify-github", "verify-vercel", "verify-supabase", "verify-whatsapp",
    "save-creds", "finalize", "set-provider", "pair-whatsapp",
}

# Plantilla de error para token inválido (reutilizada en múltiples endpoints)
_TOKEN_INVALID_ERROR = {
    "error": "token_invalid",
    "message": "El enlace de invitación ha caducado o es inválido. Por favor, solicite un nuevo enlace en el panel de control.",
    "action": "solicitar_nuevo_enlace",
}


def _url(var: str, *, vercel_default: str, local_default: str) -> str:
    """Lee una URL del entorno; si no está definida, elige un default según si
    estamos en Vercel (producción) o local (desarrollo)."""
    val = _os.getenv(var)
    if val and val.strip():
        return val.strip()
    if _os.getenv("VERCEL_ENV"):
        return vercel_default
    return local_default




application = FastAPI(title="VCOO Onboarding API v2")


@application.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Global exception handler — return detail but not traceback in production
@application.exception_handler(Exception)
async def global_exception_handler(request, exc):
    content = {"detail": str(exc)}
    if not _os.getenv("VERCEL_ENV"):
        import traceback
        content["traceback"] = traceback.format_exc()
    return JSONResponse(status_code=500, content=content)

_cors_origins = [
    "https://vcoo-onboarding.vercel.app",
    "https://vcoo-dashboard.vercel.app",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:4173",
]
frontend_url = _os.getenv("FRONTEND_URL", "").strip()
dashboard_url = _os.getenv("DASHBOARD_URL", "").strip()
control_plane = _os.getenv("CONTROL_PLANE", "").strip()
for url in [frontend_url, dashboard_url, control_plane]:
    if url and url not in _cors_origins:
        _cors_origins.append(url)
        if ":3000" in url:
            _cors_origins.append(url.replace(":3000", ":4173"))
        elif ":4173" in url:
            _cors_origins.append(url.replace(":4173", ":3000"))

application.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_first_operator():
    """Crea el primer operador si aún no existe ninguno.

    Lee FIRST_OPERATOR_EMAIL/PASSWORD/NAME del entorno. Trata las variables
    vacías como ausentes (os.getenv devuelve "" si están definidas vacías, lo
    que NO dispararía un default) y aplica fallbacks. Si tras aplicar fallbacks
    el email o la contraseña siguen vacíos, NO crea la cuenta: sembrar un
    operador con credenciales vacías produce una cuenta inservible con la que
    nadie puede autenticarse.
    """
    import sys as _sys
    try:
        db = SessionLocal()
        try:
            if crud.count_operators(db) != 0:
                return
            admin_email = (_os.getenv('FIRST_OPERATOR_EMAIL') or 'admin@versus-strategy.com').strip()
            admin_password = _os.getenv('FIRST_OPERATOR_PASSWORD') or ''
            admin_name = (_os.getenv('FIRST_OPERATOR_NAME') or 'Admin').strip()
            if not admin_email or not admin_password:
                print(
                    "[seed] SKIP: FIRST_OPERATOR_EMAIL/PASSWORD vacíos; "
                    "no se crea operador (define valores no vacíos para sembrarlo).",
                    file=_sys.stderr,
                )
                return
            pw_hash = auth.hash_password(admin_password)
            crud.create_operator(db, email=admin_email, password_hash=pw_hash, name=admin_name)
            print(f"[seed] Created first operator: {admin_email}")
        finally:
            db.close()
    except Exception as e:
        print(f"[seed] Skipped: {e}", file=_sys.stderr)


def _should_run_startup_migrations() -> bool:
    """¿Debe ejecutarse la creación de esquema + migraciones en el arranque?

    En serverless (Vercel) el evento `startup` se ejecuta en CADA cold start, y
    hacer `CREATE DATABASE` + `create_all` + sondas a information_schema + ALTER
    añade ~7-9 idas y vueltas a Supabase (con handshake SSL) ANTES de poder
    responder a la primera petición. En producción el esquema ya existe, así que
    ese trabajo es lastre puro en la latencia de la primera carga.

    Por eso el esquema/migraciones solo corren:
      - en local/CI/dev (cuando VERCEL_ENV no está definido), donde la BD puede
        no existir todavía, o
      - cuando se fuerza explícitamente con RUN_STARTUP_MIGRATIONS=1 (p.ej. un
        job puntual de despliegue).
    """
    if _os.getenv("RUN_STARTUP_MIGRATIONS") == "1":
        return True
    return _os.getenv("VERCEL_ENV") is None


def run_startup_migrations():
    """Crea la base de datos, las tablas y aplica migraciones de columnas.

    Solo pensado para entornos donde el esquema puede no existir todavía
    (local/CI). Ver `_should_run_startup_migrations`.
    """
    from sqlalchemy import text as _sql_text
    import sys as _sys
    # ── Ensure database exists (solo tiene sentido en Postgres local tipo Docker;
    # en Supabase la BD siempre existe) ──
    try:
        db_url = _os.environ.get('POSTGRES_URL', 'postgresql://postgres:postgres@db:5432/postgres')
        base_url = db_url.rsplit('/', 1)[0] + '/postgres'
        from sqlalchemy import create_engine as _ce
        admin_engine = _ce(base_url)
        with admin_engine.connect() as conn:
            conn.execute(_sql_text("COMMIT"))
            result = conn.execute(_sql_text("SELECT 1 FROM pg_database WHERE datname='vcoo'")).fetchone()
            if not result:
                conn.execute(_sql_text("CREATE DATABASE vcoo"))
                print("[startup] Created database 'vcoo'")
        admin_engine.dispose()
    except Exception as e:
        print(f"[startup] Cannot ensure database: {e}", file=_sys.stderr)
    # ── Create tables ──
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[startup] create_all skipped (DB unreachable): {e}", file=_sys.stderr)
    # ── Schema migrations (add columns that create_all won't add) ──
    try:
        with engine.connect() as conn:
            for col, ddl in (
                ("health_payload", "ALTER TABLE agents ADD COLUMN health_payload TEXT"),
                ("capabilities", "ALTER TABLE agents ADD COLUMN capabilities TEXT"),
                ("template_version", "ALTER TABLE agents ADD COLUMN template_version VARCHAR(32)"),
                ("supervisor_version", "ALTER TABLE agents ADD COLUMN supervisor_version VARCHAR(32)"),
            ):
                exists = conn.execute(_sql_text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='agents' AND column_name=:c"
                ), {"c": col}).fetchone()
                if not exists:
                    conn.execute(_sql_text(ddl))
                    conn.commit()
                    print(f"[migration] Added {col} column to agents table")
    except Exception as e:
        print(f"[migration] Skipped (non-critical): {e}", file=_sys.stderr)


@application.on_event("startup")
async def startup():
    if _should_run_startup_migrations():
        run_startup_migrations()
    if _os.getenv("VERCEL_ENV") is None:
        register_ws_routes(application)
    # ── Seed first operator (idempotente; 1 consulta) ──
    seed_first_operator()


# ── Health / Debug ────────────────────────────────────────────

@application.get('/healthz')
def healthz():
    """Healthcheck que comprueba la conectividad real con la base de datos.

    Devuelve 200 si la BD responde; 503 si no. Un 200 a ciegas ocultaría
    caídas de la BD (el backend quedaría inutilizable devolviendo 500 en cada
    request sin que ningún monitor lo detectara).
    """
    from sqlalchemy import text as _sql_text
    base = {"status": "ok", "version": "v2", "python": sys.version.split()[0]}
    try:
        db = SessionLocal()
        try:
            db.execute(_sql_text("SELECT 1"))
        finally:
            db.close()
        base["db"] = "ok"
        return base
    except Exception as e:
        base["status"] = "degraded"
        base["db"] = "error"
        base["detail"] = str(e).splitlines()[0][:200]
        return JSONResponse(content=base, status_code=503)


# ── OAuth callback ────────────────────────────────────────────


@application.post("/auth/verify")
def verify_auth(payload: dict, request: Request = None):
    client_ip = request.client.host if request and request.client else "unknown"
    ratelimit._login_limiter.check_and_record(client_ip)
    password = payload.get("password", "")
    if auth.verify_dashboard_password(password):
        return {"status": "ok"}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")


@application.post("/auth/login")
def operator_login(payload: schemas.LoginRequest, db: Session = Depends(get_db),
                   request: Request = None):
    """Operator login. Checks operators table first, falls back to DASHBOARD_PASSWORD."""
    client_ip = request.client.host if request and request.client else "unknown"
    ratelimit._login_limiter.check_and_record(client_ip)
    # Try operators table first
    op = crud.get_operator_by_email(db, payload.email)
    if op and auth.verify_password(payload.password, op.password_hash):
        token = auth.create_operator_token(op.email, op.name or '', str(op.id))
        return schemas.LoginResponse(
            token=token,
            user={"id": str(op.id), "email": op.email, "role": "operador", "name": op.name}
        )
    # Fallback to shared DASHBOARD_PASSWORD
    if auth.verify_dashboard_password(payload.password):
        name = payload.email.split('@')[0]
        token = auth.create_operator_token(payload.email, name)
        return schemas.LoginResponse(
            token=token,
            user={"email": payload.email, "role": "operador", "name": name}
        )
    raise HTTPException(status_code=401, detail="Credenciales inválidas")


@application.post("/auth/refresh")
def refresh_token(payload: schemas.RefreshRequest, db: Session = Depends(get_db)):
    """Refresh an existing JWT (operator or client). Issues a new token.
    Note: does NOT revoke the old JTI because the same JWT serves as both
    access token and refresh token. Revoking it would break in-flight requests."""
    decoded = auth.decode_token_ignore_expiry(payload.refreshToken)
    if not decoded:
        raise HTTPException(status_code=401, detail="Token inválido")

    role = decoded.get('role')
    exp_ts = decoded.get('exp', 0)

    # Grace period: up to 30 days past expiration
    if datetime.utcnow().timestamp() - exp_ts > 30 * 86400:
        raise HTTPException(status_code=401, detail="Token expirado, no se puede renovar")

    if role == 'operador':
        email = decoded.get('email', '')
        name = decoded.get('name', '')
        operator_id = decoded.get('operator_id', '')
        new_token = auth.create_operator_token(email, name, operator_id)
        return {
            "token": new_token,
            "user": {"id": operator_id, "email": email, "role": "operador", "name": name},
        }
    elif role == 'cliente':
        client_id = decoded.get('client_id', '')
        vcoo_id = decoded.get('vcoo_id', '')
        email = decoded.get('email', '')
        client_obj = crud.get_client_by_email(db, email)
        if not client_obj:
            raise HTTPException(status_code=401, detail="Cliente no encontrado")
        new_token = auth.create_client_token(
            str(client_obj.id),
            str(client_obj.vcoo_id) if client_obj.vcoo_id else vcoo_id,
            client_obj.email,
        )
        return {
            "token": new_token,
            "client": {
                "id": str(client_obj.id),
                "email": client_obj.email,
                "name": client_obj.name,
                "vcoo_id": str(client_obj.vcoo_id) if client_obj.vcoo_id else None,
            },
        }

    raise HTTPException(status_code=401, detail="Rol no soportado para refresh")


# ── Operator auth ────────────────────────────────────────────

@application.post("/auth/operator/register")
def operator_register(payload: schemas.OperatorRegisterRequest, db: Session = Depends(get_db),
                      request: Request = None):
    """Register a new operator."""
    client_ip = request.client.host if request and request.client else "unknown"
    ratelimit._login_limiter.check_and_record(client_ip)
    existing = crud.get_operator_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email ya registrado")
    password_hash = auth.hash_password(payload.password)
    op = crud.create_operator(db, email=payload.email, password_hash=password_hash, name=payload.name)
    token = auth.create_operator_token(op.email, op.name or '', str(op.id))
    return {
        "token": token,
        "operator": {"id": str(op.id), "email": op.email, "name": op.name},
    }


@application.post("/auth/revoke")
def revoke_operator_token(payload: dict, db: Session = Depends(get_db),
                          operator: dict = Depends(auth.verify_operator_jwt)):
    """Revoke an operator or client token by its JTI. Requires operator auth."""
    jti = payload.get("jti", "")
    if not jti:
        raise HTTPException(status_code=400, detail="jti requerido")
    crud.revoke_token(db, jti, revoked_by=operator.get('operator_id'))
    crud.create_audit_log(db, action="token.revoked", actor_email=operator.get('email'),
                          actor_id=operator.get('operator_id'), metadata={"jti": jti})
    return {"status": "revoked", "jti": jti}


# ── Client auth ──────────────────────────────────────────────

@application.post("/auth/client/register")
def client_register(payload: schemas.ClientRegisterRequest, db: Session = Depends(get_db),
                    request: Request = None):
    """Register a new client linked to a VCOO via a provision token or VCOO UUID."""
    client_ip = request.client.host if request and request.client else "unknown"
    ratelimit._login_limiter.check_and_record(client_ip)
    # 1. Validate the provision token (consume it — one-time use)
    vcoo_id = crud.validate_provision_token(db, payload.token, mark_used=True)
    if not vcoo_id:
        # Fallback: accept VCOO UUID directly (wizard sends the UUID from the URL)
        v = crud.get_vcoo(db, payload.token)
        if v:
            vcoo_id = str(v.id)
    if not vcoo_id:
        raise HTTPException(status_code=400, detail="Token de provision inválido o expirado")
    # 2. Check email not already registered
    existing = crud.get_client_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email ya registrado")
    # 3. Hash password
    password_hash = auth.hash_password(payload.password)
    # 4. Create client linked to token's vcoo_id
    client = crud.create_client(db, email=payload.email, password_hash=password_hash,
                                name=payload.name, vcoo_id=vcoo_id)
    # 5. Return JWT + client info
    token = auth.create_client_token(str(client.id), vcoo_id, client.email)
    client_resp = schemas.ClientResponse(
        id=str(client.id),
        email=client.email,
        name=client.name,
        vcoo_id=str(client.vcoo_id) if client.vcoo_id else None,
        created_at=client.created_at.isoformat() if client.created_at else None,
    )
    return {
        "token": token,
        "client": client_resp.model_dump() if hasattr(client_resp, 'model_dump') else client_resp.dict(),
    }


@application.post("/auth/client/login")
def client_login(payload: schemas.ClientLoginRequest, db: Session = Depends(get_db),
                 request: Request = None):
    """Login for existing clients."""
    client_ip = request.client.host if request and request.client else "unknown"
    ratelimit._login_limiter.check_and_record(client_ip)
    # 1. Find client by email
    client = crud.get_client_by_email(db, payload.email)
    if not client:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    # 2. Verify password
    if not auth.verify_password(payload.password, client.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    # 3. Return JWT + client info
    vcoo_id = str(client.vcoo_id) if client.vcoo_id else ""
    token = auth.create_client_token(str(client.id), vcoo_id, client.email)
    client_resp = schemas.ClientResponse(
        id=str(client.id),
        email=client.email,
        name=client.name,
        vcoo_id=vcoo_id or None,
        created_at=client.created_at.isoformat() if client.created_at else None,
    )
    return {
        "token": token,
        "client": client_resp.model_dump() if hasattr(client_resp, 'model_dump') else client_resp.dict(),
    }


@application.get("/auth/client/me")
def client_me(client: dict = Depends(auth.get_client_from_token), db: Session = Depends(get_db)):
    """Get current client info plus linked VCOO state."""
    client_obj = crud.get_client_by_email(db, client.get("email", ""))
    if not client_obj:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    result = {
        "id": str(client_obj.id),
        "email": client_obj.email,
        "name": client_obj.name,
        "vcoo_id": str(client_obj.vcoo_id) if client_obj.vcoo_id else None,
        "created_at": client_obj.created_at.isoformat() if client_obj.created_at else None,
    }
    # Add linked VCOO state if available
    if client_obj.vcoo_id:
        try:
            vcoo_id = str(client_obj.vcoo_id)
            v = crud.get_vcoo(db, vcoo_id)
            if v:
                agent = crud.get_agent_by_vcoo(db, vcoo_id)
                st = crud.get_onboarding_state(db, vcoo_id)
                result["vcoo"] = v.to_dict()
                result["vcoo"]["agent"] = agent.to_dict() if agent else None
                if st:
                    from onboarding import get_total_steps
                    modules = list(st.modules or ["core"])
                    result["vcoo"]["modules"] = modules
                    result["vcoo"]["step"] = st.step
                    result["vcoo"]["onboarding_status"] = st.status
                    result["vcoo"]["completed_steps"] = st.completed or []
                    result["vcoo"]["progress"] = {
                        "total": get_total_steps(modules),
                        "done": len(st.completed or []),
                    }
        except Exception:
            pass
    return result


# ── VCOO ──────────────────────────────────────────────────
@application.post("/vcoo")
def create_vcoo(payload: schemas.VCOOCreate = None, db: Session = Depends(get_db),
                operator: dict = Depends(auth.verify_operator_jwt)):
    name = payload.name if payload else None
    modules = payload.modules if payload else ["core"]
    vcoo = crud.create_vcoo(db, name=name)
    # Create onboarding state with selected modules
    crud.get_or_create_onboarding_state(db, str(vcoo.id), modules)
    # Generate provision token
    token = crud.create_provision_for_vcoo(db, str(vcoo.id))
    frontend_url = _url('FRONTEND_URL', vercel_default=_DASHBOARD_PROD, local_default='http://localhost:5173')
    onboarding_url = frontend_url.rstrip('/') + '/setup/' + str(vcoo.id)
    crud.create_audit_log(db, action="vcoo.created", vcoo_id=str(vcoo.id), metadata={"name": name})
    return {
        "id": str(vcoo.id),
        "name": vcoo.name,
        "status": vcoo.status,
        "modules": modules,
        "onboarding_url": onboarding_url,
    }

@application.get("/vcoos")
def list_vcoos(db: Session = Depends(get_db), operator: dict = Depends(auth.verify_operator_jwt)):
    """List all VCOOs with agent status and active token."""
    vcoos = crud.list_vcoos(db)
    dashboard_url = _url('DASHBOARD_URL', vercel_default=_DASHBOARD_PROD, local_default='http://localhost:3000')
    return [
        {
            "id": str(v.id),
            "name": v.name,
            "status": v.status,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "agent": {
                "id": str(v.agent.id),
                "status": 'offline' if (
                    not v.agent.last_seen or
                    (v.agent.last_seen and
                    (datetime.utcnow() - v.agent.last_seen.replace(tzinfo=None)).total_seconds() >= 120)
                ) else v.agent.status if v.agent.status == 'online' else v.agent.status,
                "last_seen": v.agent.last_seen.isoformat() if v.agent.last_seen else None,
            } if v.agent else None,
            "active_token": v.active_token.token if v.active_token else None,
            "token_expires_at": v.active_token.expires_at.isoformat() if v.active_token and v.active_token.expires_at else None,
            "modules": v.modules if hasattr(v, 'modules') and v.modules else ["core"],
            "onboarding_url": f"{dashboard_url}/setup/{v.id}" if v.active_token else None,
        }
        for v in vcoos
    ]


# ── Setup wizard (SPEC v2 §4.2) ───────────────────────────

@application.get("/setup/{identifier}")
def get_setup_info(identifier: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Returns onboarding state for the wizard frontend.
    Accepts VCOO UUID (preferred) or legacy JWT provision token as {identifier}.
    Access:
    - No auth → Case 1: requires_registration
    - Client who owns VCOO → Case 3: full state
    - Operator → Case 3: full state
    - Other → 403: access denied
    Read-only — does not consume the token."""
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(
                    status_code=400,
                    detail=_TOKEN_INVALID_ERROR,
                )
    vcoo_id = str(v.id)


    # Determine auth state
    is_operator = False
    is_owner = False
    if authorization and authorization.lower().startswith('bearer '):
        bearer_token = authorization.split(None, 1)[1]
        payload = auth.verify_client_token(bearer_token)
        if payload:
            if payload.get('role') == 'operador':
                is_operator = True
            else:
                client_email = payload.get("email", "")
                is_owner = _check_client_owns_vcoo(db, client_email, vcoo_id)

    if not is_operator and not is_owner:
        if authorization and authorization.lower().startswith('bearer '):
            raise HTTPException(status_code=403, detail="No tienes acceso a este VCOO")
        # Case 1: No auth — tell frontend to show registration form
        return {
            "requires_registration": True,
            "token_valid": True,
            "vcoo_name": v.name,
        }

    # Case 3: Full onboarding state (owner or operator)
    st = crud.get_onboarding_state(db, vcoo_id)
    if not st:
        raise HTTPException(status_code=404, detail="No hay datos de onboarding")
    from onboarding import get_total_steps, get_module_label, get_module_description, get_wizard_step, is_onboarding_complete
    modules = list(st.modules or ["core"])
    total = get_total_steps(modules)
    done = len(st.completed or [])
    module_labels: dict[str, dict[str, str]] = {
        m: {"label": get_module_label(m), "description": get_module_description(m)}
        for m in modules
    }
    current_step = st.step
    completed_steps = st.completed or []
    all_done = is_onboarding_complete(current_step, completed_steps, modules)
    control_plane = _url('CONTROL_PLANE', vercel_default=_CONTROL_PLANE_PROD, local_default='http://localhost:8000')
    active_token_obj = crud.get_active_token_for_vcoo(db, vcoo_id)
    if not active_token_obj:
        raw_token = crud.create_provision_for_vcoo(db, vcoo_id)
    else:
        raw_token = active_token_obj.token
    install_cmd = _install_command(control_plane, raw_token)
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    agent_online = False
    providers: list = []
    checks: dict = {}
    agent_models: dict = {}
    if agent and agent.last_seen:
        import datetime as dt
        ago = (dt.datetime.utcnow() - agent.last_seen.replace(tzinfo=None)).total_seconds()
        agent_online = ago < 120
        if agent.capabilities:
            try:
                caps = json.loads(agent.capabilities)
                providers = caps.get("providers") or []
                checks = caps.get("checks", {})
                agent_models = caps.get("models", {})
            except Exception:
                pass
    return {
        "requires_registration": False,
        "vcoo_id": str(v.id),
        "name": v.name,
        "modules": modules,
        "module_labels": module_labels,
        "providers": providers,
        "checks": checks,
        "models": agent_models,
        "step": current_step,
        "wizard_step": get_wizard_step(current_step),
        "status": st.status,
        "completed": completed_steps,
        "all_done": all_done,
        "errors": st.errors or [],
        "retry_count": st.retry_count or {},
        "progress": {"total": total, "done": done},
        "install_command": install_cmd,
        "agent_online": agent_online,
    }


@application.post("/setup/{identifier}/verify")
def trigger_step_verification(identifier: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Client clicks 'Verificar' in the wizard — enqueues the verification command.
    Waits up to 10s for the agent to register (race condition fix).
    If no agent is connected, auto-advances the step for dev/demo mode."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="auth required")
    bearer = authorization.split(None, 1)[1]
    token_payload = auth.verify_client_token(bearer)
    if not token_payload:
        raise HTTPException(status_code=401, detail="invalid token")
    is_operator = token_payload.get('role') == 'operador'
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(
            status_code=400,
            detail=_TOKEN_INVALID_ERROR,
        )
    vcoo_id = str(v.id)
    if not is_operator:
        client_email = token_payload.get("email", "")
        if not _check_client_owns_vcoo(db, client_email, vcoo_id):
            raise HTTPException(status_code=403, detail="not your VCOO")
    st = crud.get_onboarding_state(db, vcoo_id)
    if not st:
        raise HTTPException(status_code=404, detail="No hay datos de onboarding")
    from onboarding import get_step_command
    step = st.step
    if step == "finalize" or step == "done":
        return {"status": "skip", "message": "Onboarding ya completado"}
    cmd_name = get_step_command(step)

    # Wait up to 10s for agent to appear (race condition fix)
    import time as _time
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    agent_alive = False
    for _ in range(10):
        if agent and agent.last_seen:
            import datetime as dt
            ago = (dt.datetime.utcnow() - agent.last_seen.replace(tzinfo=None)).total_seconds()
            if ago < 120:
                agent_alive = True
                break
        _time.sleep(1)
        db.commit()  # refresh session
        agent = crud.get_agent_by_vcoo(db, vcoo_id)

    if agent and agent_alive:
        # Check for existing pending command for this step (idempotency)
        existing = db.query(models.Command).filter(
            models.Command.agent_id == str(agent.id),
            models.Command.command == cmd_name,
            models.Command.step == step,
            models.Command.status == 'pending',
        ).first()
        if existing:
            return {"status": "enqueued", "cmd_id": str(existing.id), "step": step, "command": cmd_name, "duplicate": True}
        cmd = crud.create_command(db, agent_id=str(agent.id), command=cmd_name, step=step)
        # Si el paso es bootstrap, el hecho de que el agente esté vivo
        # ya verifica que la instalación fue exitosa; no necesitamos
        # esperar a que el agente procese `verify-bootstrap` para avanzar.
        if step == "bootstrap":
            crud.advance_onboarding_step(db, vcoo_id, step)
            db.refresh(st)
            return {
                "status": "completed",
                "cmd_id": str(cmd.id),
                "step": step,
                "next_step": st.step,
                "message": "Agente detectado, paso completado.",
            }
        return {
            "status": "enqueued",
            "cmd_id": str(cmd.id),
            "step": step,
            "command": cmd_name,
        }
    else:
        crud.advance_onboarding_step(db, vcoo_id, step)
        db.refresh(st)
        return {
            "status": "auto_completed",
            "step": step,
            "next_step": st.step,
            "message": "Paso completado automaticamente (modo demo). En produccion, el agente ejecutara la verificacion real.",
        }


# ── Google OAuth scopes per service ─────────────────────

_GOOGLE_SCOPES_MAP: dict[str, str] = {
    "google-drive": "https://www.googleapis.com/auth/drive+https://www.googleapis.com/auth/documents+https://www.googleapis.com/auth/spreadsheets+https://www.googleapis.com/auth/presentations",
    "google": "https://www.googleapis.com/auth/drive+https://www.googleapis.com/auth/documents+https://www.googleapis.com/auth/spreadsheets+https://www.googleapis.com/auth/presentations",
    "gmail": "https://www.googleapis.com/auth/gmail.readonly",
}


# ── Auth URL generation (dynamic OAuth tabs) ────────────

@ application.get("/setup/{identifier}/auth-url")
def get_auth_url(identifier: str, service: str = "", db: Session = Depends(get_db)):
    """Generates an OAuth authorization URL for the given service."""
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(
            status_code=400,
            detail=_TOKEN_INVALID_ERROR,
        )
    vcoo_id = str(v.id)
    service = service.lower().strip()
    if service in _GOOGLE_SCOPES_MAP:
        client_id = _os.getenv("GOOGLE_CLIENT_ID", "")
        redirect = _url('GOOGLE_REDIRECT_URI', vercel_default=f'{_CONTROL_PLANE_PROD}/auth/callback', local_default='http://localhost:8000/auth/callback')
        state = f"{vcoo_id}:{service}"
        if not client_id:
            raise HTTPException(status_code=400, detail="GOOGLE_CLIENT_ID no configurado. Contacta al administrador.")
        scopes = _GOOGLE_SCOPES_MAP[service]
        url = ("https://accounts.google.com/o/oauth2/v2/auth"
               f"?client_id={client_id}&redirect_uri={redirect}"
               f"&response_type=code&scope={scopes}"
               "&access_type=offline&prompt=consent"
               f"&state={state}")
        return {"url": url, "service": service}
    elif service == "trello":
        api_key = _os.getenv("TRELLO_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=400, detail="TRELLO_API_KEY no configurado. Contacta al administrador.")
        control_plane_oauth = _url('CONTROL_PLANE', vercel_default=_CONTROL_PLANE_PROD, local_default='http://localhost:8000')
        url = "https://trello.com/1/authorize?expiration=never&name=VCOO&scope=read,write&response_type=token&key={}&return_url={}".format(api_key, f"{control_plane_oauth}/auth/callback?service=trello")
        return {"url": url, "service": "trello"}
    elif service == "github":
        return {"url": "https://cli.github.com/manual/gh_auth_login", "service": "github", "instructions": "Ejecuta 'gh auth login' en tu VPS."}
    elif service == "vercel":
        return {"url": "https://vercel.com/login", "service": "vercel", "instructions": "Ejecuta 'vercel login' en tu VPS."}
    elif service == "supabase":
        return {"url": "https://supabase.com/dashboard/login", "service": "supabase", "instructions": "Ejecuta 'supabase login' en tu VPS."}
    else:
        raise HTTPException(status_code=400, detail="Servicio no soportado: " + service)


# ── OAuth callback ─────────────────────────────────────

@application.get("/auth/callback")
def oauth_callback(code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)):
    """Receives OAuth callback from Google. Exchanges code for tokens, queues save-creds."""
    # Handle user denial / errors
    if error:
        return HTMLResponse(
            "<html><body style=\"background:#0a0a0f;color:#e2e8f0;font-family:sans-serif;text-align:center;padding:60px\">"
            f"<h1 style=\"color:#ef4444\">Autorizacion denegada</h1><p>{error}</p>"
            "<script>setTimeout(function(){window.close()},5000)</script></body></html>"
        )
    if not code:
        return HTMLResponse(
            "<html><body style=\"background:#0a0a0f;color:#e2e8f0;font-family:sans-serif;text-align:center;padding:60px\">"
            "<h1 style=\"color:#ef4444\">Error</h1><p>Falta el codigo de autorizacion (code)</p>"
            "<script>setTimeout(function(){window.close()},5000)</script></body></html>",
            status_code=400,
        )

    # Parse service from state: "{vcoo_id}:{service}" — fallback to "google"
    service = "google"
    vcoo_id = state
    if ":" in (state or ""):
        parts = state.split(":", 1)
        # vcoo_id must be a valid UUID; keep the full state if split produces garbage
        raw_vcoo = parts[0]
        if len(raw_vcoo) >= 32:  # heuristic: UUIDs are 32+ hex chars
            vcoo_id = raw_vcoo
        service = parts[1] if len(parts) > 1 else "google"

    agent = None
    if vcoo_id:
        try:
            agent = crud.get_agent_by_vcoo(db, vcoo_id)
        except Exception:
            # Malformed UUID in state — ignore, will still return success page
            pass

    # Try to exchange code for real tokens
    access_token = ""
    refresh_token = ""
    if service == "google":
        client_id = _os.getenv("GOOGLE_CLIENT_ID", "")
        client_secret = _os.getenv("GOOGLE_CLIENT_SECRET", "")
        redirect_uri = _url('GOOGLE_REDIRECT_URI', vercel_default=f'{_CONTROL_PLANE_PROD}/auth/callback', local_default='http://localhost:8000/auth/callback')
        if client_id and client_secret:
            try:
                import urllib.request
                import urllib.parse
                token_data = urllib.parse.urlencode({
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                }).encode()
                req = urllib.request.Request(
                    "https://oauth2.googleapis.com/token",
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    token_resp = json.loads(resp.read())
                    access_token = token_resp.get("access_token", "")
                    refresh_token = token_resp.get("refresh_token", "")
                    print(f"[oauth] Google token exchange OK, access_token={'ok' if access_token else 'EMPTY'}, refresh_token={'ok' if refresh_token else 'EMPTY'}", file=sys.stderr)
            except urllib.error.HTTPError as e:
                error_body = e.read().decode()
                print(f"[oauth] HTTP {e.code} from token endpoint: {error_body[:200]}", file=sys.stderr)
                print(f"[oauth] redirect_uri used: {redirect_uri}", file=sys.stderr)
                # Store error for debugging
                _oauth_error = error_body[:200]
            except Exception as e:
                print(f"[oauth] Token exchange failed: {e}", file=sys.stderr)
                print(f"[oauth] redirect_uri: {redirect_uri}", file=sys.stderr)
                _oauth_error = str(e)
                import traceback
                traceback.print_exc(file=sys.stderr)

    # Map service to the correct onboarding step and advance it NOW
    step_map: dict[str, str] = {
        "google": "google-oauth",
        "google-drive": "google-oauth",
        "gmail": "gmail-setup",
        "trello": "trello-setup",
    }
    mapped_step = step_map.get(service, "save-creds")

    # Advance onboarding step immediately (don't wait for agent)
    if vcoo_id:
        try:
            crud.advance_onboarding_step(db, vcoo_id, mapped_step)
            # Enqueue next command if the agent is connected (mirrors process_agent_result auto-trigger)
            st = crud.get_onboarding_state(db, vcoo_id)
            if st and agent and st.step not in ("done",):
                from onboarding import get_step_command
                cmd_name = get_step_command(st.step)
                if cmd_name:
                    crud.create_command(db, agent_id=str(agent.id), command=cmd_name, step=st.step)
        except Exception:
            pass  # best-effort — command queue is the fallback

    if agent:
        creds_data = {
            "service": service,
            "code": code,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "client_id": _os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": _os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": _GOOGLE_SCOPES_MAP.get(service, "").split("+"),
        }
        crud.create_command(
            db, agent_id=str(agent.id), command="save-creds", step=mapped_step,
            result=json.dumps(creds_data),
        )

    frontend_origin = _url('DASHBOARD_URL', vercel_default=_DASHBOARD_PROD, local_default='http://localhost:3000')
    oauth_error = locals().get('_oauth_error', '')
    error_html = ""
    if oauth_error:
        error_html = f"<p style=\"color:#fbbf24;font-size:12px;margin-top:20px;word-break:break-all\">Debug: {oauth_error}</p>"
    if access_token:
        return HTMLResponse(
            "<html><body style=\"background:#0a0a0f;color:#e2e8f0;font-family:sans-serif;text-align:center;padding:40px\">"
            "<h1 style=\"color:#533afd\">Autorizacion recibida</h1>"
            "<p>Vuelve al wizard para continuar.</p>"
            + error_html +
            "<script>"
            "try{if(window.opener){window.opener.postMessage('oauth-complete','" + frontend_origin + "');}}catch(e){}"
            "setTimeout(function(){window.close()},1500)"
            "</script></body></html>"
        )
    else:
        return HTMLResponse(
            "<html><body style=\"background:#0a0a0f;color:#e2e8f0;font-family:sans-serif;text-align:center;padding:40px\">"
            "<h1 style=\"color:#ef4444\">Error de autenticacion</h1>"
            "<p>No se pudo obtener el token de acceso de Google.</p>"
            + error_html +
            "<p style=\"margin-top:20px\"><a href=\"javascript:window.close()\" style=\"color:#533afd\">Cerrar ventana</a></p>"
            "</body></html>"
        )


# ── Hermes CLI commands (dynamic) ──────────────────────

@ application.get("/setup/{identifier}/hermes-commands")
def get_hermes_commands_endpoint(identifier: str, service: str = "", db: Session = Depends(get_db)):
    """Returns Hermes CLI config commands for a service."""
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(
            status_code=400,
            detail=_TOKEN_INVALID_ERROR,
        )
    vcoo_id = str(v.id)
    service = service.lower().strip()
    commands_map = {
        "google": ["hermes config set google.client_id TU_CLIENT_ID", "hermes config set google.client_secret TU_CLIENT_SECRET"],
        "trello": ["hermes config set trello.api_key TU_API_KEY", "hermes config set trello.api_token TU_TOKEN"],
        "github": ["gh auth login", "hermes config set github.token $(gh auth token)"],
        "vercel": ["vercel login", "hermes config set vercel.token TU_TOKEN"],
        "supabase": ["supabase login", "hermes config set supabase.access_token TU_ACCESS_TOKEN"],
        "whatsapp": ["hermes whatsapp"],
        "opencode": ["hermes config set model.provider opencode", "hermes config set model.default opencode/claude-sonnet-4"],
        "anthropic": ["export ANTHROPIC_API_KEY=sk-ant-tu-clave", "hermes config set model.provider anthropic"],
        "openai": ["export OPENAI_API_KEY=sk-tu-clave", "hermes config set model.provider openai"],
    }
    return {"commands": commands_map.get(service, []), "service": service}


@application.get("/vcoo/{vcoo_id}/provision-token")
def get_provision_token(vcoo_id: str, db: Session = Depends(get_db),
                        operator: dict = Depends(auth.verify_operator_jwt)):
    """Return existing active token for this VCOO, or create one if none exists."""
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    active = crud.get_active_token_for_vcoo(db, vcoo_id)
    if active:
        token = active.token
    else:
        token = crud.create_provision_for_vcoo(db, vcoo_id)
    dashboard_url = _url('DASHBOARD_URL', vercel_default=_DASHBOARD_PROD, local_default='http://localhost:3000')
    control_plane = _url('CONTROL_PLANE', vercel_default=_CONTROL_PLANE_PROD, local_default='http://localhost:8000')
    install_cmd = f"curl -sSL {control_plane}/install.sh | PROVISION_TOKEN={token} bash -"
    onboarding_url = f"{dashboard_url}/setup/{vcoo_id}"
    return {"token": token, "install_command": install_cmd, "onboarding_url": onboarding_url}

@application.post("/vcoo/{vcoo_id}/regenerate-token")
def regenerate_token(vcoo_id: str, db: Session = Depends(get_db),
                     operator: dict = Depends(auth.verify_operator_jwt)):
    """Revoke current token and generate a new one."""
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    token = crud.regenerate_token_for_vcoo(db, vcoo_id)
    dashboard_url = _url('DASHBOARD_URL', vercel_default=_DASHBOARD_PROD, local_default='http://localhost:3000')
    control_plane = _url('CONTROL_PLANE', vercel_default=_CONTROL_PLANE_PROD, local_default='http://localhost:8000')
    install_cmd = f"curl -sSL {control_plane}/install.sh | PROVISION_TOKEN={token} bash -"
    onboarding_url = f"{dashboard_url}/setup/{vcoo_id}"
    crud.create_audit_log(db, action="token.regenerated", actor_email=operator.get('email'),
                          actor_id=operator.get('operator_id'), vcoo_id=vcoo_id)
    return {"token": token, "install_command": install_cmd, "onboarding_url": onboarding_url}

@application.post("/vcoo/{vcoo_id}/complete")
def complete_vcoo(vcoo_id: str, db: Session = Depends(get_db),
                  operator: dict = Depends(auth.verify_operator_jwt)):
    """Mark VCOO as completed (setup finished). Logs are preserved."""
    v = crud.complete_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    crud.create_audit_log(db, action="vcoo.completed", actor_email=operator.get('email'),
                          actor_id=operator.get('operator_id'), vcoo_id=vcoo_id)
    return {"status": "completed"}

@application.post("/vcoo/{vcoo_id}/reactivate")
def reactivate_vcoo(vcoo_id: str, db: Session = Depends(get_db),
                    operator: dict = Depends(auth.verify_operator_jwt)):
    """Reactivate a completed VCOO and generate a new token."""
    token = crud.reactivate_vcoo(db, vcoo_id)
    if not token:
        raise HTTPException(status_code=404, detail="VCOO not found")
    control_plane = _url('CONTROL_PLANE', vercel_default=_CONTROL_PLANE_PROD, local_default='http://localhost:8000')
    install_cmd = f"curl -sSL {control_plane}/install.sh | PROVISION_TOKEN={token} bash -"
    crud.create_audit_log(db, action="vcoo.reactivated", actor_email=operator.get('email'),
                          actor_id=operator.get('operator_id'), vcoo_id=vcoo_id)
    return {"status": "active", "token": token, "install_command": install_cmd}

@application.delete("/vcoo/{vcoo_id}")
def delete_vcoo(vcoo_id: str, db: Session = Depends(get_db),
                operator: dict = Depends(auth.verify_operator_jwt)):
    """Permanently delete a VCOO and all associated data."""
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    crud.create_audit_log(db, action="vcoo.deleted", actor_email=operator.get('email'),
                          actor_id=operator.get('operator_id'), vcoo_id=vcoo_id, metadata={"name": v.name})
    ok = crud.delete_vcoo(db, vcoo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="VCOO not found")
    return {"status": "deleted"}


# ── Agent registration & auth ─────────────────────────────

@application.post("/register")
def register_agent(payload: dict, db: Session = Depends(get_db)):
    token = payload.get("token")
    info = payload.get("info", {})
    vcoo_id = crud.validate_provision_token(db, token)
    if not vcoo_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    agent = crud.create_agent(db, vcoo_id=vcoo_id, info=json.dumps(info))
    agent_token = auth.create_agent_token(str(agent.id))
    payload_token = auth.decode_agent_token(agent_token)
    jti = payload_token.get('jti') if payload_token else None
    if jti:
        crud.set_agent_token_jti(db, str(agent.id), jti)

    # Generate encryption key for remote config (Fernet-based)
    agent_id_str = str(agent.id)
    master_key = _os.getenv('MASTER_KEY', '')
    if master_key:
        from crypto import generate_encryption_key
        enc_key = generate_encryption_key(master_key, agent_id_str)
        crud.set_agent_encryption_key(db, agent_id_str, enc_key)
    else:
        enc_key = None

    # ── Auto-trigger: encolar primer comando si hay onboarding pendiente ──
    st = crud.get_onboarding_state(db, vcoo_id)
    if st and st.status not in ("blocked", "completed") and st.step != "done":
        from onboarding import get_step_command
        cmd_name = get_step_command(st.step)
        if cmd_name:
            crud.create_command(db, agent_id=str(agent.id), command=cmd_name, step=st.step)
    # ────────────────────────────────────────────────────────────────

    crud.create_provision_for_vcoo(db, vcoo_id)
    return {"agent_id": str(agent.id), "vcoo_id": str(vcoo_id), "agent_token": agent_token, "encryption_key": enc_key}


@application.post("/agent/{agent_id}/refresh")
def refresh_agent_token(agent_id: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Refresh an agent token. Accepts the current (or recently expired) agent token
    in the Authorization header and returns a new one."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="missing auth")
    token = authorization.split(None, 1)[1]
    decoded = auth.decode_token_ignore_expiry(token)
    if not decoded or decoded.get('agent_id') != agent_id:
        raise HTTPException(status_code=401, detail="invalid agent token")

    agent = crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")

    new_token = auth.create_agent_token(agent_id)
    payload_token = auth.decode_agent_token(new_token)
    jti = payload_token.get('jti') if payload_token else None
    if jti:
        crud.set_agent_token_jti(db, agent_id, jti)

    return {"token": new_token}


@application.post("/agent/{agent_id}/revoke")
def revoke_agent_token(agent_id: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Revoke an agent's current token. Accepts the agent token in Authorization header
    and revokes it immediately."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="missing auth")
    token = authorization.split(None, 1)[1]
    decoded = auth.decode_token_ignore_expiry(token)
    if not decoded or decoded.get('agent_id') != agent_id:
        raise HTTPException(status_code=401, detail="invalid agent token")

    jti = decoded.get('jti', '')
    if jti:
        crud.revoke_token(db, jti, token_type='agent')
    return {"status": "revoked", "agent_id": agent_id}


# ── Agent polling & logs ──────────────────────────────────

@application.get("/agent/{agent_id}/poll")
def agent_poll(agent_id: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="missing auth")
    token = authorization.split(None, 1)[1]
    payload = auth.decode_agent_token(token)
    if not payload or payload.get('agent_id') != agent_id:
        raise HTTPException(status_code=401, detail="invalid agent token")
    agent = crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    crud.touch_agent(db, agent_id)
    pending = crud.get_pending_commands(db, agent_id)
    result = []
    for cmd in pending:
        if cmd.command not in _VALID_AGENT_COMMANDS:
            crud.mark_command_done(db, cmd.id, result="BLOCKED: comando no reconocido, descartado")
            continue
        entry = {"cmd_id": str(cmd.id), "command": cmd.command, "step": cmd.step}
        # Include payload for data-carrying commands
        if cmd.command in ("save-creds", "set-provider") and cmd.result:
            try:
                entry["payload"] = json.loads(cmd.result)
            except Exception:
                entry["payload"] = {"raw": cmd.result}
        result.append(entry)
        crud.mark_command_sent(db, cmd.id)

    # Incluir progreso del onboarding para la TUI
    st = None
    progress_data = {}
    if agent.vcoo_id:
        st = crud.get_onboarding_state(db, str(agent.vcoo_id))
        if st:
            from onboarding import get_agent_total_steps, has_agent_command
            modules = list(st.modules or ["core"])
            progress_data = {
                "done": len([s for s in (st.completed or []) if has_agent_command(s)]),
                "total": get_agent_total_steps(modules),
            }
    return {
        "commands": result,
        "progress": progress_data,
        "step": st.step if st else "",
        "onboarding_status": st.status if st else "unknown",
    }

@application.post("/agent/{agent_id}/complete")
def agent_setup_complete(agent_id: str, db: Session = Depends(get_db)):
    """Agent calls this when onboarding setup finishes.
    Marks the VCOO as completed and revokes its token."""
    agent = crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    crud.complete_vcoo(db, str(agent.vcoo_id))
    return {"status": "ok", "vcoo_completed": True}

@application.post('/agent/{agent_id}/logs')
def agent_logs(agent_id: str, payload: dict, db: Session = Depends(get_db)):
    cmd_id = payload.get('cmd_id')
    chunk = payload.get('chunk', '')
    stream = payload.get('stream', 'stdout')
    if not cmd_id:
        raise HTTPException(status_code=400, detail='cmd_id missing')
    crud.append_command_log(db, cmd_id, chunk, stream)
    return {'status': 'ok'}

@application.get('/agent/{agent_id}/logs')
def get_command_logs(agent_id: str, cmd_id: str = "", db: Session = Depends(get_db)):
    """Retrieve command logs for a specific cmd_id (or all recent)."""
    if cmd_id:
        logs = crud.get_command_logs(db, cmd_id)
        return {"cmd_id": cmd_id, "logs": logs}
    # If no cmd_id, return recent commands with their logs for this agent
    commands = crud.get_agent_commands(db, agent_id, limit=20)
    result = []
    for cmd in commands:
        logs = crud.get_command_logs(db, str(cmd.id))
        result.append({
            "cmd_id": str(cmd.id),
            "command": cmd.command,
            "step": cmd.step,
            "status": cmd.status,
            "result": (cmd.result or "")[:2000],
            "logs": logs[-50:] if logs else [],
        })
    return {"commands": result}


# ── Set Provider (remote config) ────────────────────────

@application.post("/vcoo/{vcoo_id}/set-provider")
def set_provider(vcoo_id: str, payload: dict, db: Session = Depends(get_db),
                 operator: dict = Depends(auth.verify_operator_jwt)):
    """Operator encrypts an AI provider API key and sends it to the agent.

    Payload: {provider, model, api_key}
      provider — e.g. "openrouter", "anthropic", "openai"
      model — e.g. "openrouter/deepseek-v4", "claude-sonnet-4"
      api_key — the API key to configure

    The API key is encrypted with Fernet using MASTER_KEY + agent_id
    so only the target agent can decrypt it.
    """
    provider = payload.get("provider", "").strip()
    model = payload.get("model", "").strip()
    api_key = payload.get("api_key", "").strip()

    if not provider or not api_key:
        raise HTTPException(status_code=400, detail="provider y api_key son requeridos")

    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if not agent:
        raise HTTPException(status_code=404, detail="no se encontró agente para este VCOO")

    if not agent.encryption_key:
        raise HTTPException(status_code=400, detail="el agente no tiene clave de cifrado (re-registrar)")

    from crypto import encrypt_api_key
    encrypted = encrypt_api_key(api_key, agent.encryption_key, str(agent.id))
    command_payload = json.dumps({
        "encrypted": encrypted,
        "provider": provider,
        "model": model,
    })
    cmd = crud.create_command(db, agent_id=str(agent.id), command="set-provider", result=command_payload)
    return {"status": "command_sent", "cmd_id": str(cmd.id), "provider": provider, "model": model}


# ── Commands ──────────────────────────────────────────────

@application.post("/vcoo/{vcoo_id}/commands")
def enqueue_command(vcoo_id: str, payload: dict, db: Session = Depends(get_db)):
    command_text = payload.get("command")
    if not command_text:
        raise HTTPException(status_code=400, detail="command missing")
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if not agent:
        raise HTTPException(status_code=404, detail="no agent connected for vcoo")
    step = payload.get("step")
    cmd = crud.create_command(db, agent_id=agent.id, command=command_text, step=step)
    return {"cmd_id": str(cmd.id)}

@application.post("/vcoo/{vcoo_id}/commands/{cmd_id}/result")
def command_result(vcoo_id: str, cmd_id: str, payload: dict, db: Session = Depends(get_db)):
    result = payload.get('result', '')
    crud.mark_command_done(db, cmd_id, result=result)
    return {"status": "ok"}


# ── State ─────────────────────────────────────────────────

@application.get("/vcoo/{vcoo_id}/state")
def get_state(vcoo_id: str, db: Session = Depends(get_db),
              operator: dict = Depends(auth.verify_operator_jwt)):
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    state = v.to_dict()
    state["agent"] = agent.to_dict() if agent else None
    # Inject capabilities from agent JSON column
    if agent and hasattr(agent, 'capabilities') and agent.capabilities:
        try:
            state["agent"]["capabilities"] = json.loads(agent.capabilities)
        except Exception:
            pass
    # Compute online/offline status from last_seen (120s threshold)
    if agent:
        from datetime import datetime
        agent_dict = state["agent"]
        if agent.last_seen and (datetime.utcnow() - agent.last_seen.replace(tzinfo=None)).total_seconds() >= 120:
            agent_dict["status"] = "offline"
        elif not agent.last_seen:
            agent_dict["status"] = "offline"
    active_token = crud.get_active_token_for_vcoo(db, vcoo_id)
    state["active_token"] = active_token.token if active_token else None
    # Add onboarding state (SPEC v2)
    st = crud.get_onboarding_state(db, vcoo_id)
    if st:
        from onboarding import get_total_steps
        modules = list(st.modules or ["core"])
        state["modules"] = modules
        state["step"] = st.step
        state["onboarding_status"] = st.status
        state["completed_steps"] = st.completed or []
        state["onboarding_errors"] = st.errors or []
        state["retry_count"] = st.retry_count or {}
        state["progress"] = {
            "total": get_total_steps(modules),
            "done": len(st.completed or []),
        }
    return state


# ── Agent result (SPEC v2 §4.4) ──────────────────────────

@application.post("/agent/{agent_id}/result")
def agent_report_result(agent_id: str, payload: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Agent reports command result. ACK semantics with backoff support."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="missing auth")
    token = authorization.split(None, 1)[1]
    payload2 = auth.decode_agent_token(token)
    if not payload2 or payload2.get('agent_id') != agent_id:
        raise HTTPException(status_code=401, detail="invalid agent token")
    from fastapi.responses import JSONResponse
    cmd_id = payload.get("cmd_id")
    step = payload.get("step", "")
    status = payload.get("status", "ok")
    output = payload.get("output", "")
    if not cmd_id:
        raise HTTPException(status_code=400, detail="cmd_id missing")
    cmd, acked, next_step, status_code = crud.process_agent_result(
        db, agent_id, cmd_id, step, status, output
    )
    if status_code == 404:
        raise HTTPException(status_code=404, detail="Command not found")
    if status_code == 409:
        return JSONResponse(
            content={"ack": True, "cmd_id": cmd_id, "status": "already_reported"},
            status_code=409,
        )
    result = {"ack": True, "cmd_id": cmd_id}
    if next_step:
        result["next_step"] = next_step
    if hasattr(cmd, 'id'):
        result["cmd_id"] = str(cmd.id)
    return JSONResponse(content=result, status_code=status_code)


@application.post("/setup/{identifier}/set-provider")
def setup_set_provider(identifier: str, payload: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Client sets provider credentials from onboarding wizard.
    Payload: {provider, api_key}
    """
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="auth required")
    bearer = authorization.split(None, 1)[1]
    token_payload = auth.verify_client_token(bearer)
    if not token_payload:
        raise HTTPException(status_code=401, detail="invalid token")

    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(status_code=400, detail="invalid identifier")
    vcoo_id = str(v.id)

    is_operator = token_payload.get('role') == 'operador'
    if not is_operator:
        client_email = token_payload.get("email", "")
        if not _check_client_owns_vcoo(db, client_email, vcoo_id):
            raise HTTPException(status_code=403, detail="not your VCOO")

    provider = payload.get("provider", "").strip()
    api_key = payload.get("api_key", "").strip()
    model = payload.get("model", "").strip()
    if not provider:
        raise HTTPException(status_code=400, detail="provider required")
    if not api_key and not model:
        raise HTTPException(status_code=400, detail="api_key or model required")

    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if not agent:
        raise HTTPException(status_code=400, detail="agent not installed yet")

    # El agente ahora implementa _crypto_decrypt, podemos cifrar la API key.
    if api_key and agent.encryption_key:
        from crypto import encrypt_api_key
        encrypted = encrypt_api_key(api_key, agent.encryption_key, str(agent.id))
        command_payload = json.dumps({
            "encrypted": encrypted,
            "provider": provider,
            "model": model,
        })
    else:
        command_payload = json.dumps({
            "api_key": api_key,
            "provider": provider,
            "model": model,
            "encrypted": False,
        })
    cmd = crud.create_command(db, agent_id=str(agent.id), command="set-provider", result=command_payload)
    return {"status": "command_sent", "cmd_id": str(cmd.id), "provider": provider}


@application.post("/setup/{identifier}/advance")
def setup_advance_step(identifier: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Advance onboarding step to next phase (after provider+model configured)."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="auth required")
    bearer = authorization.split(None, 1)[1]
    token_payload = auth.verify_client_token(bearer)
    if not token_payload:
        raise HTTPException(status_code=401, detail="invalid token")
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(status_code=400, detail="invalid identifier")
    vcoo_id = str(v.id)
    is_operator = token_payload.get('role') == 'operador'
    if not is_operator:
        client_email = token_payload.get("email", "")
        if not _check_client_owns_vcoo(db, client_email, vcoo_id):
            raise HTTPException(status_code=403, detail="not your VCOO")
    st = crud.get_onboarding_state(db, vcoo_id)
    if not st:
        raise HTTPException(status_code=404, detail="no onboarding state")
    if st.step in ("finalize", "done"):
        return {"status": "already_done", "step": st.step}
    crud.advance_onboarding_step(db, vcoo_id, st.step)
    return {"status": "advanced", "step": st.step}


@application.post("/setup/{identifier}/start-pair-whatsapp")
def setup_start_pair_whatsapp(identifier: str, payload: dict = {}, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Enqueue a pair-whatsapp command for the agent. Payload can contain {phone: '+1234567890'} for pairing code mode."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="auth required")
    token_payload = auth.verify_client_token(authorization.split(None, 1)[1])
    if not token_payload:
        raise HTTPException(status_code=401, detail="invalid token")
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(status_code=400, detail="invalid identifier")
    vcoo_id = str(v.id)
    is_operator = token_payload.get('role') == 'operador'
    if not is_operator:
        client_email = token_payload.get("email", "")
        if not _check_client_owns_vcoo(db, client_email, vcoo_id):
            raise HTTPException(status_code=403, detail="not your VCOO")
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if not agent:
        raise HTTPException(status_code=400, detail="agent not installed yet")
    phone = (payload or {}).get("phone", "") if isinstance(payload, dict) else ""
    import json as _json
    cmd_payload = _json.dumps({"phone": phone}) if phone else ""
    cmd = crud.create_command(db, agent_id=str(agent.id), command="pair-whatsapp", result=cmd_payload)
    return {"status": "command_sent", "cmd_id": str(cmd.id), "mode": "pairing_code" if phone else "qr"}


@application.get("/setup/{identifier}/whatsapp-qr")
def setup_get_whatsapp_qr(identifier: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Return the latest WhatsApp QR code from the agent's command result."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="auth required")
    token_payload = auth.verify_client_token(authorization.split(None, 1)[1])
    if not token_payload:
        raise HTTPException(status_code=401, detail="invalid token")
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(status_code=400, detail="invalid identifier")
    vcoo_id = str(v.id)
    is_operator = token_payload.get('role') == 'operador'
    if not is_operator:
        client_email = token_payload.get("email", "")
        if not _check_client_owns_vcoo(db, client_email, vcoo_id):
            raise HTTPException(status_code=403, detail="not your VCOO")
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if not agent:
        return {"status": "no_agent"}
    # Find the latest pair-whatsapp command result
    cmd = db.query(models.Command).filter(
        models.Command.agent_id == agent.id,
        models.Command.command == "pair-whatsapp",
    ).order_by(models.Command.created_at.desc()).first()
    if not cmd:
        return {"status": "no_command"}
    if cmd.status == "pending":
        return {"status": "pending"}
    if cmd.status == "done":
        import json as _json
        try:
            result = _json.loads(cmd.result) if cmd.result else {}
            if isinstance(result, dict):
                mode = result.get("mode", "qr")
                output = result.get("output", "")
                if mode == "pairing_code":
                    return {"status": "pairing_code", "code": output, "phone": result.get("phone", "")}
                return {"status": "qr", "qr": output}
            return {"status": "qr", "qr": cmd.result or ""}
        except Exception:
            return {"status": "qr", "qr": cmd.result or ""}
    return {"status": cmd.status, "result": cmd.result}


# ── VCOO Logs ────────────────────────────────────────────

@application.get("/vcoo/{vcoo_id}/audit")
def get_vcoo_audit(vcoo_id: str, db: Session = Depends(get_db),
                   operator: dict = Depends(auth.verify_operator_jwt)):
    """Return audit log entries for a VCOO."""
    logs = crud.get_audit_log_for_vcoo(db, vcoo_id)
    return {
        "audit_log": [
            {
                "id": str(log.id),
                "action": log.action,
                "actor_email": log.actor_email,
                "actor_id": log.actor_id,
                "metadata": json.loads(log.log_metadata) if log.log_metadata else None,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    }


@application.get("/vcoo/{vcoo_id}/logs")
def get_vcoo_logs(vcoo_id: str, db: Session = Depends(get_db),
                  operator: dict = Depends(auth.verify_operator_jwt)):
    """Retrieve all command logs for a VCOO (across all its agents)."""
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if not agent:
        return {"commands": []}
    commands = crud.get_agent_commands(db, str(agent.id), limit=50)
    result = []
    for cmd in commands:
        logs = crud.get_command_logs(db, str(cmd.id))
        result.append({
            "cmd_id": str(cmd.id),
            "command": cmd.command,
            "step": cmd.step,
            "status": cmd.status,
            "result": (cmd.result or "")[:2000],
            "logs": logs[-100:] if logs else [],
        })
    return {"commands": result}


# ── Agent heartbeat (SPEC v2 §4.6) ───────────────────────

@application.post("/agent/heartbeat")
def agent_heartbeat_endpoint(payload: dict, db: Session = Depends(get_db)):
    agent_id = payload.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id missing")
    crud.agent_heartbeat(db, agent_id)
    return {"ack": True}


# ── Agent health report ────────────────────────────────────

@application.post("/agent/{agent_id}/health")
def agent_health_report(agent_id: str, payload: dict = {}, db: Session = Depends(get_db)):
    """Receive health ping from agent's health reporter.
    Stores health data (hostname, uptime, disk, hermes_running).
    """
    try:
        ok = crud.update_agent_health(db, agent_id, payload)
        if not ok:
            raise HTTPException(status_code=404, detail="agent not found")
        # Store version info if reported
        if payload.get("template_version") or payload.get("supervisor_version"):
            crud.update_agent_version(db, agent_id,
                template_version=payload.get("template_version"),
                supervisor_version=payload.get("supervisor_version"))
        return {"status": "ok", "agent_id": agent_id}
    except HTTPException:
        raise
    except Exception as e:
        import sys as _sys
        print(f"[health] Error for agent {agent_id}: {e}", file=_sys.stderr)
        raise HTTPException(status_code=404, detail="agent not found")


# ── Agent capabilities ────────────────────────────────────

@application.post("/agent/{agent_id}/capabilities")
def agent_capabilities_endpoint(agent_id: str, payload: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Receive agent's reported capabilities (hermes_version, providers, etc.)."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="missing auth")
    token = authorization.split(None, 1)[1]
    token_payload = auth.decode_agent_token(token)
    if not token_payload or token_payload.get('agent_id') != agent_id:
        raise HTTPException(status_code=401, detail="invalid agent token")
    agent = crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    crud.set_agent_capabilities(db, agent_id, payload)
    crud.touch_agent(db, agent_id)
    return {"status": "ok"}


# ── Agent tick (unified health + command poll) ─────────────

@application.post("/agent/{agent_id}/tick")
def agent_tick(agent_id: str, body: schemas.TickRequest, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Unified tick: agent sends health + last_command_id, receives commands + tick_interval."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing auth")
    token = authorization.split(None, 1)[1]
    token_payload = auth.decode_agent_token(token)
    if not token_payload or token_payload.get('agent_id') != agent_id:
        raise HTTPException(status_code=401, detail="invalid agent token")

    agent = crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")

    if body.health:
        agent.last_seen = datetime.utcnow()
        agent.health_payload = json.dumps(body.health.model_dump())
        db.commit()

    if body.last_command_id:
        crud.acknowledge_command(db, body.last_command_id)

    pending = crud.get_pending_commands(db, agent_id, body.last_command_id)
    cmd_dicts = []
    for cmd in pending:
        if cmd.command not in _VALID_AGENT_COMMANDS:
            crud.mark_command_done(db, cmd.id, result="BLOCKED: comando no reconocido, descartado")
            continue
        entry = {"cmd_id": str(cmd.id), "command": cmd.command, "step": cmd.step}
        if cmd.command in ("save-creds", "set-provider", "pair-whatsapp") and cmd.result:
            try:
                entry["payload"] = json.loads(cmd.result)
            except Exception:
                entry["payload"] = {"raw": cmd.result}
        cmd_dicts.append(entry)
        crud.mark_command_sent(db, cmd.id)

    has_commands = len(cmd_dicts) > 0
    tick_interval = 5 if has_commands else 0  # 0 = let agent use its own interval

    vcoo = crud.get_vcoo_by_agent(db, agent_id)
    progress = crud.get_tick_progress(db, str(vcoo.id)) if vcoo else None
    step = None
    if vcoo:
        st = crud.get_onboarding_state(db, str(vcoo.id))
        if st:
            step = st.step

    return schemas.TickResponse(
        commands=cmd_dicts,
        tick_interval=tick_interval,
        step=step,
        progress=progress,
    )


# ── VCOO Secrets (for installer) ───────────────────────────

@application.get("/vcoo/{vcoo_id}/secrets")
def get_vcoo_secrets_endpoint(vcoo_id: str, db: Session = Depends(get_db)):
    """Return stored secrets for installer to configure .env.
    Used by the unified one-liner install.sh after agent registration.
    """
    try:
        v = crud.get_vcoo(db, vcoo_id)
        if not v:
            raise HTTPException(status_code=404, detail="VCOO not found")
        secrets = crud.get_vcoo_secrets(db, vcoo_id)
        return secrets
    except HTTPException:
        raise
    except Exception as e:
        import sys as _sys
        print(f"[secrets] Error for vcoo {vcoo_id}: {e}", file=_sys.stderr)
        raise HTTPException(status_code=404, detail="VCOO not found")


# ── Onboarding management (operator actions) ─────────────

@application.post("/vcoo/{vcoo_id}/onboarding/retry")
def retry_onboarding_step(vcoo_id: str, payload: dict, db: Session = Depends(get_db),
                          operator: dict = Depends(auth.verify_operator_jwt)):
    """Operator manually retries a blocked/failed step."""
    step = payload.get("step")
    if not step:
        raise HTTPException(status_code=400, detail="step missing")
    st = crud.reset_onboarding_retry(db, vcoo_id, step)
    if not st:
        raise HTTPException(status_code=404, detail="Not found")
    # Re-enqueue the verification command
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if agent:
        from onboarding import get_step_command
        cmd_name = get_step_command(step)
        crud.create_command(db, agent_id=str(agent.id), command=cmd_name, step=step)
    crud.create_audit_log(db, action="onboarding.retry", actor_email=operator.get('email'),
                          actor_id=operator.get('operator_id'), vcoo_id=vcoo_id, metadata={"step": step})
    return {"status": "ok", "step": step, "onboarding_status": st.status}


@application.post("/vcoo/{vcoo_id}/onboarding/skip")
def skip_onboarding_step(vcoo_id: str, payload: dict, db: Session = Depends(get_db),
                         operator: dict = Depends(auth.verify_operator_jwt)):
    """Operator skips a blocked/impossible step."""
    step = payload.get("step")
    if not step:
        raise HTTPException(status_code=400, detail="step missing")
    st = crud.skip_onboarding_step(db, vcoo_id, step)
    if not st:
        raise HTTPException(status_code=404, detail="Not found")
    crud.create_audit_log(db, action="onboarding.skip", actor_email=operator.get('email'),
                          actor_id=operator.get('operator_id'), vcoo_id=vcoo_id, metadata={"step": step, "next": st.step})
    return {"status": "ok", "step": step, "next_step": st.step}


# ── Playbooks ──────────────────────────────────────────────

_PLAYBOOKS_DIR = _os.path.join(_os.path.dirname(__file__), 'playbooks')

@application.get('/playbooks')
def list_playbooks():
    if not _os.path.isdir(_PLAYBOOKS_DIR):
        return {'playbooks': []}
    names = sorted(
        f for f in _os.listdir(_PLAYBOOKS_DIR)
        if _os.path.isfile(_os.path.join(_PLAYBOOKS_DIR, f)) and not f.startswith('.')
    )
    return {'playbooks': names}

@application.get('/playbooks/{name}')
def get_playbook(name: str):
    safe_name = _os.path.basename(name)
    path = _os.path.join(_PLAYBOOKS_DIR, safe_name)
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Playbook not found')
    content = _safe_read_file(path)
    return {'name': safe_name, 'script': content}

@application.get('/playbooks/{name}/raw')
def get_playbook_raw(name: str):
    """Returns raw script content (for curl downloads from install.sh).
    Accepts optional Authorization header (provision token) to gate access."""
    safe_name = _os.path.basename(name)
    path = _os.path.join(_PLAYBOOKS_DIR, safe_name)
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Playbook not found')
    content = _safe_read_file(path)
    return PlainTextResponse(content, media_type='text/x-python')

@application.get('/setup/{identifier}/playbooks/{name}')
def get_vcoo_playbook(identifier: str, name: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Returns a playbook for a VCOO, authenticated via provision token."""
    if not authorization:
        raise HTTPException(status_code=401, detail='auth required')
    bearer = authorization.split(None, 1)[1]
    vcoo_id = crud.validate_provision_token(db, bearer)
    if not vcoo_id or str(vcoo_id) != identifier:
        raise HTTPException(status_code=403, detail='invalid token')
    from fastapi.responses import PlainTextResponse
    safe_name = _os.path.basename(name)
    path = _os.path.join(_PLAYBOOKS_DIR, safe_name)
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Playbook not found')
    content = _safe_read_file(path)
    return PlainTextResponse(content, media_type='text/x-python')


# ── Static assets ─────────────────────────────────────────

_STATIC_DIR = _os.path.join(_os.path.dirname(__file__))

@application.get('/install.sh')
def get_install_script():
    path = _os.path.join(_STATIC_DIR, 'install.sh')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    content = _safe_read_file(path)
    # Inyectar CONTROL_PLANE real y fix para HOME unbound
    control_plane_url = _url('CONTROL_PLANE', vercel_default=_CONTROL_PLANE_PROD, local_default='http://localhost:8000')
    lines = content.split('\n')
    home_fix = '\n# Fix HOME unbound (systemd) - inyectado por backend\n'
    home_fix += 'export HOME="${HOME:-/root}"\n'
    for i, line in enumerate(lines):
        if line.startswith('CONTROL_PLANE='):
            lines[i] = f'CONTROL_PLANE="{control_plane_url}"'
            if 'export HOME' not in content:
                lines.insert(i, home_fix)
            break
    content = '\n'.join(lines)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content, media_type='text/x-sh')

@application.get('/agent_http.py')
def get_agent_script():
    path = _os.path.join(_STATIC_DIR, 'agent_http.py')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(open(path).read(), media_type='text/x-python')

@application.get('/template.tar.gz')
def get_template_tar():
    path = _os.path.join(_STATIC_DIR, 'template.tar.gz')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type='application/gzip')

@application.get('/crypto.py')
def get_crypto_module():
    path = _os.path.join(_STATIC_DIR, 'crypto.py')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(open(path).read(), media_type='text/x-python')


@application.get("/admin/vcoo/{vcoo_id}/debug")
def admin_vcoo_debug(vcoo_id: str, token_payload: dict = Depends(auth.verify_operator_jwt), db: Session = Depends(get_db)):
    """Operator-only: raw VCOO state for debugging onboarding issues."""

    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="vcoo not found")

    state = crud.get_onboarding_state(db, str(v.id))
    agent = crud.get_agent_by_vcoo(db, str(v.id))

    result: dict[str, Any] = {
        "vcoo_id": str(v.id),
        "vcoo_name": v.name,
        "created_at": str(v.created_at) if v.created_at else None,
    }

    if state:
        result["onboarding"] = {
            "step": state.step,
            "status": state.status,
            "completed": state.completed or [],
            "errors": state.errors or {},
            "retry_count": state.retry_count or {},
        }

    if agent:
        caps = {}
        if agent.capabilities:
            try:
                caps = json.loads(agent.capabilities)
            except Exception:
                caps = {"parse_error": True}

        last_seen_ago = None
        if agent.last_seen:
            import datetime as dt
            last_seen_ago = (dt.datetime.utcnow() - agent.last_seen.replace(tzinfo=None)).total_seconds()

        pending_cmds = []
        try:
            pending_cmds = [
                {"id": str(c.id), "command": c.command, "created_at": str(c.created_at)}
                for c in db.query(models.Command)
                    .filter(models.Command.agent_id == agent.id, models.Command.status == "pending")
                    .all()
            ]
        except Exception:
            pass

        result["agent"] = {
            "id": str(agent.id),
            "online": last_seen_ago is not None and last_seen_ago < 120,
            "last_seen_seconds_ago": last_seen_ago,
            "has_encryption_key": bool(agent.encryption_key),
            "capabilities_summary": {
                "providers_count": len(caps.get("providers", [])),
                "models_keys": list(caps.get("models", {}).keys()),
                "checks": caps.get("checks", {}),
                "current_provider": caps.get("current_provider"),
            },
            "pending_commands": pending_cmds,
        }

    return result
