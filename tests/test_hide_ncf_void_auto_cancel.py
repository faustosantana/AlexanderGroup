"""Hide Anular NCF / Corregir o Anular; void NCF when cancelling."""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
UX = REPO / "addons" / "alexander" / "justech_alexander_ux"
BASE = REPO / "addons" / "alexander" / "justech_alexander_base"


def test_ncf_void_buttons_hidden():
    views = (UX / "views" / "account_move_views.xml").read_text(encoding="utf-8")
    assert "action_open_void_ncf_wizard" in views
    assert "action_open_correct_invoice_wizard" in views
    assert "view_move_form_justech_do_ncf" in views
    assert 'attribute name="invisible">1' in views


def test_cancel_posted_invoice_voids_ncf():
    source = (BASE / "models" / "account_move_ncf_cancel.py").read_text(
        encoding="utf-8"
    )
    draft = (BASE / "models" / "account_move_draft.py").read_text(encoding="utf-8")
    views = (BASE / "views" / "account_move_views.xml").read_text(encoding="utf-8")
    assert "_dx_void_ncf_before_cancel" in source
    assert "justech_do_ncf_voided" in source
    assert "justech.do.ncf.consumption" in source
    assert "_dx_void_ncf_before_cancel" in draft
    assert 'string="Anular"' in views
    assert "invisible=\"state != 'posted'\"" in views
