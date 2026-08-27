# -*- coding: utf-8 -*-
import math

from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    warranty_ids = fields.One2many(
        "justech.warranty", "invoice_id", string="Garantías", copy=False,
    )
    warranty_count = fields.Integer(string="Nº garantías", compute="_compute_warranty_count")
    warranty_unit_ids = fields.One2many(
        "justech.warranty.unit", "invoice_id", string="Unidades de garantía",
        copy=False,
    )
    warranty_unit_count = fields.Integer(
        string="Nº unidades", compute="_compute_warranty_count",
    )

    def _compute_warranty_count(self):
        wty_data = self.env["justech.warranty"]._read_group(
            [("invoice_id", "in", self.ids)], ["invoice_id"], ["__count"]
        )
        wty_map = {move.id: count for move, count in wty_data}
        unit_data = self.env["justech.warranty.unit"]._read_group(
            [("invoice_id", "in", self.ids)], ["invoice_id"], ["__count"]
        )
        unit_map = {move.id: count for move, count in unit_data}
        for move in self:
            move.warranty_count = wty_map.get(move.id, 0)
            move.warranty_unit_count = unit_map.get(move.id, 0)

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted._generate_warranties()
        return posted

    def _generate_warranties(self):
        """Genera una garantía por línea con garantía + N unidades de garantía.

        RC6.2:
          * Idempotente por `invoice_line_id`.
          * Cantidad de unidades = ``max(warranty_expected_units, floor(quantity), 1)``.
          * Seriales planificados (uno por línea de texto) se aplican en orden a
            las unidades; si no hay serial, la unidad queda `pending_serial`.
          * No requiere ``stock.picking`` ni crea ``stock.lot`` automáticamente.
        """
        Warranty = self.env["justech.warranty"].sudo()
        WarrantyUnit = self.env["justech.warranty.unit"].sudo()
        for move in self:
            if move.move_type != "out_invoice" or move.state != "posted":
                continue
            for line in move.invoice_line_ids:
                product = line.product_id
                if not product or line.display_type in ("line_section", "line_note"):
                    continue
                if not line.warranty_apply or line.warranty_months <= 0 or line.quantity <= 0:
                    continue

                wty_type = line.warranty_type_id
                sale_line = line.sale_line_ids[:1]
                sale_order = sale_line.order_id if sale_line else self.env["sale.order"]
                partner = move.partner_id
                start_date = move.invoice_date or fields.Date.context_today(move)
                vendor = line.warranty_vendor_id or (sale_line.warranty_vendor_id if sale_line else False)
                planned_units = max(
                    int(line.warranty_expected_units or 0),
                    int(math.floor(line.quantity or 0)),
                    1,
                )
                planned_serials = line._parse_planned_serials()

                warranty = Warranty.search(
                    [("invoice_line_id", "=", line.id)], limit=1
                )
                if not warranty:
                    warranty = Warranty.create(
                        {
                            "partner_id": partner.id,
                            "vendor_id": vendor.id if vendor else False,
                            "product_id": product.id,
                            "quantity": planned_units,
                            "warranty_months": line.warranty_months,
                            "type_id": wty_type.id if wty_type else False,
                            "warranty_type": wty_type.kind if wty_type else "store",
                            "date_start": start_date,
                            "invoice_id": move.id,
                            "invoice_line_id": line.id,
                            "sale_order_id": sale_order.id if sale_order else False,
                            "company_id": move.company_id.id,
                            "note": line.warranty_notes or False,
                            "state": "active",
                        }
                    )

                existing_units = warranty.unit_ids
                missing = planned_units - len(existing_units)
                if missing <= 0:
                    continue

                start_number = (
                    max(existing_units.mapped("unit_number") or [0]) + 1
                    if existing_units
                    else 1
                )
                offset = len(existing_units)
                unit_vals_list = []
                for idx in range(missing):
                    unit_index = offset + idx
                    unit_number = start_number + idx
                    planned = (
                        planned_serials[unit_index]
                        if unit_index < len(planned_serials)
                        else None
                    )
                    serial_manufacturer = ""
                    unit_note = False
                    if planned:
                        serial_manufacturer = (
                            planned.get("serial_manufacturer") or ""
                        ).strip()
                        unit_note = planned.get("note") or False
                    unit_vals_list.append(
                        {
                            "warranty_id": warranty.id,
                            "company_id": move.company_id.id,
                            "product_id": product.id,
                            "product_description": line.name or product.display_name,
                            "partner_id": partner.id,
                            "vendor_id": vendor.id if vendor else False,
                            "unit_number": unit_number,
                            "serial_manufacturer": serial_manufacturer or False,
                            "serial_state": "confirmed" if serial_manufacturer else "pending",
                            "sale_order_id": sale_order.id if sale_order else False,
                            "sale_line_id": sale_line.id if sale_line else False,
                            "invoice_id": move.id,
                            "invoice_line_id": line.id,
                            "customer_warranty_months": line.warranty_months,
                            "customer_date_start": start_date,
                            "delivery_mode": "pending",
                            "state": "active" if serial_manufacturer else "pending_serial",
                            "note": unit_note,
                        }
                    )
                if unit_vals_list:
                    WarrantyUnit.create(unit_vals_list)

                # Si al menos una unidad quedó pendiente de serial, el header
                # refleja ese estado (permite emitir el certificado cuando
                # todas las unidades tengan serial).
                if warranty.unit_ids and any(
                    u.state == "pending_serial" for u in warranty.unit_ids
                ):
                    if warranty.state == "active":
                        warranty.state = "pending_serial"
        return True

    def action_view_warranties(self):
        self.ensure_one()
        return {
            "name": _("Garantías"),
            "type": "ir.actions.act_window",
            "res_model": "justech.warranty",
            "view_mode": "list,form",
            "domain": [("invoice_id", "=", self.id)],
            "context": {"default_invoice_id": self.id, "default_partner_id": self.partner_id.id},
        }

    def action_view_warranty_units(self):
        self.ensure_one()
        return {
            "name": _("Unidades de garantía"),
            "type": "ir.actions.act_window",
            "res_model": "justech.warranty.unit",
            "view_mode": "list,form",
            "domain": [("invoice_id", "=", self.id)],
            "context": {"default_invoice_id": self.id},
        }
