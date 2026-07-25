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
        assert steps == ["bootstrap", "whatsapp-setup", "finalize"]

    def test_get_steps_for_modules_office(self):
        steps = get_steps_for_modules(["core", "office"])
        assert "google-oauth" in steps
        assert "bootstrap" in steps
        assert "finalize" in steps

    def test_get_steps_for_modules_office_and_google_drive_equivalent(self):
        office_steps = get_steps_for_modules(["core", "office"])
        gdrive_steps = get_steps_for_modules(["core", "google-drive"])
        assert office_steps == gdrive_steps

    def test_get_steps_for_modules_developer(self):
        steps = get_steps_for_modules(["core", "developer"])
        assert "github-setup" in steps
        assert "vercel-setup" in steps
        assert "supabase-setup" in steps
        assert "bootstrap" in steps
        assert "finalize" in steps

    def test_get_steps_for_modules_all(self):
        steps = get_steps_for_modules(["core", "office", "mail", "planner", "developer"])
        assert len(steps) == 9

    def test_get_total_steps(self):
        assert get_total_steps(["core"]) == 3
        assert get_total_steps(["core", "office"]) == 4
        assert get_total_steps(["core", "developer"]) == 6

    def test_can_advance_to_bootstrap(self):
        """Bootstrap no tiene dependencias, siempre se puede avanzar."""
        assert can_advance_to("bootstrap", [], ["core"])

    def test_can_advance_to_google_oauth_only_after_bootstrap(self):
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
        assert not can_advance_to("finalize", ["bootstrap"], ["core", "office"])
        assert not can_advance_to("finalize", ["bootstrap", "google-oauth"], ["core", "office"])
        assert can_advance_to("finalize", ["bootstrap", "whatsapp-setup", "google-oauth"], ["core", "office"])

    def test_can_advance_to_finalize_with_developer(self):
        steps = get_steps_for_modules(["core", "developer"])
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
        assert get_agent_total_steps(["core"]) == 3
        assert get_agent_total_steps(["core", "office"]) == 4

    def test_get_steps_order_is_canonical(self):
        steps = get_steps_for_modules(["core", "developer", "office"])
        bootstrap_idx = steps.index("bootstrap")
        google_idx = steps.index("google-oauth")
        github_idx = steps.index("github-setup")
        assert bootstrap_idx < google_idx
        assert google_idx < github_idx

    def test_cannot_advance_to_whatsapp(self):
        assert not can_advance_to("whatsapp-setup", [], ["core"])
        assert can_advance_to("whatsapp-setup", ["bootstrap"], ["core"])

    def test_onboarding_complete_all_steps(self):
        assert is_onboarding_complete("done", ["bootstrap", "whatsapp-setup"], ["core"])
        assert is_onboarding_complete("bootstrap", ["bootstrap", "whatsapp-setup", "finalize"], ["core"])
        assert not is_onboarding_complete("finalize", ["bootstrap"], ["core"])


class TestCRUDEdgeCases:
    """CRUD integration edge cases that need a DB session."""

    def test_advance_onboarding_step_none_state(self):
        from db import SessionLocal
        import crud
        db = SessionLocal()
        try:
            result = crud.advance_onboarding_step(db, "nonexistent-id", "bootstrap")
            assert result is None
        finally:
            db.close()

    def test_add_onboarding_error_none_state(self):
        from db import SessionLocal
        import crud
        db = SessionLocal()
        try:
            result = crud.add_onboarding_error(db, "nonexistent-id", "bootstrap", "error")
            assert result is None
        finally:
            db.close()

    def test_auto_enqueue_next_none_state(self):
        from db import SessionLocal
        import crud
        db = SessionLocal()
        try:
            result = crud.auto_enqueue_next(db, "no-agent-id", "nonexistent-vcoo-id")
            assert result is None
        finally:
            db.close()
