from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .catalog import (
    GENERAL_JOURNAL_HINTS,
    JOURNAL_LABELS,
    LOCATION_LABELS,
    PICKING_LABELS,
    all_business_areas,
    profile_for_company,
)


class ResCompany(models.Model):
    _inherit = "res.company"

    dx_short_code = fields.Char(
        string="Código de empresa",
        size=5,
        index=True,
        help="Código corto único (DOR, PIN, DOM, MAY, REM, BLU).",
    )
    dx_trade_name = fields.Char(string="Nombre comercial (público)")
    dx_public_sector = fields.Char(string="Sector público")
    dx_public_description = fields.Text(string="Descripción pública")
    dx_website_published = fields.Boolean(
        string="Visible en website institucional",
        default=False,
    )
    dx_sequence = fields.Integer(string="Orden público", default=100)
    dx_legal_representative = fields.Char(
        string="Representante legal",
        groups="base.group_system,account.group_account_manager",
        help="Uso interno. Nunca se publica en el website.",
    )
    dx_legal_id_number = fields.Char(
        string="Documento del representante",
        groups="base.group_system,account.group_account_manager",
        help="Uso interno fiscal. Nunca se publica en el website.",
    )

    dx_report_show_logo = fields.Boolean(string="Mostrar logo", default=True)
    dx_report_logo_height = fields.Integer(
        string="Alto del logo (mm)",
        default=18,
    )
    dx_report_show_legal_name = fields.Boolean(
        string="Mostrar razón social",
        default=True,
    )
    dx_report_show_rnc = fields.Boolean(
        string="Mostrar RNC en documentos",
        default=True,
        help="RNC solo en documentos comerciales/fiscales, nunca en el website.",
    )
    dx_report_show_address = fields.Boolean(string="Mostrar dirección", default=True)
    dx_report_show_phone = fields.Boolean(string="Mostrar teléfono", default=True)
    dx_report_show_email = fields.Boolean(string="Mostrar correo", default=True)
    dx_report_show_bank = fields.Boolean(
        string="Mostrar información bancaria",
        default=True,
    )
    dx_report_show_salesperson = fields.Boolean(string="Mostrar vendedor", default=True)
    dx_report_show_signature = fields.Boolean(string="Mostrar firma", default=True)
    dx_report_footer_text = fields.Char(string="Texto de pie de página")
    dx_report_terms = fields.Text(string="Términos por defecto")

    @api.constrains("dx_short_code")
    def _check_dx_short_code_unique(self):
        for company in self:
            if not company.dx_short_code:
                continue
            other = self.search(
                [
                    ("dx_short_code", "=", company.dx_short_code),
                    ("id", "!=", company.id),
                ],
                limit=1,
            )
            if other:
                raise ValidationError("El código corto de empresa debe ser único.")

    def _dx_public_payload(self):
        self.ensure_one()
        height = self.dx_report_logo_height or 18
        return {
            "id": self.id,
            "code": self.dx_short_code or "",
            "trade_name": self.dx_trade_name or self.name,
            "legal_display": self.dx_trade_name or self.name,
            "sector": self.dx_public_sector or "",
            "description": self.dx_public_description or "",
            "color": self.primary_color or "#1B365D",
            "logo_url": "/web/image/res.company/%s/logo" % self.id,
            "sequence": self.dx_sequence,
            "areas": tuple(
                a.strip() for a in (self.dx_public_sector or "").split(",") if a.strip()
            ),
            "logo_height": height,
        }

    @api.model
    def _dx_public_companies(self):
        companies = self.sudo().search(
            [
                ("dx_website_published", "=", True),
                ("dx_short_code", "!=", False),
            ],
            order="dx_sequence, name",
        )
        return [c._dx_public_payload() for c in companies]

    @api.model
    def _dx_public_company(self, code):
        code = (code or "").strip().upper()
        company = self.sudo().search(
            [
                ("dx_short_code", "=", code),
                ("dx_website_published", "=", True),
            ],
            limit=1,
        )
        return company._dx_public_payload() if company else {}

    @api.model
    def _dx_public_areas(self):
        return all_business_areas()

    def _dx_apply_profile(self, profile):
        self.ensure_one()
        footer = self.dx_report_footer_text or (
            "%s · República Dominicana" % profile["trade_name"]
        )
        vals = {
            "dx_short_code": profile["code"],
            "dx_trade_name": profile["trade_name"],
            "dx_public_sector": profile["sector"],
            "dx_public_description": profile["description"],
            "dx_website_published": True,
            "dx_sequence": profile["sequence"],
            "primary_color": profile["color"],
            "secondary_color": profile["color_secondary"],
            "dx_report_footer_text": footer,
        }
        self.write(vals)
        partner_vals = {}
        if "justech_do_rnc_official_name" in self.partner_id._fields:
            partner_vals["justech_do_rnc_official_name"] = self.name
        if "justech_do_rnc_trade_name" in self.partner_id._fields:
            partner_vals["justech_do_rnc_trade_name"] = profile["trade_name"]
        if "justech_do_rnc_economic_activity" in self.partner_id._fields:
            partner_vals["justech_do_rnc_economic_activity"] = profile["sector"]
        if partner_vals:
            self.partner_id.sudo().write(partner_vals)

    def _dx_structure_legal_from_comment(self):
        """Mueve datos legales del comment a campos propios y limpia el comment."""
        self.ensure_one()
        partner = self.partner_id.sudo()
        comment = partner.comment or ""
        if not comment:
            return
        text = comment.replace("<p>", "\n").replace("</p>", "\n")
        for raw in text.splitlines():
            line = raw.strip()
            if line.lower().startswith("representante legal:"):
                value = line.split(":", 1)[-1].strip()
                if value and not self.dx_legal_representative:
                    self.sudo().write({"dx_legal_representative": value})
            elif line.lower().startswith("cedula representante:"):
                value = line.split(":", 1)[-1].strip()
                if value and not self.dx_legal_id_number:
                    self.sudo().write({"dx_legal_id_number": value})
            elif line.lower().startswith("fecha inicio"):
                value = line.split(":", 1)[-1].strip()
                if value and "l10n_do_dgii_start_date" in self._fields:
                    if not self.l10n_do_dgii_start_date:
                        try:
                            self.sudo().write({"l10n_do_dgii_start_date": value})
                        except Exception:
                            pass
        # El comment no debe conservar cédulas, RNC ni representantes.
        partner.write({"comment": False})

    def _dx_apply_warehouse_organization(self):
        self.ensure_one()
        code = self.dx_short_code
        if not code:
            return
        Warehouse = self.env["stock.warehouse"].sudo()
        warehouses = Warehouse.search([("company_id", "=", self.id)])
        for wh in warehouses:
            old_code = wh.code
            wh.write({"name": "Almacén Principal", "code": code})
            self._dx_rename_locations(wh, old_code, code)
            self._dx_rename_picking_types(wh, old_code, code)
            self._dx_rename_stock_sequences(old_code, code)

    def _dx_rename_locations(self, warehouse, old_code, new_code):
        Location = self.env["stock.location"].sudo()
        locations = Location.search(
            [
                ("company_id", "=", self.id),
                ("usage", "in", ("internal", "view")),
            ]
        )
        locations.invalidate_recordset()
        view = warehouse.view_location_id
        if view and view.name != new_code:
            view.write({"name": new_code})
        labels = {key.lower(): value for key, value in LOCATION_LABELS.items()}
        for loc in locations:
            name = (loc.name or "").strip()
            new_name = labels.get(name.lower())
            if new_name and new_name != name:
                loc.write({"name": new_name})

    def _dx_rename_picking_types(self, warehouse, old_code, new_code):
        types = (
            self.env["stock.picking.type"]
            .sudo()
            .search([("warehouse_id", "=", warehouse.id)])
        )
        for ptype in types:
            label = PICKING_LABELS.get(ptype.code)
            vals = {}
            if label:
                vals["name"] = "%s / %s" % (new_code, label)
            if ptype.sequence_id and ptype.sequence_id.prefix:
                prefix = ptype.sequence_id.prefix.replace(old_code, new_code)
                if prefix != ptype.sequence_id.prefix:
                    ptype.sequence_id.write({"prefix": prefix})
            if vals:
                ptype.write(vals)

    def _dx_rename_stock_sequences(self, old_code, new_code):
        sequences = (
            self.env["ir.sequence"].sudo().search([("company_id", "=", self.id)])
        )
        for seq in sequences:
            vals = {}
            prefix = seq.prefix or ""
            if old_code and old_code in prefix:
                vals["prefix"] = prefix.replace(old_code, new_code)
            name = seq.name or ""
            dirty = any(
                token in name
                for token in (
                    "PENDIENTE",
                    "Doralex Empresa",
                    "Oficina principal",
                    old_code or "",
                )
            )
            if dirty:
                clean = name
                for token in (
                    " [PENDIENTE RAZON SOCIAL/RNC]",
                    "Oficina principal - ",
                ):
                    clean = clean.replace(token, "")
                if old_code:
                    clean = clean.replace(old_code, new_code)
                vals["name"] = "%s · %s" % (
                    new_code,
                    clean.strip() or seq.code or "secuencia",
                )
            if vals:
                seq.write(vals)

    def _dx_apply_journal_organization(self):
        self.ensure_one()
        code = self.dx_short_code
        if not code:
            return
        journals = (
            self.env["account.journal"].sudo().search([("company_id", "=", self.id)])
        )
        for journal in journals:
            label = JOURNAL_LABELS.get(journal.type)
            if not label and journal.type == "general":
                jcode = journal.code or ""
                for hint, hinted_label in GENERAL_JOURNAL_HINTS:
                    if hint in jcode:
                        label = hinted_label
                        break
                if not label:
                    label = "Operaciones diversas"
            if label:
                journal.write({"name": "%s · %s" % (label, code)})

    def _dx_ensure_document_sequences(self):
        self.ensure_one()
        code = self.dx_short_code
        if not code:
            return
        Sequence = self.env["ir.sequence"].sudo()
        specs = (
            ("sale.order", "%s/SO/" % code, "Pedidos de venta · %s" % code),
            ("purchase.order", "%s/OC/" % code, "Órdenes de compra · %s" % code),
            ("stock.scrap", "%s/SP/" % code, "Desperdicios · %s" % code),
        )
        for seq_code, prefix, name in specs:
            existing = Sequence.search(
                [("code", "=", seq_code), ("company_id", "=", self.id)],
                limit=1,
            )
            if existing:
                existing.write({"prefix": prefix, "name": name, "padding": 5})
            else:
                Sequence.create(
                    {
                        "name": name,
                        "code": seq_code,
                        "prefix": prefix,
                        "padding": 5,
                        "company_id": self.id,
                    }
                )

    def _dx_apply_professional_organization(self):
        for company in self:
            profile = profile_for_company(company)
            if not profile:
                continue
            company._dx_apply_profile(profile)
            company._dx_structure_legal_from_comment()
            company._dx_apply_warehouse_organization()
            company._dx_apply_journal_organization()
            company._dx_ensure_document_sequences()

    @api.model
    def _dx_bootstrap_doralex(self):
        companies = self.sudo().search([])
        targets = companies.filtered(lambda c: profile_for_company(c))
        targets._dx_apply_professional_organization()
        leftover = companies - targets
        main = self.env.ref("base.main_company", raise_if_not_found=False)
        for company in leftover:
            if main and company.id == main.id and "My Company" in (company.name or ""):
                company.write(
                    {
                        "name": "Plantilla técnica (no operativa)",
                        "dx_website_published": False,
                    }
                )
        return True
