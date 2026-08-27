# -*- coding: utf-8 -*-
"""Migración controlada legacy Adel → Motor Fiscal Justech."""
import hashlib
import json
import re
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


# Prefijos emitidos por nosotros en ventas / notas.
_SALE_PREFIXES = {"B01", "B02", "B03", "B04", "B14", "B15", "B16", "B17"}
# Prefijos emitidos por nosotros en compras (comprobantes propios).
_PURCHASE_PREFIXES = {"B11", "B13"}


class JustechDoNcfMigrationService(models.AbstractModel):
    _name = "justech.do.ncf.migration.service"
    _description = "NCF Migration Service (Legacy → Justech)"

    def build_proposals(self, companies=None):
        """Calcula propuestas de rango Justech por empresa/tipo.

        Returns:
            list[dict]: propuestas listas para el wizard / auditoría.
        """
        companies = companies or self.env["res.company"].search([])
        companies = companies.filtered(
            lambda c: c.country_id.code == "DO" and c.justech_do_fiscal_enabled
        )
        proposals = []
        for company in companies:
            proposals.extend(self._proposals_for_company(company))
        return proposals

    def _proposals_for_company(self, company):
        FiscalSeq = self.env["account.fiscal.sequence"].sudo()
        sequences = FiscalSeq.search(
            [("company_id", "=", company.id), ("state", "in", ("active", "depleted"))]
        )
        by_prefix = {}
        for seq in sequences:
            prefix = (seq.fiscal_type_id.doc_code_prefix or "").upper()
            if not re.match(r"^B\d{2}$", prefix):
                continue
            by_prefix.setdefault(prefix, self.env["account.fiscal.sequence"])
            by_prefix[prefix] |= seq
        out = []
        for prefix, candidates in sorted(by_prefix.items()):
            seq = max(
                candidates,
                key=lambda s: (1 if s.state == "active" else 0, s.sequence_end or 0),
            )
            out.append(self._build_one_proposal(company, seq, prefix))
        return out

    def _issued_move_types(self, prefix):
        if prefix in _PURCHASE_PREFIXES:
            return ("in_invoice", "in_refund", "in_debit")
        return ("out_invoice", "out_refund", "out_debit")

    def _max_published_seq(self, company, prefix):
        move_types = self._issued_move_types(prefix)
        self.env.cr.execute(
            """
            SELECT COALESCE(MAX(substring(ncf from 4)::bigint), 0),
                   MAX(ncf),
                   COUNT(*)
            FROM (
                SELECT COALESCE(
                    NULLIF(justech_do_ncf, ''),
                    NULLIF(l10n_latam_document_number, '')
                ) AS ncf
                FROM account_move
                WHERE company_id = %s
                  AND state = 'posted'
                  AND move_type = ANY(%s)
            ) t
            WHERE ncf ~ %s
            """,
            [company.id, list(move_types), f"^{prefix}[0-9]{{8}}$"],
        )
        row = self.env.cr.fetchone()
        return int(row[0] or 0), row[1] or False, int(row[2] or 0)

    def _duplicate_issued_count(self, company, prefix):
        move_types = self._issued_move_types(prefix)
        self.env.cr.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT ncf
                FROM (
                    SELECT COALESCE(
                        NULLIF(justech_do_ncf, ''),
                        NULLIF(l10n_latam_document_number, '')
                    ) AS ncf
                    FROM account_move
                    WHERE company_id = %s
                      AND state = 'posted'
                      AND move_type = ANY(%s)
                ) t
                WHERE ncf ~ %s
                GROUP BY ncf
                HAVING COUNT(*) > 1
            ) d
            """,
            [company.id, list(move_types), f"^{prefix}[0-9]{{8}}$"],
        )
        return int(self.env.cr.fetchone()[0] or 0)

    def _build_one_proposal(self, company, legacy_seq, prefix):
        DocType = self.env["justech.do.fiscal.document.type"].sudo()
        doc = DocType.search([("prefix", "=", prefix)], limit=1)
        ir_seq = legacy_seq.sequence_id
        legacy_next = int(ir_seq.number_next or legacy_seq.sequence_start or 1)
        legacy_start = int(legacy_seq.sequence_start or 1)
        legacy_end = int(legacy_seq.sequence_end or 0)
        legacy_last = max(legacy_start - 1, legacy_next - 1)

        max_pub, max_ncf, docs = self._max_published_seq(company, prefix)
        dupes = self._duplicate_issued_count(company, prefix)

        Range = self.env["justech.do.ncf.range"].sudo()
        existing = Range.search(
            [
                ("company_id", "=", company.id),
                ("prefix", "=", prefix),
                ("state", "in", ("draft", "active")),
            ],
            order="next_sequence desc",
            limit=1,
        )
        justech_next = int(existing.next_sequence) if existing else 0
        justech_last = max(0, justech_next - 1) if existing else 0

        # Regla: max(publicado, legacy_last, justech_last) + 1
        safe_next = max(max_pub, legacy_last, justech_last) + 1

        status = "ready"
        block_reasons = []
        if not doc:
            status = "blocked"
            block_reasons.append(
                _("No existe tipo fiscal Justech para el prefijo %s.") % prefix
            )
        if dupes:
            status = "blocked"
            block_reasons.append(
                _("Hay %s NCF duplicados emitidos para %s.") % (dupes, prefix)
            )
        if not legacy_end:
            status = "blocked"
            block_reasons.append(_("El rango legacy no tiene sequence_end."))
        if safe_next > legacy_end:
            status = "blocked"
            block_reasons.append(
                _(
                    "Siguiente seguro %(next)s supera el fin autorizado legacy %(end)s."
                )
                % {"next": safe_next, "end": legacy_end}
            )
        if safe_next < legacy_start:
            status = "blocked"
            block_reasons.append(
                _("Siguiente seguro %(next)s es menor que el inicio legacy %(start)s.")
                % {"next": safe_next, "start": legacy_start}
            )
        if existing and existing.state == "active":
            if existing.next_sequence == safe_next and existing.sequence_end >= safe_next:
                status = "skip"
                block_reasons.append(
                    _("Ya existe rango Justech activo alineado (next=%s).")
                    % existing.next_sequence
                )
            elif existing.next_sequence > safe_next:
                status = "blocked"
                block_reasons.append(
                    _(
                        "Rango Justech existente adelantado (next=%s) respecto al "
                        "cálculo seguro (%s). Revisar manualmente."
                    )
                    % (existing.next_sequence, safe_next)
                )
            elif existing.next_sequence < safe_next:
                status = "reconcile"
                block_reasons.append(
                    _(
                        "Rango Justech desfasado: next=%s, seguro=%s. "
                        "Usar reconciliación o recrear."
                    )
                    % (existing.next_sequence, safe_next)
                )

        today = fields.Date.context_today(self)
        exp = legacy_seq.expiration_date or (today + relativedelta(years=1))
        if isinstance(exp, date) and exp < today:
            # Rango legacy vencido: no bloquear migración de numeración, extender 1 año.
            exp = today + relativedelta(years=1)
        auth = legacy_seq.name or False
        proposed_name = Range.STANDARD_RANGE_NAMES.get(
            prefix, f"{prefix} Migración Justech"
        )

        payload = {
            "company_id": company.id,
            "company_name": company.name,
            "prefix": prefix,
            "document_type_id": doc.id if doc else False,
            "document_type_name": doc.display_name if doc else False,
            "legacy_sequence_id": legacy_seq.id,
            "legacy_name": legacy_seq.name,
            "legacy_state": legacy_seq.state,
            "legacy_start": legacy_start,
            "legacy_end": legacy_end,
            "legacy_number_next": legacy_next,
            "legacy_last": legacy_last,
            "max_published_seq": max_pub,
            "max_published_ncf": max_ncf,
            "published_docs": docs,
            "justech_range_id": existing.id if existing else False,
            "justech_next": justech_next or False,
            "safe_next": safe_next,
            "proposed_start": safe_next,
            "proposed_end": legacy_end,
            "proposed_name": proposed_name,
            "authorization_number": auth,
            "date_to": fields.Date.to_string(exp) if exp else False,
            "duplicate_groups": dupes,
            "status": status,
            "block_reasons": block_reasons,
            "proposed_next_ncf": f"{prefix}{safe_next:08d}" if safe_next else False,
        }
        payload["evidence_hash"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        return payload

    def apply_proposal(self, proposal, enable_journals=True):
        """Crea/activa el rango Justech. No modifica documentos ni legacy."""
        if proposal.get("status") not in ("ready", "reconcile"):
            raise UserError(
                _("La propuesta %s no se puede aplicar: %s")
                % (proposal.get("prefix"), "; ".join(proposal.get("block_reasons") or []))
            )
        company = self.env["res.company"].browse(proposal["company_id"])
        doc = self.env["justech.do.fiscal.document.type"].browse(
            proposal["document_type_id"]
        )
        if not company or not doc:
            raise UserError(_("Empresa o tipo fiscal inválido."))

        Range = self.env["justech.do.ncf.range"].sudo()
        existing = Range.browse(proposal["justech_range_id"]) if proposal.get(
            "justech_range_id"
        ) else Range.browse()

        vals = {
            "name": proposal["proposed_name"],
            "company_id": company.id,
            "document_type_id": doc.id,
            "authorization_number": proposal.get("authorization_number"),
            "sequence_start": proposal["proposed_start"],
            "sequence_end": proposal["proposed_end"],
            "next_sequence": proposal["safe_next"],
            "date_from": fields.Date.context_today(self),
            "date_to": fields.Date.to_date(proposal["date_to"])
            if proposal.get("date_to")
            else fields.Date.context_today(self) + relativedelta(years=1),
        }

        if existing and existing.exists() and proposal["status"] == "reconcile":
            # Solo avanzar next_sequence; nunca retroceder.
            if proposal["safe_next"] > existing.next_sequence:
                existing.write(
                    {
                        "next_sequence": proposal["safe_next"],
                        "sequence_end": max(existing.sequence_end, proposal["proposed_end"]),
                    }
                )
            rng = existing
        elif existing and existing.exists() and existing.state == "draft":
            existing.write(vals)
            rng = existing
        else:
            rng = Range.create(vals)

        if rng.state == "draft":
            rng.action_activate()
        elif rng.state != "active":
            raise UserError(_("No se pudo activar el rango %s.") % rng.display_name)

        journals_enabled = 0
        if enable_journals:
            journals_enabled = self._enable_journals_for_prefix(company, proposal["prefix"])

        log = self.env["justech.do.ncf.migration.log"].sudo().create(
            {
                "company_id": company.id,
                "prefix": proposal["prefix"],
                "legacy_sequence_id": proposal.get("legacy_sequence_id"),
                "range_id": rng.id,
                "last_published_ncf": proposal.get("max_published_ncf"),
                "safe_next": proposal["safe_next"],
                "source": "legacy_migration",
                "evidence_hash": proposal.get("evidence_hash"),
                "payload_json": json.dumps(proposal, default=str),
                "user_id": self.env.user.id,
            }
        )
        return {"range": rng, "log": log, "journals_enabled": journals_enabled}

    def _enable_journals_for_prefix(self, company, prefix):
        Journal = self.env["account.journal"].sudo()
        if prefix in _PURCHASE_PREFIXES:
            domain = [("company_id", "=", company.id), ("type", "=", "purchase")]
        else:
            domain = [("company_id", "=", company.id), ("type", "=", "sale")]
        journals = Journal.search(domain)
        # Solo diarios fiscales principales (excluir migración CxC/CxP por código)
        journals = journals.filtered(
            lambda j: (j.code or "").upper() not in ("CXC", "CXP")
        )
        to_enable = journals.filtered(lambda j: not j.justech_do_use_ncf)
        to_enable.write({"justech_do_use_ncf": True})
        return len(to_enable)
