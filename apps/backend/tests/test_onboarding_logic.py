"""Tests de la lógica pura de onboarding (sin BD)."""
from onboarding import (
    get_steps_for_modules,
    get_total_steps,
    can_advance_to,
    get_next_step,
    get_module_label,
    get_module_description,
    is_onboarding_complete,
    get_wizard_step,
    get_step_command,
    has_agent_command,
    get_agent_total_steps,
)


class TestOnboardingLogic:
    def test_get_steps_for_modules_core_only(self):
        steps = get_steps_for_modules(["core"])
        assert steps == ["bootstrap", "finalize"]

    def test_get_steps_for_modules_office(self):
        steps = get_steps_for_modules(["core", "office"])
        assert "google-oauth" in steps
        assert "bootstrap" in steps
        assert "finalize" in steps

    def test_get_steps_for_modules_developer(self):
        steps = get_steps_for_modules(["core", "developer"])
        assert "github-setup" in steps
        assert "vercel-setup" in steps
        assert "supabase-setup" in steps
        assert "bootstrap" in steps
        assert "finalize" in steps

    def test_get_steps_for_modules_all(self):
        steps = get_steps_for_modules(["core", "office", "mail", "planner", "developer"])
        assert len(steps) == 8  # bootstrap + google-oauth + gmail-setup + trello-setup + github-setup + vercel-setup + supabase-setup + finalize

    def test_get_total_steps(self):
        assert get_total_steps(["core"]) == 2
        assert get_total_steps(["core", "office"]) == 3
        assert get_total_steps(["core", "developer"]) == 5

    def test_can_advance_to_bootstrap(self):
        """Bootstrap no tiene dependencias, siempre se puede avanzar."""
        assert can_advance_to("bootstrap", [], ["core"])

    def test_can_advance_to_google_oauth_only_after_bootstrap(self):
        """Google OAuth requiere bootstrap."""
        assert not can_advance_to("google-oauth", [], ["core", "office"])
        assert can_advance_to("google-oauth", ["bootstrap"], ["core", "office"])

    def test_can_advance_to_gmail_requires_bootstrap_and_google_oauth(self):
        assert not can_advance_to("gmail-setup", ["bootstrap"], ["core", "office", "mail"])
        assert can_advance_to("gmail-setup", ["bootstrap", "google-oauth"], ["core", "office", "mail"])

    def test_can_advance_to_github_requires_bootstrap(self):
        assert not can_advance_to("github-setup", [], ["core", "developer"])
        assert can_advance_to("github-setup", ["bootstrap"], ["core", "developer"])

    def test_can_advance_to_vercel_requires_bootstrap_and_github(self):
        assert not can_advance_to("vercel-setup", ["bootstrap"], ["core", "developer"])
        assert can_advance_to("vercel-setup", ["bootstrap", "github-setup"], ["core", "developer"])

    def test_can_advance_to_supabase_requires_bootstrap_and_github(self):
        assert not can_advance_to("supabase-setup", ["bootstrap"], ["core", "developer"])
        assert can_advance_to("supabase-setup", ["bootstrap", "github-setup"], ["core", "developer"])

    def test_can_advance_to_finalize_requires_all(self):
        """Finalize requiere todos los pasos contratados."""
        assert not can_advance_to("finalize", ["bootstrap"], ["core", "office"])
        assert can_advance_to("finalize", ["bootstrap", "google-oauth"], ["core", "office"])

    def test_can_advance_to_finalize_with_developer(self):
        steps = get_steps_for_modules(["core", "developer"])
        # developer steps: bootstrap, github, vercel, supabase, finalize
        all_except_finalize = [s for s in steps if s != "finalize"]
        assert can_advance_to("finalize", all_except_finalize, ["core", "developer"])

    def test_get_next_step_returns_first_uncompleted(self):
        assert get_next_step([], ["core", "office"]) == "bootstrap"
        assert get_next_step(["bootstrap"], ["core", "office"]) == "google-oauth"

    def test_get_next_step_returns_none_when_done(self):
        steps = get_steps_for_modules(["core"])
        all_steps = [s for s in steps]
        assert get_next_step(all_steps, ["core"]) is None

    def test_get_module_label(self):
        assert get_module_label("office") == "Google Drive"
        assert get_module_label("mail") == "Gmail"
        assert get_module_label("unknown") == "Unknown"

    def test_get_module_description(self):
        assert "documentos" in get_module_description("office").lower()
        assert get_module_description("unknown") == "Servicio conectable"

    def test_is_onboarding_complete_true_when_done(self):
        assert is_onboarding_complete("done", ["bootstrap"], ["core"])

    def test_is_onboarding_complete_false_when_not_done(self):
        assert not is_onboarding_complete("bootstrap", [], ["core"])

    def test_is_onboarding_complete_false_on_finalize_without_all(self):
        """Aunque se esté en finalize, no debe dar por completado si faltan pasos."""
        assert not is_onboarding_complete("finalize", ["bootstrap"], ["core", "office"])

    def test_get_wizard_step_mapping(self):
        assert get_wizard_step("bootstrap") == 0
        assert get_wizard_step("google-oauth") == 1
        assert get_wizard_step("finalize") == 3
        assert get_wizard_step("done") == 3
        assert get_wizard_step("unknown") == 0

    def test_get_step_command(self):
        assert get_step_command("bootstrap") == "verify-bootstrap"
        assert get_step_command("finalize") == "finalize"

    def test_has_agent_command(self):
        assert has_agent_command("bootstrap")
        assert has_agent_command("finalize")
        assert not has_agent_command("nonexistent")

    def test_get_agent_total_steps(self):
        assert get_agent_total_steps(["core"]) == 2  # bootstrap + finalize
        assert get_agent_total_steps(["core", "office"]) == 3

    def test_get_steps_order_is_canonical(self):
        """Los pasos deben devolverse en orden canónico, no en orden de módulos."""
        steps = get_steps_for_modules(["core", "developer", "office"])
        bootstrap_idx = steps.index("bootstrap")
        google_idx = steps.index("google-oauth")
        github_idx = steps.index("github-setup")
        assert bootstrap_idx < google_idx
        assert google_idx < github_idx
