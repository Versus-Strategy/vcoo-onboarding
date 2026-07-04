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

# Etiquetas descriptivas para mostrar en el frontend
MODULE_LABELS: dict[str, str] = {
    "office":    "Google Drive",
    "mail":      "Gmail",
    "planner":   "Calendar + Trello",
    "developer": "Developer",
}

MODULE_DESCRIPTIONS: dict[str, str] = {
    "office":    "Documentos, hojas de cálculo y almacenamiento en la nube",
    "mail":      "Correo electrónico y bandeja de entrada inteligente",
    "planner":   "Calendario, tareas y organización del trabajo",
    "developer": "GitHub, Vercel, Supabase y herramientas para desarrolladores",
}

# Proveedores de IA disponibles para el wizard de onboarding
PROVIDERS: list[dict[str, str]] = [
    {"id": "anthropic", "nombre": "Anthropic",   "descripcion": "Claude — modelos de última generación"},
    {"id": "openai",    "nombre": "OpenAI",      "descripcion": "GPT-4, GPT-4o y más"},
    {"id": "google",    "nombre": "Google IA",   "descripcion": "Gemini y modelos de Google"},
    {"id": "mistral",   "nombre": "Mistral AI",  "descripcion": "Modelos abiertos y eficientes"},
    {"id": "xai",       "nombre": "xAI",         "descripcion": "Grok y modelos de xAI"},
    {"id": "cohere",    "nombre": "Cohere",      "descripcion": "Modelos empresariales"},
    {"id": "openrouter","nombre": "OpenRouter",  "descripcion": "Múltiples modelos en un solo API"},
    {"id": "copilot",   "nombre": "GitHub Copilot", "descripcion": "Modelos de GitHub y socios"},
    {"id": "gemini",    "nombre": "Google Gemini","descripcion": "Modelos Gemini de Google"},
]


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
    "finalize":       3,
}


def get_wizard_step(step: str) -> int:
    return WIZARD_STEP_MAP.get(step, 0)


def is_onboarding_complete(step: str, completed: list[str], modules: list[str]) -> bool:
    """True when all required steps are done or we're on finalize."""
    all_steps = get_steps_for_modules(modules)
    if not all_steps:
        return True
    return step == "finalize" or len(completed) >= len(all_steps) - 1


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


def has_agent_command(step: str) -> bool:
    """Returns True if this step has a corresponding agent command."""
    return step in {"bootstrap", "google-oauth", "gmail-setup", "trello-setup",
                    "github-setup", "vercel-setup", "supabase-setup", "finalize"}


def get_agent_total_steps(modules: list[str]) -> int:
    """Number of steps that require agent verification (excludes provider-config, etc.)."""
    steps = get_steps_for_modules(modules)
    return sum(1 for s in steps if has_agent_command(s))
