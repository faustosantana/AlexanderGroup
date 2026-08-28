"""Proveedor de configuración fiscal por empresa.

P0.1 — Fuente de verdad NCF (FISC-AUD-001):
- Emisión: Justech (`justech_do_*`) es canónico.
- Compras recibidas: LATAM (`l10n_latam_*`) es entrada del proveedor.
- FDP: solo lectura (Justech → LATAM → estándar).
- Dual-write NCF Justech→LATAM: OFF por defecto.
"""
from odoo import models


class JustechDoFiscalConfigService(models.AbstractModel):
    _name = "justech.do.fiscal.config.service"
    _description = "Justech Fiscal Configuration Service"

    # Canonical NCF write policy (documentation + helpers for callers).
    NCF_SOT_ISSUED = "justech"
    NCF_SOT_RECEIVED = "latam"
    NCF_READ_FACADE = "fdp"

    def get_ncf_source_of_truth(self, move=None, registration_mode=None):
        """Return canonical write stack for a move: 'justech' | 'latam' | 'none'."""
        if move is None:
            return self.NCF_SOT_ISSUED
        move.ensure_one()
        if move.move_type in ("in_invoice", "in_refund"):
            mode = registration_mode or (
                move.justech_do_purchase_registration_mode
                if "justech_do_purchase_registration_mode" in move._fields
                else "received"
            )
            if (mode or "received") == "received":
                return self.NCF_SOT_RECEIVED
        if move.move_type in (
            "out_invoice",
            "out_refund",
            "in_invoice",
            "in_refund",
        ):
            return self.NCF_SOT_ISSUED
        return "none"

    def is_fiscal_enabled(self, company=None):
        company = company or self.env.company
        if not (company.country_id.code == "DO" and company.justech_do_fiscal_enabled):
            return False
        if "justech.fiscal.feature.flag" in self.env:
            # Lectura técnica del motor: no exigir grupo Fiscal Admin al facturador.
            return self.env["justech.fiscal.feature.flag"].sudo().is_enabled(
                "ncf_motor", company
            )
        return True

    def is_dual_write_enabled(self, company=None):
        """Justech→LATAM NCF mirror. Default OFF (P0.1) when flag model/row missing."""
        company = company or self.env.company
        if "justech.fiscal.feature.flag" not in self.env:
            return False
        Flag = self.env["justech.fiscal.feature.flag"].sudo()
        # Prefer explicit row; if absent, do not dual-write.
        has_row = Flag.search_count(
            [
                ("code", "=", "ncf_dual_write"),
                ("active", "=", True),
                "|",
                ("company_id", "=", company.id),
                ("company_id", "=", False),
            ]
        )
        if not has_row:
            return False
        return Flag.is_enabled("ncf_dual_write", company)

    def is_duplicate_blocking_enabled(self, company=None):
        company = company or self.env.company
        if "justech.fiscal.feature.flag" not in self.env:
            return True
        return self.env["justech.fiscal.feature.flag"].sudo().is_enabled(
            "duplicate_blocking", company
        )

    def get_param(self, key, company=None, default=None):
        company = company or self.env.company
        full_key = f"justech_fiscal.{company.id}.{key}"
        value = self.env["ir.config_parameter"].sudo().get_param(full_key)
        if value is None:
            value = self.env["ir.config_parameter"].sudo().get_param(
                f"justech_fiscal.{key}", default
            )
        return value
