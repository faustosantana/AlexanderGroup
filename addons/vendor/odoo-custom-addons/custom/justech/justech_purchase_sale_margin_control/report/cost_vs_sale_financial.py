# -*- coding: utf-8 -*-
"""19.0.8.3.0 — Reporte compacto gerencial + monedas documentales.

Conserva ITBIS/margen correctos; elimina densidades de 1 op/página;
formatea cada importe con la moneda real del documento.
"""
import base64
import io
import re
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

try:
    from odoo.addons.justech_purchase_sale_margin_control.wizard.margin_labels import (
        label_payment_state,
    )
except ImportError:
    def label_payment_state(state):
        return state or ""


STATE_LABELS = {
    "draft": "Borrador",
    "detected": "Detectada",
    "pending_review": "Pendiente de revisión",
    "validated": "Validada",
    "approved": "Aprobada",
    "closed": "Cerrada",
    "rejected": "Rechazada",
    "reopened": "Reabierta",
}


def _move_ncf(move):
    if not move:
        return ""
    for fname in ("l10n_do_fiscal_number", "l10n_latam_document_number"):
        if fname in move._fields and move[fname]:
            return move[fname]
    return move.ref or ""


def _move_label(move):
    if not move:
        return ""
    name = (move.name or "").strip()
    if name and name != "/":
        return name
    return (move.ref or move.display_name or "").strip()


def _sign_for_move(move):
    """Notas de crédito restan."""
    if not move:
        return 1.0
    if move.move_type in ("out_refund", "in_refund"):
        return -1.0
    return 1.0


def _move_tax_amount(move):
    """ITBIS real: amount_tax, o suma de líneas, o tax_totals. Nunca inventado."""
    if not move:
        return 0.0
    tax = move.amount_tax or 0.0
    if tax:
        return abs(tax)
    # Fallback: diferencia líneas productivas
    lines = move.invoice_line_ids.filtered(
        lambda l: l.display_type not in ("line_section", "line_note")
    )
    from_lines = sum(abs(l.price_total - l.price_subtotal) for l in lines)
    if from_lines:
        return from_lines
    # tax_totals dict (Odoo 16+)
    totals = getattr(move, "tax_totals", None) or {}
    if isinstance(totals, dict):
        for key in ("tax_amount", "tax_amount_currency"):
            if totals.get(key):
                return abs(totals[key])
        groups = totals.get("groups_by_subtotal") or totals.get("subtotals") or []
        if isinstance(groups, dict):
            amount = 0.0
            for _name, group in groups.items():
                if isinstance(group, list):
                    for g in group:
                        amount += abs(g.get("tax_group_amount") or 0.0)
            if amount:
                return amount
    return 0.0


RELATION_CONFIRMED_STATES = frozenset({"validated", "approved", "closed"})


