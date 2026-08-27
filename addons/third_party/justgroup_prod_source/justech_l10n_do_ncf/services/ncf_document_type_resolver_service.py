"""Resolución de tipo de comprobante fiscal — lógica extraída de account.move."""
from odoo import models


class JustechDoNcfDocumentTypeResolverService(models.AbstractModel):
    _name = "justech.do.ncf.document.type.resolver.service"
    _description = "NCF Document Type Resolver Service"

    def resolve_for_move(self, move):
        """Orden de resolución (ventas):

        1. Tipo ya persistido en la factura (si válido).
        2. Comprobante por defecto del cliente.
        3. Histórico confirmado / reconstruible por empresa.
        4. Clasificación validada por padrón (sugerencia).
        5. Regla inequívoca (sugerencia compute).
        6. Vacío (el post bloqueará si es cliente nuevo).
        """
        move.ensure_one()
        journal = move.journal_id
        purchase_issued = move.move_type in ("in_invoice", "in_refund") and getattr(
            move, "justech_do_purchase_registration_mode", "received"
        ) == "issued"
        if move.justech_do_document_type_id:
            if move.move_type in ("out_invoice", "out_refund") or purchase_issued:
                return move.justech_do_document_type_id
        if move.move_type == "out_refund":
            return self.env.ref(
                "justech_l10n_do_base.doc_type_b04", raise_if_not_found=False
            )
        if move.move_type == "out_invoice" and move.debit_origin_id:
            return self.env.ref(
                "justech_l10n_do_base.doc_type_b03", raise_if_not_found=False
            )
        if (
            move.move_type == "in_refund"
            and purchase_issued
            and move.reversed_entry_id
        ):
            return move.reversed_entry_id.justech_do_document_type_id
        if move.move_type == "out_invoice":
            partner = move.partner_id.commercial_partner_id
            # 2 + 3: default persistido o histórico por empresa
            partner_default = partner.justech_do_get_default_sale_document_type(
                company=move.company_id
            )
            if partner_default:
                return partner_default
            # 4 + 5: sugerencia inequívoca (padrón / persona / taxpayer)
            suggested = partner.justech_do_suggested_document_type_id
            if suggested and partner.justech_do_fiscal_config_state in (
                "validated_padron",
                "confirmed_history",
            ):
                return suggested
            if suggested and partner.justech_do_fiscal_config_state != "needs_review":
                # Regla inequívoca solo cuando el compute ya decidió prefijo
                # sin ambigüedad (p.ej. persona→B02, taxpayer→B01).
                payer = getattr(partner, "l10n_do_dgii_tax_payer_type", False)
                if partner.justech_do_rnc_status == "valid" or payer in (
                    "taxpayer",
                    "non_payer",
                    "governmental",
                    "special",
                ):
                    return suggested
                if not partner.is_company and partner.justech_do_partner_id_type in (
                    "2",
                    "3",
                    "4",
                ):
                    return suggested
            # NO usar RNC→B01 genérico: evita degradar gobierno/especial.
            return self.env["justech.do.fiscal.document.type"]
        # Compras recibidas: no resolver tipo Justech (LATAM externo).
        if move.move_type in ("in_invoice", "in_refund"):
            mode = getattr(move, "justech_do_purchase_registration_mode", "received")
            if mode != "issued":
                return self.env["justech.do.fiscal.document.type"]
            if move.justech_do_document_type_id and move.justech_do_document_type_id.is_purchase_ncf():
                return move.justech_do_document_type_id
            if journal.justech_do_default_document_type_id:
                doc = journal.justech_do_default_document_type_id
                if doc.is_purchase_ncf():
                    return doc
            return self.env["justech.do.fiscal.document.type"]
        return self.env["justech.do.fiscal.document.type"]

    def doc_supports_auto_ncf(self, move, doc):
        if not doc:
            return False
        if move.move_type in ("out_invoice", "out_refund") and doc.is_sale_ncf():
            return True
        if (
            move.move_type in ("in_invoice", "in_refund")
            and getattr(move, "justech_do_purchase_registration_mode", None) == "issued"
            and doc.is_purchase_ncf()
        ):
            return True
        return False

    def should_auto_assign_ncf(self, move):
        move.ensure_one()
        config = self.env["justech.do.fiscal.config.service"]
        if not config.is_fiscal_enabled(move.company_id):
            return False
        if move.move_type in ("in_invoice", "in_refund"):
            if getattr(move, "justech_do_purchase_registration_mode", "received") != "issued":
                return False
        if not move.journal_id.justech_do_use_ncf:
            return False
        doc = self.resolve_for_move(move)
        if not doc or not doc.auto_assign_on_post:
            return False
        return self.doc_supports_auto_ncf(move, doc)
