"""Printed NCF validity on Doralex invoices. Does not change the NCF engine."""

import sys
from pathlib import Path

MODELS = (
    Path(__file__).resolve().parent.parent
    / "addons"
    / "alexander"
    / "justech_alexander_reports"
    / "models"
)
if str(MODELS) not in sys.path:
    sys.path.insert(0, str(MODELS))

from ncf_validity import (  # noqa: E402
    dx_ecf_skips_ncf_validity,
    dx_ncf_prefix_and_seq,
    dx_ncf_validity_label,
    dx_pick_ncf_validity_date,
)

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "addons" / "alexander" / "justech_alexander_reports"


def test_pick_prefers_move_then_range_then_company():
    assert dx_pick_ncf_validity_date("2026-12-31", "2027-12-31", "2028-01-01") == (
        "2026-12-31"
    )
    assert dx_pick_ncf_validity_date(False, "2027-12-31", "2028-01-01") == "2027-12-31"
    assert dx_pick_ncf_validity_date(None, False, "2027-12-31") == "2027-12-31"
    assert dx_pick_ncf_validity_date(False, None, "") is False


def test_ecf_32_34_skip_validity():
    assert dx_ecf_skips_ncf_validity(False, "E32", "E3200000001") is False
    assert dx_ecf_skips_ncf_validity(True, "E32", "") is True
    assert dx_ecf_skips_ncf_validity(True, "E34", "") is True
    assert dx_ecf_skips_ncf_validity(True, "E31", "E3100000001") is False
    assert dx_ncf_validity_label(False) == "Válida hasta"
    assert dx_ncf_validity_label(True) == "Vencimiento e-NCF"


def test_ncf_prefix_and_seq():
    assert dx_ncf_prefix_and_seq("B0100000061") == ("B01", 61)
    assert dx_ncf_prefix_and_seq("B1500000150") == ("B15", 150)
    assert dx_ncf_prefix_and_seq("") == ("", False)


def test_invoice_template_prints_valida_hasta():
    comps = (REPORTS / "reports" / "components.xml").read_text(encoding="utf-8")
    hero = comps.split('id="dx_invoice_composition"')[1].split("</template>")[0]
    assert "ncf_validity" in hero
    assert "Válida hasta" in hero
    assert "dx-ncf-until" in hero
    assert "invoice_date_due" not in hero
    meta = comps.split('id="dx_commercial_meta"')[1].split("</template>")[0]
    assert "ncf_validity" in meta
    css = (REPORTS / "static" / "src" / "css" / "report.css").read_text(
        encoding="utf-8"
    )
    assert ".dx-ncf-until" in css
    py = (REPORTS / "models" / "report_compose.py").read_text(encoding="utf-8")
    assert "def _dx_invoice_ncf_validity" in py
    assert "justech_do_ncf_range_id" in py
    assert "l10n_do_ncf_expiration_date" in py
    assert '"ncf_validity": ncf_validity' in py
    manifest = (REPORTS / "__manifest__.py").read_text(encoding="utf-8")
    assert "19.0.3.13.10" in manifest


def test_does_not_reuse_quote_validity_as_ncf():
    company = (REPORTS / "models" / "res_company.py").read_text(encoding="utf-8")
    assert 'meta["date2_label"] = "Vencimiento"' in company
    compose = (REPORTS / "models" / "report_compose.py").read_text(encoding="utf-8")
    assert '"due": _dx_date(self.env, self.invoice_date_due)' in compose
    assert "ncf_validity_label" in compose


def test_invoice_prints_entrega_recibido_signatures():
    compose = (REPORTS / "models" / "report_compose.py").read_text(encoding="utf-8")
    invoice = compose.split("def _dx_invoice_compose")[1].split(
        "def _dx_invoice_propet"
    )[0]
    assert 'sign_left, sign_right = "Entrega", "Recibido"' in invoice
    assert "dx_report_show_signature" in invoice
    assert "customer_invoice" in invoice
    assert "min_mm=16" in invoice
    comps = (REPORTS / "reports" / "components.xml").read_text(encoding="utf-8")
    hero = comps.split('id="dx_invoice_composition"')[1].split("</template>")[0]
    assert "dx_signature_panel" in hero
    assert "ncf_validity" in hero
