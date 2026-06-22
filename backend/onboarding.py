"""
onboarding.py — Onboarding step logic + dependency enforcement.
SPEC v2 §7: Módulos y Pasos del Onboarding.
"""

from typing import Optional

# ── Constantes del SPEC §7 ──

STEP_DEPENDENCIES: dict[str, list[str]] = {
    "bootstrap":      [],
    "google-oauth":   ["bootstrap"],
    "gmail-setup":    ["bootstrap", "google-oauth"],
    "trello-setup":   ["bootstrap"],
    "github-setup":   ["bootstrap"],
    "vercel-setup":   ["bootstrap", "github-setup"],
    "supabase-setup": ["bootstrap", "github-setup"],
    "finalize":       [],  # especial: requiere todos los contratados
}

# Mapeo módulo → pasos que añade
MODULE_STEPS: dict[str, list[str]] = {
    "core":      ["bootstrap"],
    "office":    ["google-oauth"],
    "mail":      ["gmail-setup"],
    "planner":   ["trello-setup"],
    "developer": ["github-setup", "vercel-setup", "supabase-setup"],
}


def get_steps_for_modules(modules: list[str]) -> list[str]:
    """Devuelve los pasos necesarios según módulos contratados, en orden."""
    seen: set[str] = set()
    ordered: list[str] = []
    # Orden canónico
    canonical = [
        "bootstrap", "google-oauth", "gmail-setup",
        "trello-setup", "github-setup", "vercel-setup",
        "supabase-setup", "finalize",
    ]
    step_modules: dict[str, str] = {}
    for mod, steps in MODULE_STEPS.items():
        for s in steps:
            step_modules[s] = mod

    for step in canonical:
        if step == "finalize":
            if "finalize" not in ordered:
                ordered.append(step)
            break
        mod = step_modules.get(step)
        if mod and mod in modules:
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


def get_next_step(current_completed: list[str], modules: list[str]) -> Optional[str]:
    """Devuelve el siguiente paso pendiente, o None si todos completados."""
    ordered = get_steps_for_modules(modules)
    for step in ordered:
        if step not in current_completed:
            return step
    return None


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
        "finalize":       "finalize",
    }
    return mapping.get(step, step)
