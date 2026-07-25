"""
onboarding.py — Onboarding step logic + dependency enforcement.
SPEC v2 §7: Módulos y Pasos del Onboarding.
"""

# ── Constantes del SPEC §7 ──

STEP_DEPENDENCIES: dict[str, list[str]] = {
    "bootstrap":      [],
    "google-oauth":   ["bootstrap"],
    "gmail-setup":    ["bootstrap", "google-oauth"],
    "trello-setup":   ["bootstrap"],
    "github-setup":   ["bootstrap"],
    "vercel-setup":   ["bootstrap", "github-setup"],
    "supabase-setup": ["bootstrap", "github-setup"],
    "whatsapp-setup": ["bootstrap"],
    "finalize":       [],  # especial: requiere todos los contratados
}

# Mapeo módulo → pasos que añade
MODULE_STEPS: dict[str, list[str]] = {
    "core":         ["bootstrap", "whatsapp-setup"],
    "office":       ["google-oauth"],
    "google-drive": ["google-oauth"],
    "mail":         ["gmail-setup"],
    "gmail":        ["gmail-setup"],
    "planner":      ["trello-setup"],
    "trello":       ["trello-setup"],
    "developer":    ["github-setup", "vercel-setup", "supabase-setup"],
}

# Etiquetas descriptivas para mostrar en el frontend
MODULE_LABELS: dict[str, str] = {
    "office":       "Google Drive",
    "google-drive": "Google Drive",
    "mail":         "Gmail",
    "gmail":        "Gmail",
    "planner":      "Calendar + Trello",
    "trello":       "Calendar + Trello",
    "developer":    "Developer",
}

MODULE_DESCRIPTIONS: dict[str, str] = {
    "office":       "Documentos, hojas de cálculo y almacenamiento en la nube",
    "google-drive": "Documentos, hojas de cálculo y almacenamiento en la nube",
    "mail":         "Correo electrónico y bandeja de entrada inteligente",
    "gmail":        "Correo electrónico y bandeja de entrada inteligente",
    "planner":      "Calendario, tareas y organización del trabajo",
    "trello":       "Calendario, tareas y organización del trabajo",
    "developer":    "GitHub, Vercel, Supabase y herramientas para desarrolladores",
}



def get_module_label(module_id: str) -> str:
    return MODULE_LABELS.get(module_id, module_id.capitalize())


def get_module_description(module_id: str) -> str:
    return MODULE_DESCRIPTIONS.get(module_id, "Servicio conectable")


def get_steps_for_modules(modules: list[str]) -> list[str]:
    """Devuelve los pasos necesarios según módulos contratados, en orden."""
    seen: set[str] = set()
    ordered: list[str] = []
    # Orden canónico
    canonical = [
        "bootstrap", "google-oauth", "gmail-setup",
        "trello-setup", "github-setup", "vercel-setup",
        "supabase-setup", "whatsapp-setup", "finalize",
    ]
    step_modules: dict[str, set[str]] = {}
    for mod, steps in MODULE_STEPS.items():
        for s in steps:
            step_modules.setdefault(s, set()).add(mod)

    for step in canonical:
        if step == "finalize":
            if "finalize" not in ordered:
                ordered.append(step)
            break
        mods = step_modules.get(step, set())
        if mods and any(m in modules for m in mods):
            ordered.append(step)
    return ordered


def get_total_steps(modules: list[str]) -> int:
    return len(get_steps_for_modules(modules))


def can_advance_to(step: str, completed: list[str], modules: list[str]) -> bool:
    """Un paso solo se puede iniciar si todos sus requisitos están completados."""
    if step == "finalize":
        # finalize requiere TODOS los contratados (menos él mismo)
        required = [s for s in get_steps_for_modules(modules) if s != "finalize"]
        return all(d in completed for d in required)

    deps = STEP_DEPENDENCIES.get(step, [])
    # Filtrar deps que no aplican (módulo no contratado)
    valid_steps = get_steps_for_modules(modules)
    required = [d for d in deps if d in valid_steps]
    return all(d in completed for d in required)


def get_next_step(current_completed: list[str], modules: list[str]) -> str | None:
    """Devuelve el siguiente paso pendiente, o None si todos completados."""
    ordered = get_steps_for_modules(modules)
    for step in ordered:
        if step not in current_completed:
            return step
    return None


# Mapeo de pasos del backend a pasos del wizard frontend (0-3)
# 0 = Instalar Agente, 1 = Proveedor IA, 2 = Módulos, 3 = Finalización
WIZARD_STEP_MAP: dict[str, int] = {
    "bootstrap":      0,
    "google-oauth":   1,
    "gmail-setup":    2,
    "trello-setup":   2,
    "github-setup":   2,
    "vercel-setup":   2,
    "supabase-setup": 2,
    "whatsapp-setup": 2,
    "finalize":       3,
    "done":           3,
}


def get_wizard_step(step: str) -> int:
    return WIZARD_STEP_MAP.get(step, 0)


def is_onboarding_complete(step: str, completed: list[str], modules: list[str]) -> bool:
    """True when all required steps are done."""
    all_steps = get_steps_for_modules(modules)
    if not all_steps:
        return True
    return step == "done" or len(completed) >= len(all_steps)


def get_step_command(step: str) -> str:
    """Devuelve el comando de verificación para un paso."""
    mapping = {
        "bootstrap":      "verify-bootstrap",
        "google-oauth":   "verify-google",
        "gmail-setup":    "verify-email",
        "trello-setup":   "verify-trello",
        "github-setup":   "verify-github",
        "vercel-setup":   "verify-vercel",
        "supabase-setup": "verify-supabase",
        "whatsapp-setup": "verify-whatsapp",
        "finalize":       "finalize",
    }
    return mapping.get(step, step)


def has_agent_command(step: str) -> bool:
    """Returns True if this step has a corresponding agent command."""
    return step in {"bootstrap", "google-oauth", "gmail-setup", "trello-setup",
                    "github-setup", "vercel-setup", "supabase-setup",
                    "whatsapp-setup", "finalize"}


def get_agent_total_steps(modules: list[str]) -> int:
    """Number of steps that require agent verification (excludes provider-config, etc.)."""
    steps = get_steps_for_modules(modules)
    return sum(1 for s in steps if has_agent_command(s))
