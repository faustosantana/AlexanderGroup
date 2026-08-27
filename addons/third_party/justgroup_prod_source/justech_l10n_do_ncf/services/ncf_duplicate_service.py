"""Detección de NCF duplicados — clave fiscal v2.0."""
from odoo import _, models
from odoo.exceptions import ValidationError

from odoo.addons.justech_l10n_do_ncf.validators import duplicate_scope


class JustechDoNcfDuplicateService(models.AbstractModel):
    _name = "justech.do.ncf.duplicate.service"
    _description = "NCF Duplicate Detection Service"

    def validate_manual_ncf(self, move):
        move.ensure_one()
        if not move.justech_do_ncf:
            return
        validator = self.env["justech.do.fiscal.validator.service"]
        ncf = validator.validate_ncf_format(move.justech_do_ncf)
        move.justech_do_ncf = ncf
        prefix, _seq = validator.parse_ncf(ncf)
        if move.justech_do_document_type_id and prefix != move.justech_do_document_type_id.prefix:
            raise ValidationError(
                _("El prefijo del NCF no coincide con el tipo de comprobante seleccionado.")
            )
        self.check_duplicate(move, ncf)
        self.env["justech.do.ncf.compat.sync.service"].sync_manual_ncf(move)

    def check_duplicate(self, move, ncf):
        move.ensure_one()
        if not self.env["justech.do.fiscal.config.service"].is_duplicate_blocking_enabled(
            move.company_id
        ):
            return
        domain = duplicate_scope.duplicate_search_domain(
            company_id=move.company_id.id,
            ncf=ncf,
            move_type=move.move_type,
            partner_id=move.partner_id.id if move.partner_id else False,
        )
        domain.insert(0, ("id", "!=", move.id))
        dup = move.search(domain, limit=1)
        if dup:
            module = duplicate_scope.fiscal_module_for_move_type(move.move_type)
            company = move.company_id.display_name
            if module == "compras":
                msg = _(
                    "No fue posible registrar el comprobante fiscal.\n\n"
                    "El NCF %(ncf)s del proveedor ya está registrado en %(move)s "
                    "(%(company)s).\n\n"
                    "Cada NCF debe ser único según la normativa DGII.\n"
                    "Verifique el NCF del proveedor antes de continuar.",
                    ncf=ncf,
                    move=dup.name,
                    company=company,
                )
            else:
                msg = _(
                    "No fue posible emitir el comprobante fiscal.\n\n"
                    "El NCF %(ncf)s ya fue utilizado en otra factura de %(company)s "
                    "(%(move)s).\n\n"
                    "Revise la configuración del rango fiscal o contacte al administrador.",
                    ncf=ncf,
                    company=company,
                    move=dup.name,
                )
            raise ValidationError(msg)

    def find_duplicate_groups_v2(self, company):
        """Escaneo read-only de duplicados reales v2.0 (para diagnóstico)."""
        company = company or self.env.company
        cr = self.env.cr
        cr.execute(
            """
            SELECT am.id, am.name, am.move_type, am.justech_do_ncf,
                   COALESCE(rp.vat, '') AS partner_vat,
                   COALESCE(rpc.vat, '') AS company_vat
            FROM account_move am
            JOIN res_company rc ON rc.id = am.company_id
            JOIN res_partner rpc ON rpc.id = rc.partner_id
            LEFT JOIN res_partner rp ON rp.id = am.partner_id
            WHERE am.company_id = %s
              AND am.state = 'posted'
              AND am.justech_do_ncf IS NOT NULL
              AND am.justech_do_ncf != ''
              AND COALESCE(am.justech_do_ncf_voided, false) = false
            ORDER BY am.justech_do_ncf, am.id
            """,
            [company.id],
        )
        rows = cr.fetchall()
        from odoo.addons.justech_l10n_do_base.validators import fiscal_context

        buckets: dict[tuple, list] = {}
        for row in rows:
            move_id, name, move_type, ncf, partner_vat, company_vat = row
            key = fiscal_context.fiscal_duplicate_key_v2(
                company_id=company.id,
                move_type=move_type,
                ncf=ncf,
                company_vat=company_vat,
                partner_vat=partner_vat,
            )
            buckets.setdefault(key, []).append({"id": move_id, "name": name, "ncf": ncf})

        return [
            {"key": key, "moves": moves}
            for key, moves in buckets.items()
            if len(moves) > 1
        ]
