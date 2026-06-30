from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException
import models
from datetime import datetime, timedelta


def create_vcoo(db: Session, name: str = None):
    v = models.VCOO(name=name, status='active')
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def get_vcoo(db: Session, vcoo_id: str):
    return db.query(models.VCOO).filter(models.VCOO.id == vcoo_id).first()


def list_vcoos(db: Session, limit: int = 50):
    """List VCOOs with their latest agent, ordered by creation date."""
    vcoos = (
        db.query(models.VCOO)
        .order_by(models.VCOO.created_at.desc())
        .limit(limit)
        .all()
    )
    for v in vcoos:
        agent = get_agent_by_vcoo(db, str(v.id))
        v.agent = agent
        active_token = get_active_token_for_vcoo(db, str(v.id))
        v.active_token = active_token
        # Attach modules from onboarding_state
        st = get_onboarding_state(db, str(v.id))
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
        from uuid import UUID
        vcoo_uuid = UUID(vcoo_id)
        
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
    """Return the active (unused, unexpired) token for a VCOO, or None."""
    return (
        db.query(models.ProvisionToken)
        .filter(
            models.ProvisionToken.vcoo_id == vcoo_id,
            models.ProvisionToken.used == False,
        )
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


def get_pending_commands(db: Session, agent_id: str):
    return db.query(models.Command).filter(
        models.Command.agent_id == agent_id,
        models.Command.status == 'pending'
    ).all()


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
    pt = db.query(models.ProvisionToken).filter(models.ProvisionToken.token == token).first()
    if not pt:
        return None
    if pt.used:
        return None
    if pt.expires_at and pt.expires_at.replace(tzinfo=None) < datetime.utcnow():
        return None
    pt.used = True
    db.commit()
    return str(pt.vcoo_id)


def lookup_provision_token(db: Session, token: str):
    """Read-only lookup: validates token WITHOUT consuming it (for setup page)."""
    pt = db.query(models.ProvisionToken).filter(models.ProvisionToken.token == token).first()
    if not pt:
        return None
    if pt.expires_at and pt.expires_at.replace(tzinfo=None) < datetime.utcnow():
        return None
    # Don't mark as used — the setup page is read-only
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
