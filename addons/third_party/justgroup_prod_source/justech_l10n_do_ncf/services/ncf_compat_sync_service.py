"""Sincroniza NCF Justech con campos LatAm/Adel para compatibilidad Odoo estándar."""
from odoo import models


class JustechDoNcfCompatSyncService(models.AbstractModel):
    _name = "justech.do.ncf.compat.sync.service"
    _description = "NCF LatAm/Adel Compatibility Sync"

    def resolve_latam_document_type(self, justech_doc, company=None):
        """Map Justech fiscal document type → l10n_latam.document.type by prefix."""
        if not justech_doc or "l10n_latam.document.type" not in self.env:
            return self.env["l10n_latam.document.type"]
        Latam = self.env["l10n_latam.document.type"]
        prefix = (justech_doc.prefix or "").strip().upper()
        if not prefix:
            return Latam
        latam = Latam.search([("doc_code_prefix", "=", prefix)], limit=1)
        if not latam:
            latam = Latam.search([("code", "=", prefix)], limit=1)
        return latam

    def assignment_write_vals(self, move, ncf, ncf_range, doc):
        """Valores write al asignar NCF: Justech + mirror LatAm cuando exista."""
        move.ensure_one()
        vals = {
            "justech_do_ncf": ncf,
            "justech_do_ncf_range_id": ncf_range.id,
            "justech_do_document_type_id": doc.id,
        }
        vals.update(self.latam_mirror_vals(move, ncf, doc))
        return vals

    def latam_mirror_vals(self, move, ncf, doc=None):
        """Solo metadatos compat — no activa motor Adel."""
        move.ensure_one()
        if not ncf:
            return {}
        if not self.env["justech.do.fiscal.config.service"].is_dual_write_enabled(move.company_id):
            return {}
        vals = {}
        if "l10n_latam_document_number" in move._fields:
            vals["l10n_latam_document_number"] = ncf
        doc = doc or move.justech_do_document_type_id
        if doc and "l10n_latam_document_type_id" in move._fields:
            latam = self.resolve_latam_document_type(doc, move.company_id)
            if latam:
                vals["l10n_latam_document_type_id"] = latam.id
        return vals

    def sync_manual_ncf(self, move):
        """Tras NCF manual validado, reflejar en LatAm."""
        move.ensure_one()
        if not move.justech_do_ncf:
            return
        vals = self.latam_mirror_vals(move, move.justech_do_ncf, move.justech_do_document_type_id)
        if vals:
            move.write(vals)
