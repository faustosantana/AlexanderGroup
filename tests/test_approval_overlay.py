from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
UX = REPO_ROOT / "addons/alexander/justech_alexander_ux"


def test_approval_overlay_uses_real_actions() -> None:
    views = (UX / "views" / "approval_request_views.xml").read_text(encoding="utf-8")
    hooks = (UX / "hooks.py").read_text(encoding="utf-8")
    branding = (UX / "views" / "approval_branding.xml").read_text(encoding="utf-8")
    security = (UX / "security" / "approval_visibility.xml").read_text(encoding="utf-8")
    assert "justech.approval.request" in views
    assert "Mis solicitudes" in views
    assert "Aprobadas" in views
    assert "Rechazadas" in views
    assert "Histórico" in views
    assert "Pendientes de mi aprobación" in views
    assert "company_id" in views
    assert "requester_id" in views
    assert "Flujo de Aprobaciones" in branding
    assert "Aprobaciones Justech" not in branding
    assert "justech.do" not in branding
    assert "justgroup.app" not in branding
    assert "https://doralexgroup.cloud" in branding
    assert "rule_approval_request_own" in security
    assert "apply_approval_overlay" in hooks
    assert "alexander.pina@inversionesdoralex.com" in hooks
    assert "geilin.rosario@inversionesdoralex.com" in hooks


def test_approval_guards_block_direct_state() -> None:
    request = (UX / "models" / "approval_request.py").read_text(encoding="utf-8")
    guard = (UX / "models" / "approval_document_guard.py").read_text(encoding="utf-8")
    assert "justech_approval_state" in guard
    assert "not self.env.su" in guard
    assert "not self.env.su" in request
    assert "_mail_brand_label" in request
    assert "JUSTECH" not in request
