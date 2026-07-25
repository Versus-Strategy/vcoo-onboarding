# Onboarding Refactor — Design Spec

**Goal:** Refactor auth pattern, centralize auto-trigger logic, deprecate `/poll`, add security tests, rename module IDs, add credential encryption endpoint.

## Fase A: Refactor Interno

### A1: Shared auth dependency (`get_current_client`)

Crear `get_current_client()` en `main.py` como FastAPI `Depends` que reemplace el patrón repetido de 6 endpoints:

```python
def get_current_client(
    identifier: str,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    # 1. Parse bearer
    # 2. verify_client_token
    # 3. get_vcoo by identifier
    # 4. check ownership (if not operator)
    # 5. return {"vcoo_id", "client_email", "is_operator", "vcoo_name"}
```

Afecta: `/setup/{identifier}/verify`, `/setup/{identifier}/advance`, `/setup/{identifier}/set-provider`, `/setup/{identifier}/start-pair-whatsapp`, `/setup/{identifier}/whatsapp-qr`, y parcialmente `GET /setup/{identifier}`.

### A2: Centralizar auto-trigger helper

Crear `_auto_enqueue_next(db, agent, vcoo_id)` en `crud.py` que:
1. Obtiene `onboarding_state`
2. Si status no es blocked/completed y step ≠ done, llama a `get_step_command(st.step)`
3. Encola comando si existe

Reemplaza la lógica duplicada en: `process_agent_result`, `oauth_callback`, `/register`.

## Fase B: Deprecación + Seguridad

### B1: Unificar `/poll` → `/tick`

- `/poll` añade header `Deprecation: true` + redirige internamente a lógica compartida
- Crear helper `_build_agent_response(agent, pending)` usado por ambos

### B2: Security tests

- Test rate limiting en `/register`
- Test path traversal en playbooks más exhaustivo
- Test que `install.sh` no expone tokens en URLs

## Fase C: Data + Documentación

### C1: Renombrar módulos

`MODULE_STEPS` acepta alias: `office` ← `google-drive`, `mail` ← `gmail`. Mantener compatibilidad hacia atrás (ambos nombres funcionan).

### C2: Cifrado credenciales

Endpoint `POST /setup/{id}/encrypt-creds` que toma credenciales y las cifra con la `encryption_key` del agente.
