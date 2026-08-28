"""Asignación de NCF pre-post — orquestación centralizada."""
from odoo import _, fields, models
from odoo.exceptions import UserError


class JustechDoNcfAssignmentService(models.AbstractModel):
    _name = "justech.do.ncf.assignment.service"
    _description = "NCF Assignment Service"

    def _purchase_doc_label(self, doc):
        if not doc:
            return ""
        names = self.env["justech.do.fiscal.document.type"].PURCHASE_DOC_FULL_NAMES
        label = names.get(doc.prefix) or doc.name or doc.prefix
        return f"{doc.prefix} — {label}"

    def _validate_purchase_received(self, move):
        latam_type = getattr(move, "l10n_latam_document_type_id", False)
        latam_number = getattr(move, "l10n_latam_document_number", False)
        if not latam_type or not latam_number:
            raise UserError(
                _(
                    "Documento recibido: debe indicar el tipo de comprobante LATAM "
                    "y el NCF del proveedor antes de publicar."
                )
            )
        allowed = set(
            self.env["justech.do.fiscal.document.type"].PURCHASE_RECEIVED_DOC_PREFIXES
        )
        prefix = getattr(latam_type, "doc_code_prefix", False) or ""
        if prefix and prefix not in allowed:
            raise UserError(
                _(
                    "El tipo %(prefix)s no está permitido como documento recibido en Compras.",
                    prefix=prefix,
                )
            )

    def _validate_purchase_issued_ready(self, move, doc):
        if not doc or not doc.is_purchase_ncf():
            raise UserError(
                _(
                    "Seleccione un comprobante emitido por la empresa "
                    "(B11 — Comprobante de Compras / Proveedor Informal, "
                    "B13 — Comprobante para Gastos Menores o "
                    "B17 — Comprobante para Pagos al Exterior)."
                )
            )
        Config = self.env["justech.do.purchase.emission.config"]
        cfg = Config.get_for(move.company_id, doc)
        if not cfg:
            Config.ensure_configs_for_companies(move.company_id)
            cfg = Config.get_for(move.company_id, doc)
        if not cfg or not cfg.is_emission_ready():
            raise UserError(
                _(
                    "No existe un rango DGII activo para %(doc)s en %(company)s. "
                    "Configure y active un rango autorizado antes de publicar.",
                    doc=self._purchase_doc_label(doc),
                    company=move.company_id.display_name,
                )
            )

    def assign_before_post(self, moves):
        resolver = self.env["justech.do.ncf.document.type.resolver.service"]
        duplicate = self.env["justech.do.ncf.duplicate.service"]
        rules = self.env["justech.do.ncf.business.rules.service"]
        NcfRange = self.env["justech.do.ncf.range"]

        for move in moves:
            if move.state != "draft":
                continue
            if not self.env["justech.do.fiscal.config.service"].is_fiscal_enabled(
                move.company_id
            ):
                continue
            if move.justech_do_ncf_voided:
                continue

            # COMPRAS — documento recibido: LATAM manual, nunca consumir Justech.
            if getattr(move, "_justech_is_purchase_received", lambda: False)():
                self._validate_purchase_received(move)
                continue

            # COMPRAS — emitido: exigir tipo + rango activo antes de asignar.
            if getattr(move, "_justech_is_purchase_issued", lambda: False)():
                doc = move.justech_do_document_type_id or resolver.resolve_for_move(move)
                if doc and not move.justech_do_document_type_id:
                    move.justech_do_document_type_id = doc.id
                self._validate_purchase_issued_ready(move, doc)
                rules.validate_before_post(move)
                if move.justech_do_ncf:
                    duplicate.validate_manual_ncf(move)
                    continue
                if not move.journal_id.justech_do_use_ncf:
                    raise UserError(
                        _(
                            "El diario %(journal)s no tiene habilitado el Motor NCF "
                            "Justech para emitir desde Compras.",
                            journal=move.journal_id.display_name,
                        )
                    )
                lock_code = int(doc.code) if doc.code.isdigit() else 0
                self.env.cr.execute(
                    "SELECT pg_advisory_xact_lock(%s, %s)",
                    [move.company_id.id, lock_code],
                )
                ncf_range = NcfRange._find_active_range_for_update(
                    doc, move.journal_id, move.company_id
                )
                if not ncf_range:
                    raise UserError(
                        _(
                            "No existe un rango DGII activo para %(doc)s en %(company)s. "
                            "Configure y active un rango autorizado antes de publicar.",
                            doc=self._purchase_doc_label(doc),
                            company=move.company_id.display_name,
                        )
                    )
                ncf = ncf_range.consume_next(move)
                compat = self.env["justech.do.ncf.compat.sync.service"]
                move.write(compat.assignment_write_vals(move, ncf, ncf_range, doc))
                if move.move_type == "in_refund" and move.reversed_entry_id:
                    origin_ncf = move.reversed_entry_id.justech_do_ncf
                    move.justech_do_origin_ncf = origin_ncf
                    if not move.justech_do_ncf_modified:
                        move.justech_do_ncf_modified = origin_ncf
                continue

            # VENTAS (flujo original)
            doc = resolver.resolve_for_move(move)
            if doc and not move.justech_do_document_type_id:
                move.justech_do_document_type_id = doc.id
            rules.validate_before_post(move)
            if doc and doc.requires_vat and move.move_type in ("out_invoice", "out_refund"):
                if not move.partner_id.justech_do_has_rnc():
                    raise UserError(
                        _(
                            "El tipo de comprobante %(doc)s exige un RNC válido del cliente.",
                            doc=doc.prefix,
                        )
                    )
            if move.justech_do_ncf:
                duplicate.validate_manual_ncf(move)
                continue
            if not resolver.should_auto_assign_ncf(move):
                if move.move_type in ("out_invoice", "out_refund", "out_debit"):
                    doc_chk = doc or resolver.resolve_for_move(move)
                    if (
                        doc_chk
                        and doc_chk.auto_assign_on_post
                        and resolver.doc_supports_auto_ncf(move, doc_chk)
                    ):
                        if not move.journal_id.justech_do_use_ncf:
                            raise UserError(
                                _(
                                    "El diario %(journal)s no tiene habilitado el Motor NCF "
                                    "Justech. Active justech_do_use_ncf o asigne NCF "
                                    "manualmente antes de publicar.",
                                    journal=move.journal_id.display_name,
                                )
                            )
                        raise UserError(
                            _(
                                "Debe indicar o asignar un NCF antes de publicar esta factura."
                            )
                        )
                continue
            doc = move.justech_do_document_type_id
            lock_code = int(doc.code) if doc.code.isdigit() else 0
            self.env.cr.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [move.company_id.id, lock_code],
            )
            ncf_range = NcfRange._find_active_range_for_update(
                doc, move.journal_id, move.company_id
            )
            if not ncf_range:
                raise UserError(
                    _(
                        "No hay rango NCF activo para el tipo %(prefix)s. "
                        "Revise el Centro de Administración Fiscal.",
                        prefix=doc.prefix,
                    )
                )
            ncf = ncf_range.consume_next(move)
            compat = self.env["justech.do.ncf.compat.sync.service"]
            move.write(compat.assignment_write_vals(move, ncf, ncf_range, doc))
            if move.move_type == "out_refund" and move.reversed_entry_id:
                move.justech_do_origin_ncf = move.reversed_entry_id.justech_do_ncf

    def moves_for_post(self, moves, soft=True):
        draft = moves.filtered(lambda m: m.state == "draft")
        if soft:
            today = fields.Date.context_today(moves)
            draft = draft.filtered(lambda m: not m.date or m.date <= today)
        return draft
