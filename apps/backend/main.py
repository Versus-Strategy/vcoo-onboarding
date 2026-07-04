import sys, os as _os
_sys_path = _os.path.dirname(__file__)
if _sys_path not in sys.path:
    sys.path.insert(0, _sys_path)

from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session
import db
from db import engine, Base, SessionLocal
import models, crud, auth, schemas
from ws_routes import register_ws_routes
import asyncio
import json
import os as _os




app = FastAPI(title="VCOO Onboarding API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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

@app.on_event("startup")
async def startup():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        import sys as _sys
        print(f"[startup] create_all skipped (DB unreachable): {e}", file=_sys.stderr)
    # ── Schema migrations (add columns that create_all won't add) ──
    try:
        from sqlalchemy import text as _sql_text
        with engine.connect() as conn:
            # Check if health_payload column exists in agents table
            result = conn.execute(_sql_text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='agents' AND column_name='health_payload'
            """))
            if not result.fetchone():
                conn.execute(_sql_text(
                    "ALTER TABLE agents ADD COLUMN health_payload TEXT"
                ))
                conn.commit()
                print("[migration] Added health_payload column to agents table")
            # Check if capabilities column exists
            result = conn.execute(_sql_text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='agents' AND column_name='capabilities'
            """))
            if not result.fetchone():
                conn.execute(_sql_text(
                    "ALTER TABLE agents ADD COLUMN capabilities TEXT"
                ))
                conn.commit()
                print("[migration] Added capabilities column to agents table")
    except Exception as e:
        import sys as _sys
        print(f"[migration] Skipped (non-critical): {e}", file=_sys.stderr)
    if _os.getenv("VERCEL_ENV") is None:
        register_ws_routes(app)


# ── Health / Debug ────────────────────────────────────────────

@app.get('/healthz')
def healthz():
    return {"status": "ok", "version": "v2", "python": sys.version.split()[0]}


# ── OAuth callback ────────────────────────────────────────────


@app.post("/auth/verify")
def verify_auth(payload: dict):
    password = payload.get("password", "")
    if auth.verify_dashboard_password(password):
        return {"status": "ok"}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")