class PurchaseSaleCostVsSaleReportFinancial(models.TransientModel):
    _inherit = "purchase.sale.cost.vs.sale.report"

    # ------------------------------------------------------------------
    # Financial core
    # ------------------------------------------------------------------
    @api.model
    def _canonical_sale_service(self):
        return self.env["purchase.sale.canonical.sale.service"]

    @api.model
    def _sale_financials(self, tx):
        """Agrega facturas cliente reales (una vez cada una) o SO estimado.

        Factura posted/válida del negocio prevalece sobre SO estimada.
        Una MTX hub estimada cuyo negocio ya está facturado en otra MTX
        se marca is_superseded y no debe entrar al universo principal.
        """
        resolved = self._canonical_sale_service().resolve_canonical_sale(tx)
        if resolved.get("is_superseded"):
            currency = tx.currency_id or tx.company_id.currency_id
            return {
                "customer": tx.customer_id.display_name or "",
                "invoice_labels": [],
                "invoice_label": "",
                "ncf": "",
                "date": tx.transaction_date,
                "untaxed": 0.0,
                "tax": 0.0,
                "total": 0.0,
                "currency": currency,
                "currency_name": currency.name if currency else "",
                "payment_state": "",
                "is_estimated": True,
                "is_superseded": True,
                "tax_label": False,
                "document_kind": _("Venta facturada en otra operación"),
                "moves": self.env["account.move"],
            }

        invoices = resolved.get("moves")
        if invoices:
            invoices = invoices.sorted(
                lambda m: (m.invoice_date or fields.Date.today(), m.id)
            )
            untaxed = tax = total = 0.0
            labels = []
            ncfs = []
            dates = []
            currencies = set()
            payment_states = []
            exempt = True
            for inv in invoices:
                sign = _sign_for_move(inv)
                u = abs(inv.amount_untaxed) * sign
                t = _move_tax_amount(inv) * sign
                tot = abs(inv.amount_total) * sign
                untaxed += u
                tax += t
                total += tot
                labels.append(_move_label(inv))
                ncf = _move_ncf(inv)
                if ncf:
                    ncfs.append(ncf)
                if inv.invoice_date:
                    dates.append(inv.invoice_date)
                if inv.currency_id:
                    currencies.add(inv.currency_id)
                payment_states.append(label_payment_state(inv.payment_state))
                if abs(t) > 0.0001:
                    exempt = False
            currency = list(currencies)[0] if len(currencies) == 1 else (tx.currency_id or tx.company_id.currency_id)
            customer = (
                invoices[:1].partner_id.display_name
                or (tx.customer_id.display_name if tx.customer_id else "")
            )
            tax_label = _("Exento") if exempt and abs(tax) < 0.0001 else False
            return {
                "customer": customer,
                "invoice_labels": labels,
                "invoice_label": " · ".join(labels),
                "ncf": " · ".join(ncfs),
                "date": dates[0] if dates else tx.transaction_date,
                "untaxed": untaxed,
                "tax": tax,
                "total": total,
                "currency": currency,
                "currency_name": currency.name if currency else "",
                "payment_state": " · ".join([p for p in payment_states if p]),
                "is_estimated": False,
                "tax_label": tax_label,
                "document_kind": _("Factura de cliente"),
                "is_superseded": False,
                "moves": invoices,
            }

        # Estimado desde órdenes de venta (no presentar como factura)
        sos = resolved.get("sale_orders") or tx.sale_order_ids
        if sos:
            untaxed = sum(sos.mapped("amount_untaxed"))
            tax = sum(sos.mapped("amount_tax"))
            total = sum(sos.mapped("amount_total"))
            currency = sos[:1].currency_id or tx.currency_id or tx.company_id.currency_id
            customer = (
                (tx.customer_id.display_name if tx.customer_id else False)
                or sos[:1].partner_id.display_name
                or ""
            )
            return {
                "customer": customer,
                "invoice_labels": [],
                "invoice_label": _("Venta estimada: %s") % ", ".join(sos.mapped("name")),
                "ncf": "",
                "date": tx.transaction_date,
                "untaxed": untaxed,
                "tax": tax,
                "total": total,
                "currency": currency,
                "currency_name": currency.name if currency else "",
                "payment_state": "",
                "is_estimated": True,
                "tax_label": _("Exento") if abs(tax) < 0.0001 else False,
                "document_kind": _("Orden de venta (estimado)"),
                "is_superseded": False,
                "moves": self.env["account.move"],
            }

        # Fallback montos del TX
        untaxed = tx.sale_real_amount or tx.sale_estimated_amount or 0.0
        return {
            "customer": tx.customer_id.display_name or "",
            "invoice_labels": [],
            "invoice_label": "",
            "ncf": "",
            "date": tx.transaction_date,
            "untaxed": untaxed,
            "tax": 0.0,
            "total": untaxed,
            "currency": tx.currency_id or tx.company_id.currency_id,
            "currency_name": (tx.currency_id or tx.company_id.currency_id).name,
            "payment_state": "",
            "is_estimated": True,
            "is_superseded": False,
            "tax_label": False,
            "document_kind": _("Sin documento de venta"),
            "moves": self.env["account.move"],
        }

    @api.model
    def _cost_rows(self, tx, allocation_ledger=None):
        """Filas de costo para margen: inventario consumido y/o compra directa.

        Reglas:
        - Si la venta entregó stock, el costo de margen es la valoración de las
          salidas (SVL si existe; si no, value/standard_price × qty).
        - La factura proveedor de stock no se suma completa encima del consumo
          (evita duplicar). Sigue disponible para CxP vía include_in_cxp.
        - Compra directa MTO / servicios / costos adicionales sí entran al margen.
        - OC inventory_pending NUNCA entra completa: solo qty coincidente × PU.
        """
        if allocation_ledger is None:
            allocation_ledger = {}
        Inv = self.env["purchase.sale.inventory.cost.service"]
        Canon = self._canonical_sale_service()
        sale_orders = tx.sale_order_ids
        purchase_orders = Canon.attributable_purchase_orders(tx)
        inv_rows = Inv.inventory_cost_rows_for_sales(
            sale_orders,
            currency=tx.company_id.currency_id,
        )

        bill_rows = []
        bills = Canon.attributable_vendor_bills(tx).sorted(
            lambda m: (m.invoice_date or fields.Date.today(), m.id)
        )

        sale_lines = sale_orders.mapped("order_line")

        for bill in bills:
            sign = _sign_for_move(bill)
            pos = bill.invoice_line_ids.mapped("purchase_line_id.order_id")
            if not pos and bill.invoice_origin:
                pos = purchase_orders.filtered(
                    lambda p: p.name and p.name in (bill.invoice_origin or "")
                )
            untaxed = abs(bill.amount_untaxed) * sign
            tax = _move_tax_amount(bill) * sign
            total = abs(bill.amount_total) * sign
            polines = bill.invoice_line_ids.mapped("purchase_line_id")
            products = bill.invoice_line_ids.mapped("product_id")
            is_mto = bool(
                polines.filtered(
                    lambda l: l.sale_line_id and l.sale_line_id in sale_lines
                )
            )
            is_resale = bool(
                polines.filtered(lambda l: l.cost_usage_type == "resale_direct")
            )
            is_inventory_bill = bool(
                polines.filtered(lambda l: Inv._is_inventory_po_line(l))
            )
            all_service = bool(products) and all(p.type == "service" for p in products)
            has_storable = any(
                getattr(p, "is_storable", False)
                or getattr(p, "type", None) == "product"
                for p in products
            )

            if all_service:
                cost_source = "service"
                include_margin = True
            elif is_mto or is_resale:
                cost_source = "direct_purchase"
                include_margin = True
            elif inv_rows and (has_storable or is_inventory_bill):
                # Stock already valued via deliveries → bill is CxP only
                cost_source = "inventory" if is_inventory_bill else "direct_purchase"
                include_margin = False
            else:
                cost_source = "direct_purchase"
                include_margin = True

            bill_rows.append(
                {
                    "vendor": bill.partner_id.display_name or "",
                    "partner_id": bill.partner_id.id,
                    "po": ", ".join(pos.mapped("name")) or "",
                    "po_ids": tuple(sorted(pos.ids)),
                    "bill": _move_label(bill),
                    "bill_id": bill.id,
                    "ncf": _move_ncf(bill),
                    "date": bill.invoice_date,
                    "untaxed": untaxed if include_margin else 0.0,
                    "tax": tax if include_margin else 0.0,
                    "total": total if include_margin else 0.0,
                    "cxp_untaxed": untaxed,
                    "cxp_tax": tax,
                    "cxp_total": total,
                    "residual": bill.amount_residual * sign,
                    "payment_state": label_payment_state(bill.payment_state),
                    "raw_payment_state": bill.payment_state,
                    "move_type": bill.move_type,
                    "currency": bill.currency_id,
                    "currency_name": bill.currency_id.name if bill.currency_id else "",
                    "kind": "bill",
                    "label": _move_label(bill),
                    "cost_source": cost_source,
                    "include_in_margin": include_margin,
                    "include_in_cxp": True,
                }
            )

        # Inventario por consumo: SVL/done primero; si no hay salidas ni bills, qty×PU
        allocated_inv_rows = []
        inventory_pos = purchase_orders.filtered(
            lambda po: any(
                Inv._is_inventory_po_line(l)
                for l in po.order_line.filtered(lambda x: not x.display_type)
            )
        )
        direct_pos = purchase_orders - inventory_pos
        if (
            sale_orders
            and inventory_pos
            and not inv_rows
            and not bills
        ):
            allocated_inv_rows, allocation_ledger = Inv.allocate_inventory_po_cost_for_sales(
                inventory_pos,
                sale_orders,
                allocation_ledger=allocation_ledger,
                currency=tx.company_id.currency_id,
            )

        po_rows = []
        # Compra directa / pendiente de factura (NO inventario)
        if not bills and direct_pos and not inv_rows and not allocated_inv_rows:
            for po in direct_pos:
                po_rows.append(
                    {
                        "vendor": po.partner_id.display_name or "",
                        "partner_id": po.partner_id.id,
                        "po": po.name,
                        "po_ids": (po.id,),
                        "bill": "",
                        "bill_id": False,
                        "ncf": "",
                        "date": fields.Date.to_date(po.date_order)
                        if po.date_order
                        else False,
                        "untaxed": po.amount_untaxed,
                        "tax": po.amount_tax,
                        "total": po.amount_total,
                        "residual": 0.0,
                        "payment_state": _("Pendiente de factura"),
                        "raw_payment_state": False,
                        "move_type": False,
                        "currency": po.currency_id,
                        "currency_name": po.currency_id.name if po.currency_id else "",
                        "kind": "po",
                        "label": _("Pendiente de factura"),
                        "cost_source": "direct_purchase",
                        "include_in_margin": True,
                        "include_in_cxp": False,
                        "origin_note": _("Compra directa"),
                    }
                )

        # OC inventario sin venta: solo etiqueta, sin margen
        if not bills and inventory_pos and not sale_orders:
            for po in inventory_pos:
                status, _orig, _asg, _pend = Inv.purchase_inventory_status(po)
                label = {
                    "available": _("INVENTARIO DISPONIBLE"),
                    "partial": _("INVENTARIO PARCIALMENTE CONSUMIDO"),
                    "consumed": _("INVENTARIO CONSUMIDO"),
                }.get(status, _("INVENTARIO DISPONIBLE"))
                po_rows.append(
                    {
                        "vendor": po.partner_id.display_name or "",
                        "partner_id": po.partner_id.id,
                        "po": po.name,
                        "po_ids": (po.id,),
                        "bill": "",
                        "bill_id": False,
                        "ncf": "",
                        "date": fields.Date.to_date(po.date_order)
                        if po.date_order
                        else False,
                        "untaxed": 0.0,
                        "tax": 0.0,
                        "total": 0.0,
                        "residual": 0.0,
                        "payment_state": label,
                        "raw_payment_state": False,
                        "move_type": False,
                        "currency": po.currency_id,
                        "currency_name": po.currency_id.name if po.currency_id else "",
                        "kind": "inventory_purchase",
                        "label": label,
                        "cost_source": "inventory",
                        "include_in_margin": False,
                        "include_in_cxp": False,
                        "inventory_status": status,
                    }
                )

        # Costos manuales / adicionales en líneas de transacción (sin documento)
        extra_rows = []
        for line in tx.cost_line_ids.filtered(
            lambda l: l.state != "excluded"
            and not l.exclude_from_margin
            and l.is_manual
            and not l.account_move_id
            and not l.purchase_order_id
        ):
            src = line.cost_source or "manual"
            if line.cost_usage_type in ("logistic", "financial", "other"):
                src = "additional_cost"
            extra_rows.append(
                {
                    "vendor": line.partner_id.display_name or _("Manual"),
                    "partner_id": line.partner_id.id if line.partner_id else False,
                    "po": "",
                    "po_ids": (),
                    "bill": line.description or _("Costo manual"),
                    "bill_id": False,
                    "ncf": "",
                    "date": tx.transaction_date,
                    "untaxed": line.amount_untaxed,
                    "tax": line.amount_tax,
                    "total": line.amount_total or line.amount_untaxed,
                    "residual": 0.0,
                    "payment_state": "",
                    "raw_payment_state": False,
                    "move_type": False,
                    "currency": line.currency_id,
                    "currency_name": line.currency_id.name if line.currency_id else "",
                    "kind": "manual",
                    "label": line.description or _("Manual"),
                    "cost_source": src,
                    "include_in_margin": True,
                    "include_in_cxp": False,
                }
            )

        rows = list(inv_rows) + list(allocated_inv_rows)
        # Margin-visible bills + CxP-only bills (amounts zeroed for margin)
        for br in bill_rows:
            if br.get("include_in_margin") or br.get("include_in_cxp"):
                rows.append(br)
        if not inv_rows and not allocated_inv_rows and not bill_rows:
            rows.extend(po_rows)
        elif po_rows:
            # etiquetas inventario sin venta / CxP-only
            rows.extend([r for r in po_rows if not r.get("include_in_margin")])
        rows.extend(extra_rows)
        return rows

    @api.model
    def _cost_dedupe_key(self, crow):
        if crow.get("kind") == "inventory":
            return ("inventory", crow.get("bill"), crow.get("date"), round(crow.get("untaxed") or 0.0, 4))
        if crow.get("bill_id"):
            return ("bill", crow["bill_id"], bool(crow.get("include_in_margin", True)))
        if crow.get("kind") == "manual":
            return ("manual", crow.get("bill"), crow.get("untaxed"))
        po_ids = crow.get("po_ids") or ()
        if po_ids:
            return ("po", po_ids)
        return ("row", crow.get("vendor"), crow.get("po"), crow.get("untaxed"))

    @api.model
    def _currency_has_rate(self, currency, company, date):
        if not currency or currency == company.currency_id:
            return True
        return bool(
            self.env["res.currency.rate"].search(
                [
                    ("currency_id", "=", currency.id),
                    ("name", "<=", date),
                    "|",
                    ("company_id", "=", company.id),
                    ("company_id", "=", False),
                ],
                limit=1,
            )
        )

    @api.model
    def _convert_amount(self, amount, from_currency, to_currency, company, date):
        """Convierte con tasa histórica. No inventa tasa."""
        if not from_currency or not to_currency or from_currency == to_currency:
            return amount or 0.0, 1.0, True, date
        if not date:
            date = fields.Date.context_today(self)
        if not self._currency_has_rate(from_currency, company, date):
            return amount or 0.0, False, False, date
        if not self._currency_has_rate(to_currency, company, date):
            return amount or 0.0, False, False, date
        try:
            converted = from_currency._convert(amount or 0.0, to_currency, company, date)
            unit = from_currency._convert(1.0, to_currency, company, date)
        except Exception:
            return amount or 0.0, False, False, date
        return converted, unit, True, date

    @api.model
    def _operation_summary(self, tx, allocation_ledger=None):
        sale = self._sale_financials(tx)
        costs = self._cost_rows(tx, allocation_ledger=allocation_ledger)
        sale_curr = sale["currency"] or tx.currency_id or tx.company_id.currency_id
        company = tx.company_id
        date = sale["date"] or tx.transaction_date or fields.Date.context_today(self)

        margin_costs = [r for r in costs if r.get("include_in_margin", True)]
        cost_u_doc = sum(r["untaxed"] for r in margin_costs)
        cost_t_doc = sum(r["tax"] for r in margin_costs)
        cost_tot_doc = sum(r["total"] for r in margin_costs)

        cost_u = 0.0
        cost_t = 0.0
        cost_tot = 0.0
        conversions = []
        margin_pending_rate = False
        multi_currency = False

        enriched_costs = []
        for r in costs:
            crow = dict(r)
            ccur = r["currency"] or sale_curr
            crow["display_currency"] = ccur
            in_margin = r.get("include_in_margin", True)
            if ccur and sale_curr and ccur != sale_curr:
                multi_currency = True
                conv_u, rate, ok, rdate = self._convert_amount(
                    r["untaxed"], ccur, sale_curr, company, r["date"] or date
                )
                conv_t, _rate_t, ok2, _rdate_t = self._convert_amount(
                    r["tax"], ccur, sale_curr, company, r["date"] or date
                )
                conv_tot, _rate_tot, ok3, _rdate_tot = self._convert_amount(
                    r["total"], ccur, sale_curr, company, r["date"] or date
                )
                if not (ok and ok2 and ok3) or rate is False:
                    if in_margin:
                        margin_pending_rate = True
                    crow["converted_untaxed"] = False
                    crow["rate"] = False
                    crow["rate_date"] = rdate
                    crow["conversion_note"] = _("Margen pendiente por tasa")
                else:
                    crow["converted_untaxed"] = conv_u
                    crow["converted_tax"] = conv_t
                    crow["converted_total"] = conv_tot
                    crow["rate"] = rate
                    crow["rate_date"] = rdate
                    crow["conversion_note"] = _(
                        "Costo convertido a %(cur)s: %(amt)s · Tasa utilizada: %(rate).6f · Fecha: %(date)s"
                    ) % {
                        "cur": sale_curr.name,
                        "amt": formatLang(self.env, conv_u, currency_obj=sale_curr),
                        "rate": rate,
                        "date": rdate,
                    }
                    if in_margin:
                        cost_u += conv_u
                        cost_t += conv_t
                        cost_tot += conv_tot
                        conversions.append(crow["conversion_note"])
            else:
                crow["converted_untaxed"] = r["untaxed"]
                crow["converted_tax"] = r["tax"]
                crow["converted_total"] = r["total"]
                crow["rate"] = 1.0
                crow["rate_date"] = date
                crow["conversion_note"] = False
                if in_margin:
                    cost_u += r["untaxed"]
                    cost_t += r["tax"]
                    cost_tot += r["total"]
            enriched_costs.append(crow)

        has_sale = bool(
            sale["untaxed"] or sale.get("invoice_label") or sale.get("moves") or tx.sale_order_ids
        )
        has_margin_cost = bool(margin_costs)
        incomplete_sale_only = bool(has_sale and not has_margin_cost)
        incomplete_cost_only = bool(has_margin_cost and not has_sale)

        if margin_pending_rate:
            margin = 0.0
            margin_pct = 0.0
            band = "pending"
        elif incomplete_cost_only:
            # Sin venta: no calcular margen comercial
            margin = 0.0
            margin_pct = 0.0
            band = "pending"
        elif incomplete_sale_only:
            # Venta sin costo: margen estimado venta - 0, marcado pendiente de costo
            margin = sale["untaxed"]
            margin_pct = 100.0 if sale["untaxed"] else 0.0
            band = "pending"
        else:
            margin = sale["untaxed"] - cost_u
            margin_pct = (margin / sale["untaxed"] * 100.0) if sale["untaxed"] else 0.0
            if margin_pct < 0:
                band = "negative"
            elif margin_pct < 15:
                band = "low"
            else:
                band = "positive"

        state_label = STATE_LABELS.get(tx.state, tx.state)
        if margin_pending_rate:
            status = _("Margen pendiente por tasa")
        elif incomplete_cost_only:
            status = _("Margen pendiente")
        elif incomplete_sale_only:
            status = _("Costo pendiente")
        elif sale["is_estimated"]:
            status = _("Estimada")
        elif tx.state in ("approved", "closed", "validated"):
            status = _("Confirmada")
        elif tx.state in ("pending_review", "detected", "draft"):
            status = _("Pendiente")
        else:
            status = state_label

        return {
            "tx": tx,
            "tx_number": tx.transaction_number or tx.name or "",
            "state_label": state_label,
            "status": status,
            "sale": sale,
            "costs": enriched_costs,
            "cost_untaxed": cost_u if not margin_pending_rate else cost_u_doc,
            "cost_tax": cost_t if not margin_pending_rate else cost_t_doc,
            "cost_total": cost_tot if not margin_pending_rate else cost_tot_doc,
            "cost_untaxed_documental": cost_u_doc,
            "cost_tax_documental": cost_t_doc,
            "cost_total_documental": cost_tot_doc,
            "margin": margin,
            "margin_pct": margin_pct,
            "margin_band": band,
            "margin_pending_rate": margin_pending_rate,
            "incomplete_sale_only": incomplete_sale_only,
            "incomplete_cost_only": incomplete_cost_only,
            "multi_currency": multi_currency,
            "conversions": conversions,
            "company": company,
            "currency": sale_curr,
        }

    @api.model
    def _relation_status_for(self, tx, has_sale, has_cost):
        """Map real MTX state/validation → relation status (independent of class)."""
        if not (has_sale and has_cost):
            return "unrelated", _("SIN RELACIONAR")
        if (
            tx.state in RELATION_CONFIRMED_STATES
            or getattr(tx, "validation_state", None) == "validated"
        ):
            return "confirmed", _("CONFIRMADA")
        return "unconfirmed", _("SIN CONFIRMAR")

    @api.model
    def _block_relation_status(self, txs, has_sale, has_cost):
        if not (has_sale and has_cost):
            return "unrelated", _("SIN RELACIONAR")
        if not txs:
            return "unrelated", _("SIN RELACIONAR")
        statuses = [
            self._relation_status_for(tx, True, True)[0] for tx in txs
        ]
        if "confirmed" in statuses:
            return "confirmed", _("CONFIRMADA")
        if "unconfirmed" in statuses:
            return "unconfirmed", _("SIN CONFIRMAR")
        return "unrelated", _("SIN RELACIONAR")

    def _op_included(self, op):
        """Filtro por tipos de operación — UNION (OR) de checkboxes.

        Completa = venta + costo atribuible (estructura). Estado de relación
        (confirmada / sin confirmar) NO excluye de completas.
        """
        sale = op["sale"]
        if sale.get("is_superseded"):
            return False
        tx = op["tx"]
        has_sale = bool(sale["untaxed"] or sale["invoice_label"] or sale["moves"] or tx.sale_order_ids)
        has_cost = any(c.get("include_in_margin", True) for c in (op.get("costs") or []))
        if not has_sale and not has_cost:
            return False
        klass = getattr(tx, "report_relation_class", False) or ""
        sale_only = bool(has_sale and not has_cost)
        cost_only = bool(has_cost and not has_sale)
        both = bool(has_sale and has_cost)

        show_complete, show_sales, show_costs, show_incomplete = (
            self._operation_type_flags()
            if hasattr(self, "_operation_type_flags")
            else (
                bool(getattr(self, "show_complete", True)),
                bool(getattr(self, "show_sales_without_cost", False)),
                bool(getattr(self, "show_costs_without_sale", False)),
                bool(getattr(self, "show_incomplete", False)),
            )
        )

        # Compat 8.18: si aún existe report_scope y no hay multi-select explícito
        if "show_complete" not in self._fields and hasattr(self, "report_scope"):
            flags = self._effective_include_flags()
            scope = getattr(self, "report_scope", "all") or "all"
            if scope == "complete_only":
                return both
            if scope == "sales_wo_cost":
                return sale_only
            if scope == "costs_wo_sale":
                return cost_only
            if scope == "incomplete_only":
                return klass != "complete"
            if not has_cost and not flags["sales_wo_cost"]:
                return False
            if not has_sale and not flags["costs_wo_sale"]:
                return False
            return True

        # UNION of selected classes (never AND / intersection)
        matched = False
        if show_complete and both:
            matched = True
        if show_sales and sale_only:
            matched = True
        if show_costs and cost_only:
            matched = True
        if show_incomplete:
            # Residual incompletas: no re-clasificar C/D si esas clases
            # no están marcadas (evita intersección silenciosa).
            if not both and not sale_only and not cost_only:
                matched = True
            elif klass in ("pending_relation", "probable_duplicate") and not both:
                matched = True
            elif not both and not show_sales and not show_costs and not show_complete:
                # Solo "Incompletas": umbrella de no-completas (compat UX)
                matched = True
        if not matched:
            return False
        # Borradores/rechazadas: solo con incompletas o ventas/costos huérfanos
        if tx.state == "rejected" and not (show_incomplete or show_sales or show_costs):
            return False
        if tx.state == "draft" and not both and not (show_incomplete or show_sales or show_costs):
            return False
        return True

    def _iter_operation_summaries(self):
        self.ensure_one()
        ledger = {}
        Canon = self._canonical_sale_service()
        txs = self._iter_transactions()

        def _alloc_key(tx):
            has_inv = Canon.tx_has_invoice_sale(tx)
            superseded = Canon.is_superseded_estimated(tx)
            return (
                0 if has_inv else 1,
                1 if superseded else 0,
                tx.transaction_date or fields.Date.today(),
                tx.id,
            )

        for tx in txs.sorted(_alloc_key):
            if Canon.is_superseded_estimated(tx):
                continue
            summary = self._operation_summary(tx, allocation_ledger=ledger)
            if not self._op_included(summary):
                continue
            yield summary

    @api.model
    def _sale_group_key(self, tx, sale):
        """Clave comercial: SO canónica → factura cliente → TX.

        Una SO con varias facturas/NC se agrupa una sola vez.
        """
        sos = tx.sale_order_ids
        if sos:
            return ("so", tuple(sorted(sos.ids)))
        moves = sale.get("moves")
        if moves:
            return ("inv", tuple(sorted(moves.ids)))
        return ("tx", (tx.id,))

    def _margin_status_label(self, band):
        return {
            "positive": _("MARGEN SALUDABLE"),
            "low": _("MARGEN BAJO"),
            "negative": _("MARGEN NEGATIVO"),
            "pending": _("MARGEN PENDIENTE"),
        }.get(band, band or "")

    def _format_rate(self, rate):
        if rate is False or rate is None:
            return ""
        try:
            return "%.2f" % float(rate)
        except (TypeError, ValueError):
            return str(rate)

    def _iter_sale_blocks(self):
        """Consolida MTX bajo la misma venta comercial (factura/SO)."""
        self.ensure_one()
        groups = {}
        order_keys = []
        for op in self._iter_operation_summaries():
            key = self._sale_group_key(op["tx"], op["sale"])
            if key not in groups:
                groups[key] = []
                order_keys.append(key)
            groups[key].append(op)

        blocks = []
        for key in order_keys:
            ops = groups[key]
            real_ops = [
                op
                for op in ops
                if not op["sale"].get("is_estimated") and not op["sale"].get("is_superseded")
            ]
            base = max(
                real_ops or ops,
                key=lambda op: (
                    0 if op["sale"].get("is_estimated") else 1,
                    len(op["sale"].get("moves") or []),
                    abs(op["sale"].get("untaxed") or 0.0),
                ),
            )
            sale = dict(base["sale"])
            # Deduplicate costs across MTX
            costs = []
            seen = set()
            conversions = []
            pending = False
            multi = False
            tx_numbers = []
            txs = self.env["purchase.sale.margin.transaction"]
            for op in ops:
                txs |= op["tx"]
                tn = op.get("tx_number") or ""
                if tn and tn not in tx_numbers:
                    tx_numbers.append(tn)
                if op.get("margin_pending_rate"):
                    pending = True
                if op.get("multi_currency"):
                    multi = True
                for note in op.get("conversions") or []:
                    if note and note not in conversions:
                        conversions.append(note)
                for c in op["costs"]:
                    dk = self._cost_dedupe_key(c)
                    if dk in seen:
                        continue
                    seen.add(dk)
                    costs.append(c)

            # Recalculate consolidated margin from unique costs
            sale_curr = sale.get("currency") or base["currency"]
            company = base["company"]
            date = sale.get("date") or fields.Date.context_today(self)
            cost_u = cost_t = cost_tot = 0.0
            enriched = []
            conversions = []
            pending = False
            multi = False
            for r in costs:
                crow = dict(r)
                ccur = r.get("display_currency") or r.get("currency") or sale_curr
                crow["display_currency"] = ccur
                in_margin = r.get("include_in_margin", True)
                if ccur and sale_curr and ccur != sale_curr:
                    multi = True
                    conv_u, rate, ok, rdate = self._convert_amount(
                        r["untaxed"], ccur, sale_curr, company, r.get("date") or date
                    )
                    if not ok or rate is False:
                        if in_margin:
                            pending = True
                        crow["converted_untaxed"] = False
                        crow["rate"] = False
                        crow["rate_display"] = ""
                        crow["conversion_note"] = _("Margen pendiente por tasa")
                    else:
                        crow["converted_untaxed"] = conv_u
                        crow["rate"] = rate
                        crow["rate_display"] = self._format_rate(rate)
                        crow["conversion_note"] = _(
                            "Costo original: %(orig)s · Convertido: %(conv)s · Tasa: %(rate)s"
                        ) % {
                            "orig": formatLang(self.env, r["untaxed"], currency_obj=ccur),
                            "conv": formatLang(self.env, conv_u, currency_obj=sale_curr),
                            "rate": crow["rate_display"],
                        }
                        if in_margin:
                            cost_u += conv_u
                            conversions.append(crow["conversion_note"])
                else:
                    crow["converted_untaxed"] = r["untaxed"]
                    crow["rate"] = 1.0
                    crow["rate_display"] = ""
                    crow["conversion_note"] = False
                    if in_margin:
                        cost_u += r["untaxed"]
                if in_margin:
                    cost_t += r.get("tax") or 0.0
                    cost_tot += r.get("total") or 0.0
                # Display helpers for PDF/Excel-style columns (presentation only)
                if crow.get("kind") == "inventory":
                    crow["doc_line"] = crow.get("bill") or _("Salida inventario")
                    crow["status_label"] = _("CONSUMIDO")
                    crow["abono"] = False
                    crow["abono_note"] = ""
                elif crow.get("kind") in ("po", "inventory_purchase") or not crow.get("bill"):
                    crow["doc_line"] = _("OC %s · Pendiente de factura") % (crow.get("po") or "—")
                    crow["status_label"] = crow.get("label") or _("Pendiente de factura")
                    crow["abono"] = False
                    crow["abono_note"] = ""
                else:
                    parts = []
                    if crow.get("bill"):
                        parts.append(crow["bill"])
                    if crow.get("po"):
                        parts.append(_("OC %s") % crow["po"])
                    crow["doc_line"] = " · ".join(parts) if parts else "—"
                    # Abono / NC: paid portion or credit-note amount; blank if none
                    total = crow.get("total") or 0.0
                    residual = crow.get("residual") or 0.0
                    if total < -0.005:
                        crow["abono"] = abs(total)
                        crow["abono_note"] = _("Nota de crédito")
                        crow["status_label"] = _("Nota de crédito")
                    else:
                        paid = total - residual
                        if abs(paid) >= 0.005:
                            crow["abono"] = paid
                            crow["abono_note"] = _("Abono") if residual > 0.005 else _("Pagado")
                        else:
                            crow["abono"] = False
                            crow["abono_note"] = ""
                        raw_ps = (crow.get("payment_state") or "").strip()
                        if raw_ps.lower() in ("pagada parcialmente", "partial"):
                            crow["status_label"] = _("Pago parcial")
                        elif raw_ps.lower() in ("pagada", "paid"):
                            crow["status_label"] = _("Pagado")
                        elif raw_ps:
                            crow["status_label"] = raw_ps
                        else:
                            crow["status_label"] = _("Facturado")
                enriched.append(crow)

            if pending:
                margin = 0.0
                margin_pct = 0.0
                band = "pending"
            else:
                margin = sale["untaxed"] - cost_u
                margin_pct = (margin / sale["untaxed"] * 100.0) if sale["untaxed"] else 0.0
                if margin_pct < 0:
                    band = "negative"
                elif margin_pct < 15:
                    band = "low"
                else:
                    band = "positive"

            # Sale document line for header
            if sale.get("is_estimated"):
                sale_doc = _("Venta estimada · Cotización: %s") % (
                    sale.get("invoice_label", "").replace(_("Venta estimada: "), "").replace("Venta estimada: ", "")
                    or "—"
                )
            else:
                sale_doc = sale.get("invoice_label") or "—"

            has_sale = bool(
                sale.get("untaxed")
                or sale.get("invoice_label")
                or sale.get("moves")
                or any(t.sale_order_ids for t in txs)
            )
            has_margin_cost = any(c.get("include_in_margin", True) for c in enriched)
            incomplete_sale_only = bool(has_sale and not has_margin_cost)
            incomplete_cost_only = bool(has_margin_cost and not has_sale)
            if incomplete_cost_only and not pending:
                margin = 0.0
                margin_pct = 0.0
                band = "pending"
            elif incomplete_sale_only and not pending:
                margin = sale.get("untaxed") or 0.0
                margin_pct = 100.0 if margin else 0.0
                band = "pending"

            if incomplete_cost_only:
                scope_category = "COSTOS_SIN_VENTA"
            elif incomplete_sale_only:
                scope_category = (
                    "ESTIMADAS_SIN_FACTURAR"
                    if sale.get("is_estimated")
                    else "VENTAS_SIN_COSTOS"
                )
            elif has_sale and has_margin_cost:
                # Estructura completa (venta+costo). FX pendiente / sin confirmar
                # NO sacan la operación de esta clase.
                scope_category = "OPERACIONES_COMPLETAS"
            else:
                scope_category = "OPERACIONES_INCOMPLETAS"

            rel_status, rel_badge = self._block_relation_status(
                txs, has_sale, has_margin_cost
            )
            cost_stage, cost_stage_badge = "none", ""
            if txs and hasattr(txs[:1], "_cost_document_stage"):
                cost_stage, cost_stage_badge = txs[:1]._cost_document_stage()

            blocks.append(
                {
                    "group_key": key,
                    "sale": sale,
                    "costs": enriched,
                    "cost_untaxed": cost_u,
                    "cost_tax": cost_t,
                    "cost_total": cost_tot,
                    "margin": margin,
                    "margin_pct": margin_pct,
                    "margin_band": band,
                    "scope_category": scope_category,
                    "margin_label": self._margin_status_label(band),
                    "margin_pending_rate": pending,
                    "incomplete_sale_only": incomplete_sale_only,
                    "incomplete_cost_only": incomplete_cost_only,
                    "relation_status": rel_status,
                    "relation_badge": rel_badge,
                    "cost_stage": cost_stage,
                    "cost_stage_badge": cost_stage_badge,
                    "multi_currency": multi,
                    "conversions": conversions,
                    "company": company,
                    "currency": sale_curr,
                    "status": base.get("status"),
                    "state_label": base.get("state_label"),
                    "tx_numbers": tx_numbers,
                    "tx_number": ", ".join(tx_numbers[:3]),
                    "txs": txs,
                    "tx": base["tx"],
                    "sale_doc": sale_doc,
                    "payment_state": sale.get("payment_state") or "",
                }
            )

        # Sort
        sort_by = getattr(self, "sort_by", "date") or "date"

        def _sk(b):
            s = b["sale"]
            if sort_by == "customer":
                return (s.get("customer") or "", s.get("date") or fields.Date.today(), s.get("invoice_label") or "")
            if sort_by == "sale_amount":
                return (-(s.get("untaxed") or 0.0), s.get("date") or fields.Date.today())
            if sort_by == "margin":
                return (-(b.get("margin") or 0.0), s.get("date") or fields.Date.today())
            return (s.get("date") or fields.Date.today(), s.get("customer") or "", s.get("invoice_label") or "")

        blocks.sort(key=_sk)
        for i, b in enumerate(blocks, start=1):
            b["sale_number"] = i
        return blocks

    def _format_amount(self, amount, currency=None):
        """Formatea con moneda documental. Nunca concatena símbolos a mano."""
        currency = currency or self.company_id.currency_id
        if isinstance(currency, str):
            currency = self.env["res.currency"].search([("name", "=", currency)], limit=1) or self.company_id.currency_id
        return formatLang(self.env, amount or 0.0, currency_obj=currency)

    def _format_tax_display(self, amount, currency=None, tax_label=False):
        if tax_label:
            return tax_label
        return self._format_amount(amount, currency)

    def _template_has_forced_page_break_per_op(self):
        """Auditoría estática: no page-break-after/before always en bloque de op."""
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document",
            raise_if_not_found=False,
        )
        if not view:
            return True
        arch = view.arch_db or ""
        # Solo fallar si el bloque de operación fuerza salto
        if "page-break-after:always" in arch.replace(" ", "").lower():
            # permitido solo en resumen general
            if arch.count("page-break-after") > 1:
                return True
        if "page-break-before:always" in arch.replace(" ", "").lower():
            # permitido una vez para dashboard/resumen
            count = len(re.findall(r"page-break-before\s*:\s*always", arch, flags=re.I))
            if count > 1:
                return True
        # page-break-inside:avoid en jm-sale es intencional (8.5.0+) para no cortar ventas
        return False

    def _page_density_gate(self, op_count, page_count):
        """Criterios densos: 100 ops simples ≤ 25 páginas; promedio ≥ 3."""
        if op_count <= 0:
            return {"pass": True, "ops": op_count, "pages": page_count, "avg": 0.0, "reason": "empty"}
        avg = op_count / float(page_count or 1)
        reasons = []
        ok = True
        if op_count >= 100 and page_count > 25:
            ok = False
            reasons.append("100+ ops with >25 pages")
        if op_count >= 30 and avg < 3.0 and page_count > 25:
            ok = False
            reasons.append("avg ops/page < 3")
        return {
            "pass": ok,
            "ops": op_count,
            "pages": page_count,
            "avg": avg,
            "reason": "; ".join(reasons) or "ok",
        }

    def _general_summary(self, transactions=None):
        """Totales por moneda sobre ventas consolidadas. No mezcla monedas ni duplica ventas."""
        # transactions param kept for API compat; consolidación usa _iter_sale_blocks
        _unused_transactions = transactions  # noqa: F841 — no sombrear gettext `_`
        blocks = self._iter_sale_blocks()
        by_cur = {}
        pending_po = 0
        sales_wo_cost = 0
        costs_wo_sale = 0
        pending_review = 0
        pending_rate = 0
        pos_n = low_n = neg_n = 0
        complete_n = 0
        for b in blocks:
            sale_only = bool(b.get("incomplete_sale_only"))
            cost_only = bool(b.get("incomplete_cost_only"))
            # Clase estructural: venta+costo = completa (aunque FX pendiente o sin confirmar)
            struct_complete = not sale_only and not cost_only
            confirmed_for_margin = struct_complete and not b.get("margin_pending_rate")
            cur_rec = b["currency"]
            cur = cur_rec.name if cur_rec else ""
            bucket = by_cur.setdefault(
                cur,
                {
                    "tx_count": 0,
                    "sale_untaxed": 0.0,
                    "sale_tax": 0.0,
                    "sale_total": 0.0,
                    "cost_untaxed": 0.0,
                    "cost_tax": 0.0,
                    "cost_total": 0.0,
                    "margin": 0.0,
                    "currency_id": cur_rec,
                    "complete_count": 0,
                    "sale_confirmed": 0.0,
                    "sale_without_cost": 0.0,
                    "sale_estimated": 0.0,
                    "cost_without_sale": 0.0,
                },
            )
            if not bucket.get("currency_id") and cur_rec:
                bucket["currency_id"] = cur_rec
            s = b["sale"]
            bucket["tx_count"] += 1
            if struct_complete:
                bucket["complete_count"] += 1
                complete_n += 1
            if confirmed_for_margin:
                bucket["sale_untaxed"] += s["untaxed"]
                bucket["sale_tax"] += s["tax"]
                bucket["sale_total"] += s["total"]
                bucket["cost_untaxed"] += b["cost_untaxed"]
                bucket["cost_tax"] += b["cost_tax"]
                bucket["cost_total"] += b["cost_total"]
                bucket["margin"] += b["margin"]
                if s.get("is_estimated"):
                    bucket["sale_estimated"] += s["untaxed"]
                else:
                    bucket["sale_confirmed"] += s["untaxed"]
            elif sale_only:
                # venta sin costo: cuenta venta, no contamina margen confirmado
                bucket["sale_untaxed"] += s["untaxed"]
                bucket["sale_tax"] += s["tax"]
                bucket["sale_total"] += s["total"]
                if s.get("is_estimated"):
                    bucket["sale_estimated"] += s["untaxed"]
                else:
                    bucket["sale_without_cost"] += s["untaxed"]
            elif cost_only:
                bucket["cost_untaxed"] += b["cost_untaxed"]
                bucket["cost_tax"] += b["cost_tax"]
                bucket["cost_total"] += b["cost_total"]
                bucket["cost_without_sale"] += b["cost_untaxed"]
            elif struct_complete and b.get("margin_pending_rate"):
                # Completa estructural con tasa pendiente: volúmenes sí, margen no
                bucket["sale_untaxed"] += s["untaxed"]
                bucket["sale_tax"] += s["tax"]
                bucket["sale_total"] += s["total"]
                bucket["cost_untaxed"] += b["cost_untaxed"]
                bucket["cost_tax"] += b["cost_tax"]
                bucket["cost_total"] += b["cost_total"]

            if confirmed_for_margin:
                if b["margin_band"] == "positive":
                    pos_n += 1
                elif b["margin_band"] == "low":
                    low_n += 1
                else:
                    neg_n += 1
            elif b["margin_band"] == "pending" or sale_only or cost_only:
                pending_rate += 1

            if sale_only:
                sales_wo_cost += 1
            if cost_only:
                costs_wo_sale += 1

            for tx in b.get("txs") or b["tx"]:
                if tx.purchase_order_ids and not tx.vendor_bill_ids:
                    pending_po += 1
                if tx.state in ("pending_review", "detected", "draft"):
                    pending_review += 1

        top_clients = defaultdict(float)
        for b in blocks:
            if b.get("margin_pending_rate") or b.get("incomplete_sale_only") or b.get("incomplete_cost_only"):
                continue
            top_clients[b["sale"]["customer"] or _("(Sin cliente)")] += b["margin"]
        top_clients_list = sorted(top_clients.items(), key=lambda x: x[1], reverse=True)[:10]
        top_ops = sorted(
            [
                o
                for o in blocks
                if not o.get("margin_pending_rate")
                and not o.get("incomplete_sale_only")
                and not o.get("incomplete_cost_only")
            ],
            key=lambda o: o["margin"],
            reverse=True,
        )[:10]
        neg_ops = sorted(
            [
                o
                for o in blocks
                if o["margin"] < 0
                and not o.get("margin_pending_rate")
                and not o.get("incomplete_sale_only")
                and not o.get("incomplete_cost_only")
            ],
            key=lambda o: o["margin"],
        )
        # Presentación: ranking de proveedores por costo (no altera montos)
        top_vendors_map = defaultdict(float)
        for b in blocks:
            for c in b.get("costs") or []:
                name = c.get("vendor") or _("(Sin proveedor)")
                amt = c.get("converted_untaxed")
                if amt is False or amt is None:
                    amt = c.get("untaxed") or 0.0
                top_vendors_map[name] += amt
        top_vendors = sorted(top_vendors_map.items(), key=lambda x: x[1], reverse=True)[:10]

        by_currency_rows = []
        for cur, bucket in by_cur.items():
            row = dict(bucket)
            row["currency"] = cur
            confirmed_base = bucket.get("sale_confirmed") or 0.0
            row["margin_pct"] = (
                (bucket["margin"] / confirmed_base * 100.0) if confirmed_base else 0.0
            )
            by_currency_rows.append(row)

        category_totals = {
            "OPERACIONES_COMPLETAS": {"count": 0, "sale": 0.0, "cost": 0.0, "margin": 0.0},
            "VENTAS_SIN_COSTOS": {"count": 0, "sale": 0.0, "cost": 0.0, "margin": 0.0},
            "COSTOS_SIN_VENTA": {"count": 0, "sale": 0.0, "cost": 0.0, "margin": 0.0},
            "OPERACIONES_INCOMPLETAS": {"count": 0, "sale": 0.0, "cost": 0.0, "margin": 0.0},
            "ESTIMADAS_SIN_FACTURAR": {"count": 0, "sale": 0.0, "cost": 0.0, "margin": 0.0},
        }
        for b in blocks:
            cat = b.get("scope_category") or "OPERACIONES_INCOMPLETAS"
            bucket_cat = category_totals.setdefault(
                cat, {"count": 0, "sale": 0.0, "cost": 0.0, "margin": 0.0}
            )
            bucket_cat["count"] += 1
            bucket_cat["sale"] += b["sale"].get("untaxed") or 0.0
            bucket_cat["cost"] += b.get("cost_untaxed") or 0.0
            if cat == "OPERACIONES_COMPLETAS":
                bucket_cat["margin"] += b.get("margin") or 0.0
        return {
            "by_currency": by_cur,
            "by_currency_rows": by_currency_rows,
            "pending_po": pending_po,
            "sales_wo_cost": sales_wo_cost,
            "costs_wo_sale": costs_wo_sale,
            "complete_ops": complete_n,
            "pending_review": pending_review,
            "pending_rate": pending_rate,
            "tx_count": len(blocks),
            "sale_count": len(blocks),
            "positive": pos_n,
            "low": low_n,
            "negative": neg_n,
            "top_clients": top_clients_list,
            "top_ops": top_ops,
            "neg_ops": neg_ops,
            "top_vendors": top_vendors,
            "sales": blocks,
            "operations": blocks,
            "category_totals": category_totals,
            "report_layout": getattr(self, "report_layout", "compact") or "compact",
            "show_fiscal_detail": bool(getattr(self, "show_fiscal_detail", False)),
            "report_scope": getattr(self, "report_scope", "all") or "all",
            "report_scope_label": self._report_scope_label(),
        }

    # ------------------------------------------------------------------
    # Backward-compatible APIs used by tests / old PDF
    # ------------------------------------------------------------------
    @api.model
    def _relation_rows(self, tx):
        sale = self._sale_financials(tx)
        costs = self._cost_rows(tx)
        rows = []
        for c in costs:
            margin = sale["untaxed"] - c["untaxed"]
            rows.append(
                {
                    "company": tx.company_id.name,
                    "tx": tx.transaction_number or tx.name,
                    "state": STATE_LABELS.get(tx.state, tx.state),
                    "customer": sale["customer"],
                    "sale_inv": sale["invoice_label"],
                    "sale_ncf": sale["ncf"],
                    "sale_date": sale["date"],
                    "sale_untaxed": sale["untaxed"],
                    "sale_tax": sale["tax"],
                    "sale_total": sale["total"],
                    "sale_currency": sale["currency_name"],
                    "sale_is_estimated": sale["is_estimated"],
                    "vendor": c["vendor"],
                    "po": c["po"],
                    "bill": c["bill"],
                    "bill_ncf": c["ncf"],
                    "bill_date": c["date"],
                    "bill_untaxed": c["untaxed"],
                    "bill_tax": c["tax"],
                    "bill_total": c["total"],
                    "bill_currency": c["currency_name"],
                    "bill_residual": c["residual"],
                    "payment_state": c["payment_state"],
                    "allocated_cost": c["untaxed"],
                    "margin_row": margin,
                    "margin_pct_row": (margin / sale["untaxed"] * 100.0) if sale["untaxed"] else 0.0,
                    "relation_state": STATE_LABELS.get(tx.state, tx.state),
                    "validated_by": "",
                    "approved_by": "",
                    "kind": c["kind"],
                }
            )
        if not rows and self.env.context.get("include_empty_sale"):
            rows.append(
                {
                    "company": tx.company_id.name,
                    "tx": tx.transaction_number or tx.name,
                    "state": STATE_LABELS.get(tx.state, tx.state),
                    "customer": sale["customer"],
                    "sale_inv": sale["invoice_label"],
                    "sale_ncf": sale["ncf"],
                    "sale_date": sale["date"],
                    "sale_untaxed": sale["untaxed"],
                    "sale_tax": sale["tax"],
                    "sale_total": sale["total"],
                    "sale_currency": sale["currency_name"],
                    "sale_is_estimated": sale["is_estimated"],
                    "vendor": "",
                    "po": "",
                    "bill": "",
                    "bill_ncf": "",
                    "bill_date": False,
                    "bill_untaxed": 0.0,
                    "bill_tax": 0.0,
                    "bill_total": 0.0,
                    "bill_currency": "",
                    "bill_residual": 0.0,
                    "payment_state": "",
                    "allocated_cost": 0.0,
                    "margin_row": sale["untaxed"],
                    "margin_pct_row": 100.0 if sale["untaxed"] else 0.0,
                    "relation_state": _("Venta sin costos"),
                    "validated_by": "",
                    "approved_by": "",
                    "kind": "sale_only",
                }
            )
        return rows, sale["untaxed"], sale["tax"], sale["total"]

    @api.model
    def _paired_rows(self, tx):
        op = self._operation_summary(tx)
        left = [
            {
                "partner": c["vendor"],
                "name": c["bill"] or c["po"],
                "ncf": c["ncf"],
                "untaxed": c["untaxed"],
                "tax": c["tax"],
                "total": c["total"],
                "po": c["po"],
                "payment_state": c["payment_state"],
            }
            for c in op["costs"]
        ]
        right = []
        s = op["sale"]
        if s["untaxed"] or s["invoice_label"] or tx.sale_order_ids:
            right.append(
                {
                    "partner": s["customer"],
                    "name": s["invoice_label"],
                    "ncf": s["ncf"],
                    "untaxed": s["untaxed"],
                    "tax": s["tax"],
                    "total": s["total"],
                    "payment_state": s["payment_state"],
                    "is_estimated": s["is_estimated"],
                    "tax_label": s["tax_label"],
                }
            )
        n = max(len(left), len(right), 1)
        pairs = []
        for i in range(n):
            l = left[i] if i < len(left) else False
            r = right[0] if right else False
            pairs.append((l, r, i > 0))
        return pairs, left, right

    # ------------------------------------------------------------------
    # XLSX redesigned
    # ------------------------------------------------------------------
    def _build_xlsx_bytes(self):
        self.ensure_one()
        try:
            import xlsxwriter
        except ImportError as exc:
            raise UserError(_("La librería xlsxwriter no está disponible en el servidor.")) from exc

        summary = self._general_summary()
        ops = summary["operations"]

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        fmt_title = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#1F4E79"})
        fmt_meta = workbook.add_format({"italic": True, "font_color": "#444444"})
        fmt_head = workbook.add_format(
            {"bold": True, "bg_color": "#1F4E79", "font_color": "white", "border": 1}
        )
        fmt_money = workbook.add_format({"num_format": "#,##0.00", "border": 1})
        fmt_text = workbook.add_format({"border": 1})
        fmt_pct = workbook.add_format({"num_format": "0.00", "border": 1})
        fmt_ok = workbook.add_format({"num_format": "#,##0.00", "border": 1, "bg_color": "#E8F5E9"})
        fmt_low = workbook.add_format({"num_format": "#,##0.00", "border": 1, "bg_color": "#FFF8E1"})
        fmt_neg = workbook.add_format({"num_format": "#,##0.00", "border": 1, "bg_color": "#FFEBEE"})

        # --- Vista gerencial ---
        shg = workbook.add_worksheet("Vista gerencial")
        shg.write(0, 0, _("Vista gerencial — una fila por venta consolidada"), fmt_title)
        shg.write(1, 0, _("Operaciones: %s") % self._report_scope_label(), fmt_meta)
        gh = [
            _("Venta #"),
            _("Cliente"),
            _("Factura/venta"),
            _("Total costos"),
            _("Venta sin ITBIS"),
            _("Margen"),
            _("Margen %"),
            _("Estado"),
            _("Moneda"),
        ]
        for col, h in enumerate(gh):
            shg.write(2, col, h, fmt_head)
        row = 3
        for op in ops:
            s = op["sale"]
            mfmt = {"positive": fmt_ok, "low": fmt_low, "negative": fmt_neg}.get(
                op["margin_band"], fmt_money
            )
            vals = [
                op.get("sale_number") or "",
                s.get("customer") or "",
                op.get("sale_doc") or s.get("invoice_label") or "",
                op.get("cost_untaxed") or 0.0,
                s.get("untaxed") or 0.0,
                op.get("margin") or 0.0,
                op.get("margin_pct") or 0.0,
                op.get("margin_label") or op.get("status") or "",
                s.get("currency_name") or "",
            ]
            for col, val in enumerate(vals):
                if col in (3, 4, 5):
                    shg.write(row, col, val, mfmt if col == 5 else fmt_money)
                elif col == 6:
                    shg.write(row, col, val, fmt_pct)
                else:
                    shg.write(row, col, val, fmt_text)
            row += 1
        for col, width in enumerate([8, 28, 32, 14, 14, 14, 10, 16, 10]):
            shg.set_column(col, col, width)

        # --- Costos relacionados ---
        shc = workbook.add_worksheet("Costos relacionados")
        ch = [
            _("Venta #"),
            _("Cliente"),
            _("Proveedor"),
            _("OC"),
            _("Factura proveedor"),
            _("Costo sin ITBIS"),
            _("Moneda"),
            _("Pago"),
            _("Saldo"),
            _("Cobro cliente"),
            _("Saldo cliente"),
        ]
        for col, h in enumerate(ch):
            shc.write(0, col, h, fmt_head)
        row = 1
        for op in ops:
            s = op["sale"]
            for c in op.get("costs") or []:
                residual = c.get("residual_display")
                if residual is False:
                    residual = ""
                elif residual is None:
                    residual = abs(c.get("residual") or 0.0)
                sale_res = s.get("residual_display")
                if sale_res is False:
                    sale_res = ""
                vals = [
                    op.get("sale_number") or "",
                    s.get("customer") or "",
                    c.get("vendor") or "",
                    c.get("po") or "",
                    c.get("bill") or c.get("label") or "",
                    c.get("untaxed") or 0.0,
                    c.get("currency_name") or "",
                    c.get("payment_badge") or c.get("payment_state") or "",
                    residual if residual != "" else "",
                    s.get("collection_badge") or s.get("payment_state") or "",
                    sale_res if sale_res is not False and sale_res is not None else "",
                ]
                for col, val in enumerate(vals):
                    if col in (5, 8, 10) and val != "":
                        shc.write(row, col, val, fmt_money)
                    else:
                        shc.write(row, col, val, fmt_text)
                row += 1
        for col, width in enumerate([8, 22, 22, 12, 16, 14, 8, 12, 12, 16, 12]):
            shc.set_column(col, col, width)

        # --- Resumen ---
        sh = workbook.add_worksheet("Resumen")
        sh.write(0, 0, _("RESUMEN GENERAL — Detalle de Costos vs Ventas"), fmt_title)
        sh.write(1, 0, _("Período: %s al %s") % (self.date_from, self.date_to), fmt_meta)
        companies = self.company_ids or self.company_id
        sh.write(2, 0, _("Compañías incluidas: %s") % ", ".join(companies.mapped("name")), fmt_meta)
        sh.write(
            3,
            0,
            _("Operaciones: %s | Generado: %s | Usuario: %s")
            % (self._report_scope_label(), fields.Datetime.now(), self.env.user.name),
            fmt_meta,
        )
        headers = [_("Indicador"), _("Moneda"), _("Importe")]
        for col, h in enumerate(headers):
            sh.write(5, col, h, fmt_head)
        r = 6
        sh.write(r, 0, _("Total de ventas consolidadas"), fmt_text)
        sh.write(r, 2, summary.get("sale_count", summary["tx_count"]), fmt_text)
        r += 1
        for cur, bucket in summary["by_currency"].items():
            for label, key in [
                (_("Total de ventas sin ITBIS"), "sale_untaxed"),
                (_("ITBIS total de ventas"), "sale_tax"),
                (_("Total facturado a clientes"), "sale_total"),
                (_("Total de costos sin ITBIS"), "cost_untaxed"),
                (_("ITBIS total de costos"), "cost_tax"),
                (_("Total facturado por proveedores"), "cost_total"),
                (_("Margen total en dinero"), "margin"),
            ]:
                sh.write(r, 0, label, fmt_text)
                sh.write(r, 1, cur, fmt_text)
                sh.write(r, 2, bucket[key], fmt_money)
                r += 1
            pct = (
                (bucket["margin"] / (bucket.get("sale_confirmed") or 0.0) * 100.0)
                if bucket.get("sale_confirmed")
                else 0.0
            )
            sh.write(r, 0, _("Margen total % (sobre operaciones completas)"), fmt_text)
            sh.write(r, 1, cur, fmt_text)
            sh.write(r, 2, pct, fmt_pct)
            r += 1
            for label, key in [
                (_("Ventas posted completas"), "sale_confirmed"),
                (_("Ventas sin costo (pendiente de costeo)"), "sale_without_cost"),
                (_("Ventas estimadas no facturadas"), "sale_estimated"),
                (_("Costos sin venta"), "cost_without_sale"),
            ]:
                sh.write(r, 0, label, fmt_text)
                sh.write(r, 1, cur, fmt_text)
                sh.write(r, 2, bucket.get(key) or 0.0, fmt_money)
                r += 1
            r += 1
        for label, key in [
            (_("Operaciones con margen positivo"), "positive"),
            (_("Operaciones con margen bajo"), "low"),
            (_("Operaciones con margen negativo"), "negative"),
            (_("Ventas sin costos"), "sales_wo_cost"),
            (_("Compras pendientes de factura"), "pending_po"),
            (_("Operaciones pendientes de revisión"), "pending_review"),
            (_("Facturas proveedor"), "bill_count"),
            (_("Proveedor pendientes"), "bill_pending"),
            (_("Proveedor pagadas"), "bill_paid"),
            (_("Proveedor parciales"), "bill_partial"),
            (_("Proveedor en proceso"), "bill_in_payment"),
        ]:
            sh.write(r, 0, label, fmt_text)
            sh.write(r, 2, summary.get(key, 0), fmt_text)
            r += 1
        sh.write(r, 0, _("Saldo por pagar proveedores"), fmt_text)
        sh.write(r, 2, summary.get("vendor_residual") or 0.0, fmt_money)
        r += 2
        # CxP compacta del reporte
        sh.write(r, 0, _("CUENTAS POR PAGAR DEL REPORTE"), fmt_title)
        r += 1
        for col, h in enumerate(
            [_("Proveedor"), _("Facturas"), _("Total"), _("Pagado"), _("Saldo")]
        ):
            sh.write(r, col, h, fmt_head)
        r += 1
        for cx in summary.get("cxp_rows") or []:
            sh.write(r, 0, cx.get("vendor") or "", fmt_text)
            sh.write(r, 1, cx.get("count") or 0, fmt_text)
            sh.write(r, 2, cx.get("total") or 0.0, fmt_money)
            sh.write(r, 3, cx.get("paid") or 0.0, fmt_money)
            sh.write(r, 4, cx.get("residual") or 0.0, fmt_money)
            r += 1
        sh.set_column(0, 0, 44)
        sh.set_column(1, 1, 12)
        sh.set_column(2, 2, 16)
        sh.set_column(3, 3, 14)
        sh.set_column(4, 4, 14)

        # --- Operaciones (compat) ---
        sh2 = workbook.add_worksheet("Operaciones")
        op_headers = [
            "Venta #",
            "Empresa",
            "Cliente",
            "Documento venta",
            "Tipo documento",
            "Fecha",
            "Subtotal venta",
            "ITBIS venta",
            "Total venta",
            "Costos sin ITBIS",
            "Margen",
            "Margen %",
            "Estado",
            "Moneda",
            "MTX (técnico)",
        ]
        for col, h in enumerate(op_headers):
            sh2.write(0, col, h, fmt_head)
        sh2.freeze_panes(1, 0)
        row = 1
        for op in ops:
            s = op["sale"]
            mfmt = {"positive": fmt_ok, "low": fmt_low, "negative": fmt_neg}.get(
                op["margin_band"], fmt_money
            )
            vals = [
                op.get("sale_number") or "",
                op["company"].name if op.get("company") else "",
                s["customer"],
                op.get("sale_doc") or s["invoice_label"],
                s.get("document_kind") or "",
                str(s["date"] or ""),
                s["untaxed"],
                s["tax"],
                s["total"],
                op["cost_untaxed"],
                op["margin"],
                op["margin_pct"],
                op.get("margin_label") or op.get("status") or "",
                s.get("currency_name") or "",
                op.get("tx_number") or "",
            ]
            for col, val in enumerate(vals):
                if col in (6, 7, 8, 9, 10):
                    sh2.write(row, col, val, mfmt if col == 10 else fmt_money)
                elif col == 11:
                    sh2.write(row, col, val, fmt_pct)
                else:
                    sh2.write(row, col, val, fmt_text)
            row += 1
        for col, width in enumerate([8, 16, 24, 28, 16, 12, 12, 12, 12, 12, 12, 10, 14, 8, 18]):
            sh2.set_column(col, col, width)

        # --- Detalle de costos (fiscal) ---
        sh3 = workbook.add_worksheet("Detalle de costos")
        d_headers = [
            "Venta #",
            "Cliente",
            "Proveedor",
            "OC",
            "Factura proveedor",
            "NCF",
            "Fecha",
            "Subtotal costo",
            "ITBIS costo",
            "Total costo",
            "Saldo",
            "Estado pago",
            "Moneda",
        ]
        for col, h in enumerate(d_headers):
            sh3.write(0, col, h, fmt_head)
        sh3.freeze_panes(1, 0)
        row = 1
        for op in ops:
            s = op["sale"]
            for c in op["costs"]:
                vals = [
                    op.get("sale_number") or "",
                    s["customer"],
                    c["vendor"],
                    c["po"],
                    c["bill"] or c.get("label") or "",
                    c.get("ncf") or "",
                    str(c.get("date") or ""),
                    c["untaxed"],
                    c["tax"],
                    c["total"],
                    c.get("residual") or 0.0,
                    c.get("payment_state") or "",
                    c.get("currency_name") or "",
                ]
                for col, val in enumerate(vals):
                    if col in (7, 8, 9, 10):
                        sh3.write(row, col, val, fmt_money)
                    else:
                        sh3.write(row, col, val, fmt_text)
                row += 1
        for col, width in enumerate([8, 22, 22, 12, 16, 14, 12, 12, 12, 12, 10, 14, 8]):
            sh3.set_column(col, col, width)

        # --- Pendientes ---
        sh4 = workbook.add_worksheet("Pendientes")
        for col, h in enumerate([_("Tipo"), _("Venta #"), _("Detalle"), _("Margen")]):
            sh4.write(0, col, h, fmt_head)
        row = 1
        for op in ops:
            if not op["costs"]:
                sh4.write(row, 0, _("Venta sin costos"), fmt_text)
                sh4.write(row, 1, op.get("sale_number") or "", fmt_text)
                sh4.write(row, 2, op["sale"]["customer"], fmt_text)
                sh4.write(row, 3, op["margin"], fmt_money)
                row += 1
            if op["margin"] < 0 and not op.get("margin_pending_rate"):
                sh4.write(row, 0, _("Margen negativo"), fmt_text)
                sh4.write(row, 1, op.get("sale_number") or "", fmt_text)
                sh4.write(row, 2, op["sale"]["customer"], fmt_text)
                sh4.write(row, 3, op["margin"], fmt_neg)
                row += 1
            if op.get("margin_pending_rate"):
                sh4.write(row, 0, _("Pendiente por tasa"), fmt_text)
                sh4.write(row, 1, op.get("sale_number") or "", fmt_text)
                sh4.write(row, 2, op["sale"]["customer"], fmt_text)
                sh4.write(row, 3, 0, fmt_money)
                row += 1
        sh4.set_column(0, 0, 22)
        sh4.set_column(1, 1, 10)
        sh4.set_column(2, 2, 36)
        sh4.set_column(3, 3, 14)

        workbook.close()
        content = output.getvalue()
        return content

    def _generate_xlsx_bytes(self):
        self.ensure_one()
        return self._build_xlsx_bytes()

    def action_generate_xlsx(self):
        self.ensure_one()
        content = self._build_xlsx_bytes()
        filename = "detalle_costos_vs_ventas_%s_%s.xlsx" % (self.date_from, self.date_to)
        self.write(
            {
                "export_file": base64.b64encode(content),
                "export_filename": filename,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": (
                "/web/content/?model=purchase.sale.cost.vs.sale.report&id=%s"
                "&field=export_file&filename_field=export_filename&download=true"
                % self.id
            ),
            "target": "self",
        }
