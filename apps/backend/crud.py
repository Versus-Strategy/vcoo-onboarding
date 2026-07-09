from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException
import models
from datetime import datetime, timedelta
import json


def create_vcoo(db: Session, name: str = None):
    v = models.VCOO(name=name, status='active')
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def get_vcoo(db: Session, vcoo_id: str):
    return db.query(models.VCOO).filter(models.VCOO.id == vcoo_id).first()


def list_vcoos(db: Session, limit: int = 50):
    """List VCOOs with their latest agent, active token y módulos.

    Evita el N+1 (antes: 1 + 3 consultas por VCOO): trae los agentes, tokens y
    estados de onboarding de toda la página en 3 consultas con IN y los asocia
    en memoria, preservando la semántica de "más reciente".
    """
    vcoos = (
        db.query(models.VCOO)
        .order_by(models.VCOO.created_at.desc())
        .limit(limit)
        .all()
    )
    if not vcoos:
        return vcoos

    ids = [str(v.id) for v in vcoos]
    now = datetime.utcnow()

    # Agente más reciente por vcoo (por last_seen). Orden ascendente para que,
    # al recorrer, el último asignado sea el más reciente.
    agents = (
        db.query(models.Agent)
        .filter(models.Agent.vcoo_id.in_(ids))
        .order_by(models.Agent.last_seen.asc())
        .all()
    )
    agent_by_vcoo: dict = {}
    for a in agents:
        agent_by_vcoo[str(a.vcoo_id)] = a

    # Token activo (no expirado) más reciente por vcoo (por created_at).
    tokens = (
        db.query(models.ProvisionToken)
        .filter(
            models.ProvisionToken.vcoo_id.in_(ids),
            models.ProvisionToken.expires_at > now,
        )
        .order_by(models.ProvisionToken.created_at.asc())
        .all()
    )
    token_by_vcoo: dict = {}
    for t in tokens:
        token_by_vcoo[str(t.vcoo_id)] = t

    # Estado de onboarding (uno por vcoo).
    states = (
        db.query(models.OnboardingState)
        .filter(models.OnboardingState.vcoo_id.in_(ids))
        .all()
    )
    state_by_vcoo = {str(s.vcoo_id): s for s in states}

    for v in vcoos:
        vid = str(v.id)
        v.agent = agent_by_vcoo.get(vid)
        v.active_token = token_by_vcoo.get(vid)
        st = state_by_vcoo.get(vid)
        v.modules = st.modules if st else ["core"]
    return vcoos


# ── VCOO lifecycle ───────────────────────────────────────

def complete_vcoo(db: Session, vcoo_id: str):
    """Mark VCOO as completed. Keeps tokens visible for reference."""
    v = get_vcoo(db, vcoo_id)
    if not v:
        return None
    v.status = 'completed'
    # Don't revoke tokens — keep them visible in dashboard
    db.commit()
    return v


def reactivate_vcoo(db: Session, vcoo_id: str):
    """Reactivate a completed VCOO and generate a new token."""
    v = get_vcoo(db, vcoo_id)
    if not v:
        return None
    v.status = 'active'
    db.commit()
    token = create_provision_for_vcoo(db, vcoo_id)
    return token


def delete_vcoo(db: Session, vcoo_id: str) -> bool:
    """Hard-delete a VCOO and all related records."""
    v = db.query(models.VCOO).filter(models.VCOO.id == vcoo_id).first()
    if not v:
        return False
    try:
        # Bind the id as a string: los modelos usan String(36) (compatible con
        # SQLite) y Postgres castea el texto a uuid automáticamente. Pasar un
        # objeto UUID rompe en SQLite ("type 'UUID' is not supported").
        vcoo_uuid = str(vcoo_id)

        # Use raw SQL to bypass ORM complexity
        db.execute(text("DELETE FROM command_logs WHERE command_id IN (SELECT id FROM commands WHERE agent_id IN (SELECT id FROM agents WHERE vcoo_id = :vid))"), {"vid": vcoo_uuid})
        db.execute(text("DELETE FROM commands WHERE agent_id IN (SELECT id FROM agents WHERE vcoo_id = :vid)"), {"vid": vcoo_uuid})
        db.execute(text("DELETE FROM agents WHERE vcoo_id = :vid"), {"vid": vcoo_uuid})
        db.execute(text("DELETE FROM provision_tokens WHERE vcoo_id = :vid"), {"vid": vcoo_uuid})
        db.execute(text("DELETE FROM onboarding_state WHERE vcoo_id = :vid"), {"vid": vcoo_uuid})
        db.execute(text("DELETE FROM clients WHERE vcoo_id = :vid"), {"vid": vcoo_uuid})
        db.execute(text("DELETE FROM vcoos WHERE id = :vid"), {"vid": vcoo_uuid})
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── Token management ─────────────────────────────────────