@app.post("/auth/login")
def operator_login(payload: schemas.LoginRequest):
    """Operator login endpoint. Validates against DASHBOARD_PASSWORD and returns a JWT."""
    if not auth.verify_dashboard_password(payload.password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    # Derive a display name from the email (part before @)
    name = payload.email.split('@')[0]
    token = auth.create_operator_token(payload.email, name)
    return schemas.LoginResponse(
        token=token,
        user={"email": payload.email, "role": "operador", "name": name}
    )


# ── Client auth ──────────────────────────────────────────────

@app.post("/auth/client/register")
def client_register(payload: schemas.ClientRegisterRequest, db: Session = Depends(get_db)):
    """Register a new client linked to a VCOO via a provision token."""
    # 1. Validate the provision token (read-only, don't consume)
    vcoo_id = crud.lookup_provision_token(db, payload.token)
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


@app.post("/auth/client/login")
def client_login(payload: schemas.ClientLoginRequest, db: Session = Depends(get_db)):
    """Login for existing clients."""
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


@app.get("/auth/client/me")
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
@app.post("/vcoo")
def create_vcoo(payload: dict = {}, db: Session = Depends(get_db)):
    name = payload.get("name") if payload else None
    modules = payload.get("modules", ["core"]) if payload else ["core"]
    vcoo = crud.create_vcoo(db, name=name)
    # Create onboarding state with selected modules
    crud.get_or_create_onboarding_state(db, str(vcoo.id), modules)
    # Generate provision token
    token = crud.create_provision_for_vcoo(db, str(vcoo.id))
    frontend_url = _os.getenv('FRONTEND_URL', 'https://vcoo-dashboard.vercel.app')
    onboarding_url = frontend_url.rstrip('/') + '/setup/' + str(vcoo.id)
    return {
        "id": str(vcoo.id),
        "name": vcoo.name,
        "status": vcoo.status,
        "modules": modules,
        "onboarding_url": onboarding_url,
    }

@app.get("/vcoos")
def list_vcoos(db: Session = Depends(get_db)):
    """List all VCOOs with agent status and active token."""
    vcoos = crud.list_vcoos(db)
    dashboard_url = _os.getenv('DASHBOARD_URL', 'https://vcoo-dashboard.vercel.app')
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

@app.get("/setup/{identifier}")
def get_setup_info(identifier: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Returns onboarding state for the wizard frontend.
    Accepts VCOO UUID (preferred) or legacy JWT provision token as {identifier}.
    Handles 3 cases:
    1. No auth → {requires_registration: true, token_valid, vcoo_name}
    2. Auth but client doesn't own this VCOO → {requires_registration: false, ...state}
    3. Auth and owns it → full onboarding state (existing behavior)
    Read-only — does not consume the token."""
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "token_invalid",
                "message": "El enlace de invitación ha caducado o es inválido. Por favor, solicite un nuevo enlace en el panel de control.",
                "action": "solicitar_nuevo_enlace"
            }
        )
    vcoo_id = str(v.id)

    # Determine auth state
    client_payload = None
    if authorization and authorization.lower().startswith('bearer '):
        bearer_token = authorization.split(None, 1)[1]
        client_payload = auth.verify_client_token(bearer_token)

    if not client_payload:
        # Case 1: No auth — tell frontend to show registration form
        return {
            "requires_registration": True,
            "token_valid": True,
            "vcoo_name": v.name,
        }

    # Has auth — check if this client owns the VCOO
    client_email = client_payload.get("email", "")
    client_obj = crud.get_client_by_email(db, client_email)
    owns_vcoo = client_obj and client_obj.vcoo_id and str(client_obj.vcoo_id) == vcoo_id

    if not owns_vcoo:
        # Case 2: Auth but doesn't own this VCOO
        st = crud.get_onboarding_state(db, vcoo_id)
        from onboarding import get_total_steps
        modules = list(st.modules or ["core"]) if st else ["core"]
        return {
            "requires_registration": False,
            "token_valid": True,
            "vcoo_name": v.name,
            "vcoo_id": str(v.id),
            "modules": modules,
            "step": st.step if st else "unknown",
            "status": st.status if st else "unknown",
            "completed": st.completed or [] if st else [],
            "errors": st.errors or [] if st else [],
            "retry_count": st.retry_count or {} if st else {},
            "progress": {
                "total": get_total_steps(modules),
                "done": len(st.completed or []) if st else 0,
            },
        }

    # Case 3: Auth and owns it — full onboarding state (existing behavior)
    st = crud.get_onboarding_state(db, vcoo_id)
    if not st:
        raise HTTPException(status_code=404, detail="No hay datos de onboarding")
    from onboarding import get_total_steps
    modules = list(st.modules or ["core"])
    total = get_total_steps(modules)
    done = len(st.completed or [])
    control_plane = _os.getenv('CONTROL_PLANE', 'https://vcoo-onboarding.vercel.app')
    active_token_obj = crud.get_active_token_for_vcoo(db, vcoo_id)
    raw_token = active_token_obj.token if active_token_obj else ''
    install_cmd = f"curl -sSL {control_plane}/install.sh | CONTROL_PLANE={control_plane} PROVISION_TOKEN={raw_token} bash -"
    # Check if agent is online
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    agent_online = False
    if agent and agent.last_seen:
        import datetime as dt
        ago = (dt.datetime.utcnow() - agent.last_seen.replace(tzinfo=None)).total_seconds()
        agent_online = ago < 120
    return {
        "requires_registration": False,
        "vcoo_id": str(v.id),
        "name": v.name,
        "modules": modules,
        "step": st.step,
        "status": st.status,
        "completed": st.completed or [],
        "errors": st.errors or [],
        "retry_count": st.retry_count or {},
        "progress": {"total": total, "done": done},
        "install_command": install_cmd,
        "agent_online": agent_online,
    }


@app.post("/setup/{identifier}/verify")
def trigger_step_verification(identifier: str, db: Session = Depends(get_db)):
    """Client clicks 'Verificar' in the wizard — enqueues the verification command.
    If no agent is connected, auto-advances the step for dev/demo mode."""
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "token_invalid",
                "message": "El enlace de invitación ha caducado o es inválido. Por favor, solicite un nuevo enlace en el panel de control.",
                "action": "solicitar_nuevo_enlace"
            }
        )
    vcoo_id = str(v.id)
    st = crud.get_onboarding_state(db, vcoo_id)
    if not st:
        raise HTTPException(status_code=404, detail="No hay datos de onboarding")
    from onboarding import get_step_command
    step = st.step
    if step == "finalize" or step == "done":
        return {"status": "skip", "message": "Onboarding ya completado"}
    cmd_name = get_step_command(step)

    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    # Check if agent is active (seen within last 2 minutes)
    agent_alive = False
    if agent and agent.last_seen:
        import datetime as dt
        ago = (dt.datetime.utcnow() - agent.last_seen.replace(tzinfo=None)).total_seconds()
        agent_alive = ago < 120

    if agent and agent_alive:
        # Real agent connected — enqueue the command
        cmd = crud.create_command(db, agent_id=str(agent.id), command=cmd_name, step=step)
        return {
            "status": "enqueued",
            "cmd_id": str(cmd.id),
            "step": step,
            "command": cmd_name,
        }
    else:
        # Dev/demo mode — auto-advance the step
        crud.advance_onboarding_step(db, vcoo_id, step)
        db.refresh(st)
        return {
            "status": "auto_completed",
            "step": step,
            "next_step": st.step,
            "message": "Paso completado automaticamente (modo demo). En produccion, el agente ejecutara la verificacion real.",
        }


# ── Auth URL generation (dynamic OAuth tabs) ────────────

@ app.get("/setup/{identifier}/auth-url")
def get_auth_url(identifier: str, service: str = "", db: Session = Depends(get_db)):
    """Generates an OAuth authorization URL for the given service."""
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "token_invalid",
                "message": "El enlace de invitación ha caducado o es inválido. Por favor, solicite un nuevo enlace en el panel de control.",
                "action": "solicitar_nuevo_enlace"
            }
        )
    vcoo_id = str(v.id)
    service = service.lower().strip()
    if service == "google":
        client_id = _os.getenv("GOOGLE_CLIENT_ID", "")
        # Google strips extra query params from redirect_uri — encode service in state
        redirect = _os.getenv("GOOGLE_REDIRECT_URI", "https://vcoo-onboarding.vercel.app/auth/callback")
        state = f"{vcoo_id}:google"
        if not client_id:
            url = "https://accounts.google.com/o/oauth2/v2/auth?client_id=vcoo-dev&redirect_uri={}&response_type=code&scope=https://www.googleapis.com/auth/drive.readonly+https://www.googleapis.com/auth/gmail.readonly&access_type=offline&prompt=consent&state={}".format(redirect, state)
        else:
            url = "https://accounts.google.com/o/oauth2/v2/auth?client_id={}&redirect_uri={}&response_type=code&scope=https://www.googleapis.com/auth/drive.readonly+https://www.googleapis.com/auth/gmail.readonly&access_type=offline&prompt=consent&state={}".format(client_id, redirect, state)
        return {"url": url, "service": "google"}
    elif service == "trello":
        api_key = _os.getenv("TRELLO_API_KEY", "vcoo-dev-key")
        url = "https://trello.com/1/authorize?expiration=never&name=VCOO&scope=read,write&response_type=token&key={}&return_url={}".format(api_key, "https://vcoo-onboarding.vercel.app/auth/callback?service=trello")
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

@app.get("/auth/callback")
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
        redirect_uri = _os.getenv("GOOGLE_REDIRECT_URI", "https://vcoo-onboarding.vercel.app/auth/callback")
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
                    print(f"[oauth] Google token exchange OK, access_token={access_token[:20]}...", file=sys.stderr)
            except Exception as e:
                print(f"[oauth] Token exchange failed: {e}", file=sys.stderr)
                # Continue — store the code as fallback so the agent can retry

    # Map service to the correct onboarding step and advance it NOW
    step_map = {"google": "google-oauth", "trello": "trello-setup"}
    mapped_step = step_map.get(service, "save-creds")

    # Advance onboarding step immediately (don't wait for agent)
    if vcoo_id:
        try:
            crud.advance_onboarding_step(db, vcoo_id, mapped_step)
            # Google OAuth includes gmail scope — also complete gmail-setup if mail module is active
            if service == "google":
                st = crud.get_onboarding_state(db, vcoo_id)
                if st and "mail" in (st.modules or []) and "gmail-setup" not in (st.completed or []):
                    crud.advance_onboarding_step(db, vcoo_id, "gmail-setup")
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
        }
        crud.create_command(
            db, agent_id=str(agent.id), command="save-creds", step=mapped_step,
            result=json.dumps(creds_data),
        )

    return HTMLResponse(
        "<html><body style=\"background:#0a0a0f;color:#e2e8f0;font-family:sans-serif;text-align:center;padding:60px\">"
        "<h1 style=\"color:#533afd\">Autorizacion recibida</h1>"
        "<p>Vuelve al wizard para continuar.</p>"
        "<script>setTimeout(function(){window.close()},3000)</script></body></html>"
    )


# ── Hermes CLI commands (dynamic) ──────────────────────

@ app.get("/setup/{identifier}/hermes-commands")
def get_hermes_commands_endpoint(identifier: str, service: str = "", db: Session = Depends(get_db)):
    """Returns Hermes CLI config commands for a service."""
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "token_invalid",
                "message": "El enlace de invitación ha caducado o es inválido. Por favor, solicite un nuevo enlace en el panel de control.",
                "action": "solicitar_nuevo_enlace"
            }
        )
    vcoo_id = str(v.id)
    service = service.lower().strip()
    commands_map = {
        "google": ["hermes config set google.client_id TU_CLIENT_ID", "hermes config set google.client_secret TU_CLIENT_SECRET"],
        "trello": ["hermes config set trello.api_key TU_API_KEY", "hermes config set trello.api_token TU_TOKEN"],
        "github": ["gh auth login", "hermes config set github.token $(gh auth token)"],
        "vercel": ["vercel login", "hermes config set vercel.token TU_TOKEN"],
        "supabase": ["supabase login", "hermes config set supabase.access_token TU_ACCESS_TOKEN"],
        "opencode": ["hermes config set model.provider opencode", "hermes config set model.default opencode/claude-sonnet-4"],
        "anthropic": ["export ANTHROPIC_API_KEY=sk-ant-tu-clave", "hermes config set model.provider anthropic"],
        "openai": ["export OPENAI_API_KEY=sk-tu-clave", "hermes config set model.provider openai"],
    }
    return {"commands": commands_map.get(service, []), "service": service}


@app.get("/vcoo/{vcoo_id}/provision-token")
def get_provision_token(vcoo_id: str, db: Session = Depends(get_db)):
    """Return existing active token for this VCOO, or create one if none exists."""
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    active = crud.get_active_token_for_vcoo(db, vcoo_id)
    if active:
        token = active.token
    else:
        token = crud.create_provision_for_vcoo(db, vcoo_id)
    dashboard_url = _os.getenv('DASHBOARD_URL', 'https://vcoo-dashboard.vercel.app')
    control_plane = _os.getenv('CONTROL_PLANE', 'https://vcoo-onboarding.vercel.app')
    install_cmd = f"curl -sSL {control_plane}/install.sh | PROVISION_TOKEN={token} bash -"
    onboarding_url = f"{dashboard_url}/setup/{vcoo_id}"
    return {"token": token, "install_command": install_cmd, "onboarding_url": onboarding_url}

@app.post("/vcoo/{vcoo_id}/regenerate-token")
def regenerate_token(vcoo_id: str, db: Session = Depends(get_db)):
    """Revoke current token and generate a new one."""
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    token = crud.regenerate_token_for_vcoo(db, vcoo_id)
    dashboard_url = _os.getenv('DASHBOARD_URL', 'https://vcoo-dashboard.vercel.app')
    control_plane = _os.getenv('CONTROL_PLANE', 'https://vcoo-onboarding.vercel.app')
    install_cmd = f"curl -sSL {control_plane}/install.sh | PROVISION_TOKEN={token} bash -"
    onboarding_url = f"{dashboard_url}/setup/{vcoo_id}"
    return {"token": token, "install_command": install_cmd, "onboarding_url": onboarding_url}

@app.post("/vcoo/{vcoo_id}/complete")
def complete_vcoo(vcoo_id: str, db: Session = Depends(get_db)):
    """Mark VCOO as completed (setup finished). Logs are preserved."""
    v = crud.complete_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="VCOO not found")
    return {"status": "completed"}

@app.post("/vcoo/{vcoo_id}/reactivate")
def reactivate_vcoo(vcoo_id: str, db: Session = Depends(get_db)):
    """Reactivate a completed VCOO and generate a new token."""
    token = crud.reactivate_vcoo(db, vcoo_id)
    if not token:
        raise HTTPException(status_code=404, detail="VCOO not found")
    control_plane = _os.getenv('CONTROL_PLANE', 'https://vcoo-onboarding.vercel.app')
    install_cmd = f"curl -sSL {control_plane}/install.sh | PROVISION_TOKEN={token} bash -"
    return {"status": "active", "token": token, "install_command": install_cmd}

@app.delete("/vcoo/{vcoo_id}")
def delete_vcoo(vcoo_id: str, db: Session = Depends(get_db)):
    """Permanently delete a VCOO and all associated data."""
    ok = crud.delete_vcoo(db, vcoo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="VCOO not found")
    return {"status": "deleted"}


# ── Agent registration & auth ─────────────────────────────

@app.post("/register")
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

    return {"agent_id": str(agent.id), "vcoo_id": str(vcoo_id), "agent_token": agent_token, "encryption_key": enc_key}


# ── Agent polling & logs ──────────────────────────────────

@app.get("/agent/{agent_id}/poll")
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
    # Solo servir comandos validos del COMMAND_MAP
    VALID_COMMANDS = {
        "verify-bootstrap", "verify-google", "verify-trello", "verify-email",
        "verify-github", "verify-vercel", "verify-supabase",
        "save-creds", "finalize", "set-provider",
    }
    result = []
    for cmd in pending:
        if cmd.command not in VALID_COMMANDS:
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
            from onboarding import get_agent_total_steps
            modules = list(st.modules or ["core"])
            progress_data = {
                "done": len([s for s in (st.completed or []) if onboarding.has_agent_command(s)]),
                "total": get_agent_total_steps(modules),
            }
    return {
        "commands": result,
        "progress": progress_data,
        "step": st.step if st else "",
        "onboarding_status": st.status if st else "unknown",
    }

@app.post("/agent/{agent_id}/complete")
def agent_setup_complete(agent_id: str, db: Session = Depends(get_db)):
    """Agent calls this when onboarding setup finishes.
    Marks the VCOO as completed and revokes its token."""
    agent = crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    crud.complete_vcoo(db, str(agent.vcoo_id))
    return {"status": "ok", "vcoo_completed": True}

@app.post('/agent/{agent_id}/logs')
def agent_logs(agent_id: str, payload: dict, db: Session = Depends(get_db)):
    cmd_id = payload.get('cmd_id')
    chunk = payload.get('chunk', '')
    stream = payload.get('stream', 'stdout')
    if not cmd_id:
        raise HTTPException(status_code=400, detail='cmd_id missing')
    crud.append_command_log(db, cmd_id, chunk, stream)
    return {'status': 'ok'}

@app.get('/agent/{agent_id}/logs')
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

@app.post("/vcoo/{vcoo_id}/set-provider")
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

@app.post("/vcoo/{vcoo_id}/commands")
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

@app.post("/vcoo/{vcoo_id}/commands/{cmd_id}/result")
def command_result(vcoo_id: str, cmd_id: str, payload: dict, db: Session = Depends(get_db)):
    result = payload.get('result', '')
    crud.mark_command_done(db, cmd_id, result=result)
    return {"status": "ok"}


# ── State ─────────────────────────────────────────────────

@app.get("/vcoo/{vcoo_id}/state")
def get_state(vcoo_id: str, db: Session = Depends(get_db)):
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

@app.post("/agent/{agent_id}/result")
def agent_report_result(agent_id: str, payload: dict, db: Session = Depends(get_db)):
    """Agent reports command result. ACK semantics with backoff support."""
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


# ── VCOO Logs ────────────────────────────────────────────

@app.get("/vcoo/{vcoo_id}/logs")
def get_vcoo_logs(vcoo_id: str, db: Session = Depends(get_db)):
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

@app.post("/agent/heartbeat")
def agent_heartbeat_endpoint(payload: dict, db: Session = Depends(get_db)):
    agent_id = payload.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id missing")
    crud.agent_heartbeat(db, agent_id)
    return {"ack": True}


# ── Agent health report ────────────────────────────────────

@app.post("/agent/{agent_id}/health")
def agent_health_report(agent_id: str, payload: dict = {}, db: Session = Depends(get_db)):
    """Receive health ping from agent's health reporter.
    Stores health data (hostname, uptime, disk, hermes_running).
    """
    try:
        ok = crud.update_agent_health(db, agent_id, payload)
        if not ok:
            raise HTTPException(status_code=404, detail="agent not found")
        return {"status": "ok", "agent_id": agent_id}
    except HTTPException:
        raise
    except Exception as e:
        import sys as _sys
        print(f"[health] Error for agent {agent_id}: {e}", file=_sys.stderr)
        raise HTTPException(status_code=404, detail="agent not found")


# ── Agent capabilities ────────────────────────────────────

@app.post("/agent/{agent_id}/capabilities")
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


# ── VCOO Secrets (for installer) ───────────────────────────

@app.get("/vcoo/{vcoo_id}/secrets")
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

@app.post("/vcoo/{vcoo_id}/onboarding/retry")
def retry_onboarding_step(vcoo_id: str, payload: dict, db: Session = Depends(get_db)):
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
    return {"status": "ok", "step": step, "onboarding_status": st.status}


@app.post("/vcoo/{vcoo_id}/onboarding/skip")
def skip_onboarding_step(vcoo_id: str, payload: dict, db: Session = Depends(get_db)):
    """Operator skips a blocked/impossible step."""
    step = payload.get("step")
    if not step:
        raise HTTPException(status_code=400, detail="step missing")
    st = crud.skip_onboarding_step(db, vcoo_id, step)
    if not st:
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "ok", "step": step, "next_step": st.step}


# ── Playbooks ──────────────────────────────────────────────

_PLAYBOOKS_DIR = _os.path.join(_os.path.dirname(__file__), 'playbooks')

@app.get('/playbooks')
def list_playbooks():
    if not _os.path.isdir(_PLAYBOOKS_DIR):
        return {'playbooks': []}
    names = sorted(
        f for f in _os.listdir(_PLAYBOOKS_DIR)
        if _os.path.isfile(_os.path.join(_PLAYBOOKS_DIR, f)) and not f.startswith('.')
    )
    return {'playbooks': names}

@app.get('/playbooks/{name}')
def get_playbook(name: str):
    path = _os.path.join(_PLAYBOOKS_DIR, name)
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Playbook not found')
    content = open(path).read()
    return {'name': name, 'script': content}

@app.get('/playbooks/{name}/raw')
def get_playbook_raw(name: str):
    """Returns raw script content (for curl downloads from install.sh)."""
    from fastapi.responses import PlainTextResponse
    path = _os.path.join(_PLAYBOOKS_DIR, name)
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Playbook not found')
    content = open(path).read()
    return PlainTextResponse(content, media_type='text/x-python')


# ── Static assets ─────────────────────────────────────────

_STATIC_DIR = _os.path.join(_os.path.dirname(__file__))

@app.get('/install.sh')
def get_install_script():
    path = _os.path.join(_STATIC_DIR, 'install.sh')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    content = open(path).read()
    # Inyectar CONTROL_PLANE real y fix para HOME unbound
    control_plane_url = _os.getenv('CONTROL_PLANE', 'https://vcoo-onboarding.vercel.app')
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

@app.get('/agent_http.py')
def get_agent_script():
    path = _os.path.join(_STATIC_DIR, 'agent_http.py')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(open(path).read(), media_type='text/x-python')

@app.get('/template.tar.gz')
def get_template_tar():
    path = _os.path.join(_STATIC_DIR, 'template.tar.gz')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type='application/gzip')

@app.get('/crypto.py')
def get_crypto_module():
    path = _os.path.join(_STATIC_DIR, 'crypto.py')
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail='Not found')
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(open(path).read(), media_type='text/x-python')
