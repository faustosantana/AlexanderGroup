# -*- coding: utf-8 -*-
"""Reconciliación post-sync: avanzar Justech si quedó detrás de NCF importados."""
import hashlib
import json
import re

from odoo import _, fields, models
from odoo.exceptions import UserError


class JustechDoNcfReconcileService(models.AbstractModel):
    _name = "justech.do.ncf.reconcile.service"
    _description = "NCF Reconcile After Data Sync"

    def build_proposals(self, companies=None):
        companies = companies or self.env["res.company"].search(
            [("justech_do_fiscal_enabled", "=", True)]
        )
        Range = self.env["justech.do.ncf.range"].sudo()
        Migration = self.env["justech.do.ncf.migration.service"]
        out = []
        for company in companies:
            ranges = Range.search(
                [("company_id", "=", company.id), ("state", "=", "active")]
            )
            for rng in ranges:
                prefix = rng.prefix
                if not prefix or not re.match(r"^B\d{2}$", prefix):
                    continue
                max_pub, max_ncf, _docs = Migration._max_published_seq(company, prefix)
                safe_next = max(max_pub, rng.next_sequence - 1) + 1
                # Nunca retroceder
                if safe_next <= rng.next_sequence:
                    status = "ok"
                    block = [_("Justech ya está al día (next=%s).") % rng.next_sequence]
                elif safe_next > rng.sequence_end:
                    status = "blocked"
                    block = [
                        _(
                            "Publicado hasta %s; safe_next=%s supera fin de rango %s."
                        )
                        % (max_ncf, safe_next, rng.sequence_end)
                    ]
                else:
                    status = "advance"
                    block = [
                        _("Avanzar next de %s → %s (último publicado %s).")
                        % (rng.next_sequence, safe_next, max_ncf)
                    ]
                payload = {
                    "company_id": company.id,
                    "company_name": company.name,
                    "range_id": rng.id,
                    "prefix": prefix,
                    "current_next": rng.next_sequence,
                    "max_published_seq": max_pub,
                    "max_published_ncf": max_ncf,
                    "safe_next": safe_next,
                    "status": status,
                    "block_reasons": block,
                }
                payload["evidence_hash"] = hashlib.sha256(
                    json.dumps(payload, sort_keys=True, default=str).encode()
                ).hexdigest()
                out.append(payload)
        return out

    def apply_proposal(self, proposal):
        if proposal.get("status") != "advance":
            raise UserError(_("Nada que avanzar para %s.") % proposal.get("prefix"))
        rng = self.env["justech.do.ncf.range"].sudo().browse(proposal["range_id"])
        if not rng.exists() or rng.state != "active":
            raise UserError(_("Rango inválido."))
        if proposal["safe_next"] <= rng.next_sequence:
            raise UserError(_("No se permite retroceder la secuencia."))
        if proposal["safe_next"] > rng.sequence_end:
            raise UserError(_("safe_next fuera del rango autorizado."))
        old = rng.next_sequence
        rng.write({"next_sequence": proposal["safe_next"]})
        log = self.env["justech.do.ncf.migration.log"].sudo().create(
            {
                "company_id": rng.company_id.id,
                "prefix": rng.prefix,
                "range_id": rng.id,
                "last_published_ncf": proposal.get("max_published_ncf"),
                "safe_next": proposal["safe_next"],
                "source": "post_sync_reconcile",
                "evidence_hash": proposal.get("evidence_hash"),
                "payload_json": json.dumps(
                    {**proposal, "old_next": old}, default=str
                ),
                "user_id": self.env.user.id,
            }
        )
        return {"range": rng, "log": log, "old_next": old}