def get_active_token_for_vcoo(db: Session, vcoo_id: str):
    """Return the latest unexpired token for a VCOO, or None."""
    return (
        db.query(models.ProvisionToken)
        .filter(
            models.ProvisionToken.vcoo_id == vcoo_id,
            models.ProvisionToken.expires_at > datetime.utcnow(),
        )
        .order_by(models.ProvisionToken.created_at.desc())
        .first()
    )


def revoke_all_tokens_for_vcoo(db: Session, vcoo_id: str):
    """Mark all unused tokens for a VCOO as used."""
    db.query(models.ProvisionToken).filter(
        models.ProvisionToken.vcoo_id == vcoo_id,
        models.ProvisionToken.used == False,
    ).update({"used": True})
    db.commit()


def delete_token(db: Session, token_str: str) -> bool:
    """Mark a provision token as used (revoke it)."""
    pt = db.query(models.ProvisionToken).filter(
        models.ProvisionToken.token == token_str
    ).first()
    if not pt:
        return False
    pt.used = True
    db.commit()
    return True


def regenerate_token_for_vcoo(db: Session, vcoo_id: str):
    """Revoke current active token and create a new one."""
    revoke_all_tokens_for_vcoo(db, vcoo_id)
    return create_provision_for_vcoo(db, vcoo_id)


# ── Client CRUD ─────────────────────────────────────────────

def get_client_by_email(db: Session, email: str):
    """Find a client by email."""
    return db.query(models.Client).filter(models.Client.email == email).first()


def get_client_by_vcoo(db: Session, vcoo_id: str):
    """Find a client linked to a VCOO."""
    return db.query(models.Client).filter(models.Client.vcoo_id == vcoo_id).first()


def create_client(db: Session, email: str, password_hash: str, name: str = None, vcoo_id: str = None):
    """Create a new client."""
    c = models.Client(
        email=email,
        password_hash=password_hash,
        name=name,
        vcoo_id=vcoo_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def link_client_to_vcoo(db: Session, client_id: str, vcoo_id: str):
    """Link an existing client to a VCOO."""
    c = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not c:
        return None
    c.vcoo_id = vcoo_id
    db.commit()
    db.refresh(c)
    return c


# ── Operator CRUD ──────────────────────────────────────────

def create_operator(db: Session, email: str, password_hash: str, name: str = None):
    op = models.Operator(email=email, password_hash=password_hash, name=name)
    db.add(op)
    db.commit()
    db.refresh(op)
    return op


def get_operator_by_email(db: Session, email: str):
    return db.query(models.Operator).filter(models.Operator.email == email).first()


def get_operator_by_id(db: Session, operator_id: str):
    return db.query(models.Operator).filter(models.Operator.id == operator_id).first()


def count_operators(db: Session) -> int:
    return db.query(models.Operator).count()


# ── Agent CRUD ───────────────────────────────────────────

def create_agent(db: Session, vcoo_id: str, info: str = None, encryption_key: str = None):
    a = models.Agent(vcoo_id=vcoo_id, info=info, status='online', encryption_key=encryption_key)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def set_agent_token_jti(db: Session, agent_id: str, jti: str):
    db.query(models.Agent).filter(models.Agent.id == agent_id).update({"token_jti": jti})
    db.commit()


def set_agent_encryption_key(db: Session, agent_id: str, enc_key: str):
    db.query(models.Agent).filter(models.Agent.id == agent_id).update({"encryption_key": enc_key})
    db.commit()


def set_agent_capabilities(db: Session, agent_id: str, capabilities: dict):
    import json
    db.query(models.Agent).filter(models.Agent.id == agent_id).update(
        {"capabilities": json.dumps(capabilities)}
    )
    db.commit()


def get_agent_by_vcoo(db: Session, vcoo_id: str):
    return db.query(models.Agent).filter(
        models.Agent.vcoo_id == vcoo_id
    ).order_by(models.Agent.last_seen.desc()).first()


def get_agent(db: Session, agent_id: str):
    return db.query(models.Agent).filter(models.Agent.id == agent_id).first()


# ── Commands ─────────────────────────────────────────────

def create_command(db: Session, agent_id: str, command: str, step: str = None, result: str = None):
    c = models.Command(agent_id=agent_id, command=command, step=step, result=result)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def get_pending_commands(db: Session, agent_id: str, last_command_id: str | None = None):
    query = db.query(models.Command).filter(
        models.Command.agent_id == agent_id,
        models.Command.status == 'pending'
    )
    return query.order_by(models.Command.created_at).limit(10).all()


def acknowledge_command(db: Session, command_id: str) -> None:
    cmd = db.query(models.Command).filter(models.Command.id == command_id).first()
    if cmd:
        cmd.status = "acknowledged"
        db.commit()


def get_tick_progress(db: Session, vcoo_id: str) -> dict | None:
    st = get_onboarding_state(db, vcoo_id)
    if not st:
        return None
    from onboarding import get_total_steps
    total = get_total_steps(list(st.modules or ["core"]))
    done = len(st.completed or [])
    return {"total": total, "done": done}


def get_vcoo_by_agent(db: Session, agent_id: str):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if agent and agent.vcoo_id:
        return db.query(models.VCOO).filter(models.VCOO.id == agent.vcoo_id).first()
    return None


def mark_command_sent(db: Session, command_id: str):
    import datetime as dt
    db.query(models.Command).filter(models.Command.id == command_id).update(
        {"status": "sent", "sent_at": dt.datetime.utcnow()}
    )
    db.commit()


def mark_command_done(db: Session, command_id: str, result: str = ''):
    db.query(models.Command).filter(models.Command.id == command_id).update(
        {"status": "done", "result": result}
    )
    db.commit()


def touch_agent(db: Session, agent_id: str):
    import datetime as dt
    db.query(models.Agent).filter(models.Agent.id == agent_id).update(
        {"last_seen": dt.datetime.utcnow(), "status": "online"}
    )
    db.commit()


# ── Provision tokens ─────────────────────────────────────

def create_provision_for_vcoo(db: Session, vcoo_id: str, expires_minutes: int = 10080):  # 1 week
    import auth
    token = auth.create_provision_token(vcoo_id, expires_minutes)
    expires_at = datetime.utcnow() + timedelta(minutes=expires_minutes)
    pt = models.ProvisionToken(token=token, vcoo_id=vcoo_id, expires_at=expires_at)
    db.add(pt)
    db.commit()
    return token


def validate_provision_token(db: Session, token: str):
    """Validate a provision token and return its VCOO id.
    Tokens are not consumed — they remain valid until expiration."""
    pt = db.query(models.ProvisionToken).filter(models.ProvisionToken.token == token).first()
    if not pt:
        return None
    if pt.expires_at and pt.expires_at.replace(tzinfo=None) < datetime.utcnow():
        return None
    return str(pt.vcoo_id)


# ── Command logs ─────────────────────────────────────────

def append_command_log(db: Session, command_id: str, chunk: str, stream: str = 'stdout'):
    cl = models.CommandLog(command_id=command_id, chunk=chunk, stream=stream)
    db.add(cl)
    db.commit()
    return cl


def get_command_logs(db: Session, command_id: str) -> list[dict]:
    """Returns log chunks for a command, ordered by timestamp."""
    logs = db.query(models.CommandLog).filter(
        models.CommandLog.command_id == command_id
    ).order_by(models.CommandLog.id.asc()).all()
    return [{"chunk": l.chunk, "stream": l.stream} for l in logs]


def get_agent_commands(db: Session, agent_id: str, limit: int = 20):
    """Returns recent commands for an agent, newest first."""
    return db.query(models.Command).filter(
        models.Command.agent_id == agent_id
    ).order_by(models.Command.id.desc()).limit(limit).all()


# ── Onboarding State (SPEC v2 §3.2) ─────────────────────

def get_or_create_onboarding_state(
    db: Session, vcoo_id: str, modules: list[str] | None = None
):
    """Get existing onboarding state or create one."""
    st = db.query(models.OnboardingState).filter(
        models.OnboardingState.vcoo_id == vcoo_id
    ).first()
    if not st:
        st = models.OnboardingState(
            vcoo_id=vcoo_id,
            modules=modules or ["core"],
            step="bootstrap",
            status="in_progress",
            completed=[],
            errors=[],
            retry_count={},
        )
        db.add(st)
        db.commit()
        db.refresh(st)
    return st


def get_onboarding_state(db: Session, vcoo_id: str):
    return db.query(models.OnboardingState).filter(
        models.OnboardingState.vcoo_id == vcoo_id
    ).first()


def advance_onboarding_step(db: Session, vcoo_id: str, step_completed: str):
    """Mark a step as completed and advance to the next one."""
    st = get_onboarding_state(db, vcoo_id)
    if not st:
        return None
    completed: list = list(st.completed or [])
    if step_completed not in completed:
        completed.append(step_completed)
    st.completed = completed

    # Advance to next step
    from onboarding import get_next_step, get_steps_for_modules
    modules: list = list(st.modules or ["core"])
    next_step = get_next_step(completed, modules)
    if next_step:
        st.step = next_step
    else:
        st.step = "done"
        st.status = "completed"
    db.commit()
    db.refresh(st)
    return st


def add_onboarding_error(db: Session, vcoo_id: str, step: str, error_msg: str):
    """Record an error and increment retry count."""
    st = get_onboarding_state(db, vcoo_id)
    if not st:
        return None
    errors: list = list(st.errors or [])
    from datetime import datetime as dt
    errors.append({
        "step": step,
        "error": error_msg,
        "timestamp": dt.utcnow().isoformat(),
    })
    st.errors = errors

    retries: dict = dict(st.retry_count or {})
    retries[step] = retries.get(step, 0) + 1
    st.retry_count = retries

    # If >= 3 retries, block the step
    if retries[step] >= 3:
        st.status = "blocked"

    db.commit()
    db.refresh(st)
    return st


def reset_onboarding_retry(db: Session, vcoo_id: str, step: str):
    """Reset retry count for a step (operator manual retry)."""
    st = get_onboarding_state(db, vcoo_id)
    if not st:
        return None
    retries: dict = dict(st.retry_count or {})
    retries[step] = 0
    st.retry_count = retries
    if st.status == "blocked":
        st.status = "in_progress"
    # Remove errors for this step
    errors: list = list(st.errors or [])
    st.errors = [e for e in errors if e.get("step") != step]
    db.commit()
    db.refresh(st)
    return st


def skip_onboarding_step(db: Session, vcoo_id: str, step: str):
    """Operator skips a blocked/impossible step."""
    st = get_onboarding_state(db, vcoo_id)
    if not st:
        return None
    errors: list = list(st.errors or [])
    from datetime import datetime as dt
    errors.append({
        "step": step,
        "error": "Omitido por el operador",
        "skipped_by_operator": True,
        "timestamp": dt.utcnow().isoformat(),
    })
    st.errors = errors
    # Advance past it
    return advance_onboarding_step(db, vcoo_id, step)


# ── Agent heartbeat (SPEC v2 §4.6) ──────────────────────

def agent_heartbeat(db: Session, agent_id: str):
    """Update agent last_seen and status to online."""
    import datetime as dt
    db.query(models.Agent).filter(models.Agent.id == agent_id).update(
        {"last_seen": dt.datetime.utcnow(), "status": "online"}
    )
    db.commit()


def update_agent_health(db: Session, agent_id: str, payload: dict) -> bool:
    """Update agent health payload and last_seen timestamp."""
    import datetime as dt
    import json
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        return False
    agent.last_seen = dt.datetime.utcnow()
    agent.status = "online"
    agent.health_payload = json.dumps(payload)
    db.commit()
    return True


def get_vcoo_secrets(db: Session, vcoo_id: str) -> dict:
    """Return stored secrets for a VCOO (for the installer to configure .env)."""
    vcoo = db.query(models.VCOO).filter(models.VCOO.id == vcoo_id).first()
    if not vcoo:
        return {}
    secrets = {}
    if vcoo.integrations:
        try:
            secrets = json.loads(vcoo.integrations)
        except (json.JSONDecodeError, TypeError):
            pass
    return secrets


# ── Agent result (SPEC v2 §4.4) ─────────────────────────

def process_agent_result(
    db: Session, agent_id: str, cmd_id: str,
    step: str, status: str, output: str,
):
    """Process an agent command result with ACK semantics.
    Returns (cmd, acked, next_step, status_code).
    """
    cmd = db.query(models.Command).filter(models.Command.id == cmd_id).first()
    if not cmd:
        return None, False, None, 404  # comando no encontrado
    if cmd.acked:
        return cmd, True, None, 409   # ya reportado (idempotente)

    # Mark as done + acked
    cmd.status = "done"
    cmd.result = output
    cmd.acked = True
    db.commit()

    # Get agent's VCOO
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        return cmd, True, None, 201

    vcoo_id = str(agent.vcoo_id)

    if status == "ok":
        # Advance onboarding + auto-enqueue next step
        st = advance_onboarding_step(db, vcoo_id, step)
        if st and st.step not in ("done", step):
            from onboarding import get_step_command
            cmd_name = get_step_command(st.step)
            if cmd_name:
                create_command(db, agent_id=agent_id, command=cmd_name, step=st.step)
        next_step = st.step if st and st.step != "done" else None
        return cmd, True, next_step, 201
    else:
        # Record error
        st = add_onboarding_error(db, vcoo_id, step, output)
        if st and st.status == "blocked":
            return cmd, True, None, 201  # blocked, stop
        # Re-enqueue same command for retry (if not blocked)
        if st and st.status != "blocked":
            from onboarding import get_step_command
            cmd_name = get_step_command(step)
            create_command(db, agent_id=agent_id, command=cmd_name, step=step)
        return cmd, True, step, 201  # same step, retry pending


# ── Audit Log ────────────────────────────────────────────────

def revoke_token(db: Session, jti: str, token_type: str = None, revoked_by: str = None):
    """Revoke a JWT by its ID."""
    existing = db.query(models.RevokedToken).filter(models.RevokedToken.jti == jti).first()
    if existing:
        return False
    rt = models.RevokedToken(jti=jti, token_type=token_type, revoked_by=revoked_by)
    db.add(rt)
    db.commit()
    return True


def is_token_revoked(db: Session, jti: str) -> bool:
    """Check if a JWT ID has been revoked."""
    if not jti:
        return False
    return db.query(models.RevokedToken).filter(models.RevokedToken.jti == jti).first() is not None


def create_audit_log(db: Session, action: str, actor_email: str = None, actor_id: str = None, vcoo_id: str = None, metadata: dict = None):
    log = models.AuditLog(
        action=action,
        actor_email=actor_email,
        actor_id=actor_id,
        vcoo_id=vcoo_id,
        log_metadata=json.dumps(metadata) if metadata else None,
    )
    db.add(log)
    db.commit()
    return log


def get_audit_log_for_vcoo(db: Session, vcoo_id: str, limit: int = 20):
    return db.query(models.AuditLog).filter(
        models.AuditLog.vcoo_id == vcoo_id
    ).order_by(models.AuditLog.created_at.desc()).limit(limit).all()


def update_agent_version(db: Session, agent_id: str, template_version: str = None, supervisor_version: str = None):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        return
    if template_version:
        agent.template_version = template_version
    if supervisor_version:
        agent.supervisor_version = supervisor_version
    db.commit()
