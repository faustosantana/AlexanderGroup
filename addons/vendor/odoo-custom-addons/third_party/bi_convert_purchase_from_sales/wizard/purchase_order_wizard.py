
from odoo import api, fields, models, _
from datetime import datetime


class createpurchaseorder(models.TransientModel):
    _name = 'create.purchaseorder'
    _description = "Crear Orden de Compra"

    new_order_line_ids = fields.One2many('getsale.orderdata', 'new_order_line_id', string="Líneas de OC")
    partner_id = fields.Many2one('res.partner', string='Proveedor', required=True)
    date_order = fields.Datetime(string='Fecha de OC', required=True, copy=False, default=fields.Datetime.now)

    @api.model
    def default_get(self, default_fields):
        res = super(createpurchaseorder, self).default_get(default_fields)
        data = self.env['sale.order'].browse(self._context.get('active_ids', []))
        update = []
        for record in data.order_line:
            update.append((0, 0, {
                'product_id': record.product_id.id,
                'product_uom': record.product_uom_id.id,
                'order_id': record.order_id.id,
                'name': record.name,
                'product_qty': record.product_uom_qty,
                'price_unit': record.price_unit,
                'product_subtotal': record.price_subtotal,
                'display_type': record.display_type,
            }))
        res.update({'new_order_line_ids': update})
        return res

    def action_create_purchase_order(self):
        """Crear Orden de Compra desde la Orden de Venta"""
        self.ensure_one()
        res = self.env['purchase.order'].browse(self._context.get('id', []))
        value = []
        so = self.env['sale.order'].browse(self._context.get('active_id'))
        sale_order_name = so.name
        company_id = self.env.company
        if self.partner_id.property_purchase_currency_id :
            currency_id = self.partner_id.property_purchase_currency_id.id
        else:
            currency_id = self.env.company.currency_id.id
        purchase_order = res.create({
            'partner_id': self.partner_id.id,
            'date_order': str(self.date_order),
            'origin': sale_order_name,
            'partner_ref': sale_order_name,
            'currency_id': currency_id
        })
        sale_order = self.env['sale.order'].browse(self._context.get('active_ids', []))
        message = "Orden de Compra creada " + '@' + purchase_order.name
        sale_order.message_post(body=message)
        for data in self.new_order_line_ids:
            if data.product_id and not data.display_type:
                sale_order_name = data.order_id.name
                if not sale_order_name:
                    sale_order_name = so.name
                product_quantity = data.product_qty
                purchase_qty_uom = data.product_uom._compute_quantity(product_quantity, data.product_id.uom_id)
                # determine vendor (real supplier, sharing the same partner as the one from the PO, but with more accurate informations like validity, quantity, ...)
                # Note: one partner can have multiple supplier info for the same product
                supplierinfo = data.product_id._select_seller(
                    partner_id=purchase_order.partner_id,
                    quantity=purchase_qty_uom,
                    date=purchase_order.date_order and purchase_order.date_order.date(),
                    # and purchase_order.date_order[:10],
                    uom_id=data.product_id.uom_id
                )
                fpos = purchase_order.fiscal_position_id
                taxes = fpos.map_tax(data.product_id.supplier_taxes_id)
                if taxes:
                    taxes = taxes.filtered(lambda t: t.company_id.id == company_id.id)
                if not supplierinfo:
                    po_line_uom = data.product_uom or data.product_id.uom_id
                    price_unit = self.env['account.tax']._fix_tax_included_price_company(
                        data.product_id.uom_id._compute_price(data.product_id.standard_price, po_line_uom),
                        data.product_id.supplier_taxes_id,
                        taxes,
                        company_id,
                    )
                    if price_unit and data.order_id.currency_id and data.order_id.company_id.currency_id != data.order_id.currency_id:
                        price_unit = data.order_id.company_id.currency_id._convert(
                            price_unit,
                            data.order_id.currency_id,
                            data.order_id.company_id,
                            self.date_order or fields.Date.today(),
                        )
                # compute unit price
                if supplierinfo:
                    price_unit = self.env['account.tax'].sudo()._fix_tax_included_price_company(supplierinfo.price,
                                                                                                data.product_id.supplier_taxes_id,
                                                                                                taxes, company_id)
                    if purchase_order.currency_id and supplierinfo.currency_id != purchase_order.currency_id:
                        price_unit = supplierinfo.currency_id._convert(price_unit, purchase_order.currency_id,
                                                                    purchase_order.company_id, fields.datetime.today())
                if self.partner_id.property_purchase_currency_id :
                    value.append({
                        'product_id': data.product_id.id,
                        'name': data.name,
                        'product_qty': data.product_qty,
                        'order_id': purchase_order.id,
                        'product_uom_id': data.product_uom.id,
                        'tax_ids': data.product_id.supplier_taxes_id.ids,
                        'date_planned': data.date_planned,
                        'price_unit': price_unit,
                    })
                else:
                    value.append({
                        'product_id': data.product_id.id,
                        'name': data.name,
                        'product_qty': data.product_qty,
                        'order_id': purchase_order.id,
                        'product_uom_id': data.product_uom.id,
                        'tax_ids': data.product_id.supplier_taxes_id.ids,
                        'date_planned': data.date_planned,
                        'price_unit': price_unit,
                    })
            if data.display_type in ['line_section', 'line_note']:
                value.append({
                    'date_planned': data.date_planned,
                    'display_type': data.display_type,
                    'name': data.name,
                    'order_id': purchase_order.id,
                    'product_qty': data.product_qty,
                })
        if value:
            self.env['purchase.order.line'].create(value)
        return purchase_order


class Getsaleorderdata(models.TransientModel):
    _name = 'getsale.orderdata'
    _description = "Obtener datos de orden de venta"

    new_order_line_id = fields.Many2one('create.purchaseorder')

    product_id = fields.Many2one('product.product', string="Producto")
    name = fields.Char(string="Descripción")
    product_qty = fields.Float(string='Cantidad')
    date_planned = fields.Datetime(string='Fecha Programada', default=datetime.today())
    product_uom = fields.Many2one('uom.uom', string='Unidad de Medida')
    order_id = fields.Many2one('sale.order', string='Referencia de Orden', ondelete='cascade', index=True)
    price_unit = fields.Float(string='Precio Unitario', digits='Product Price')
    product_subtotal = fields.Float(string="SubTotal", compute='_compute_total')
    display_type = fields.Selection(selection=[
        ('line_section', "Sección"),
        ('line_note', "Nota"),
    ],
    default=False
    )

    @api.depends('product_qty', 'price_unit')
    def _compute_total(self):
        for record in self:
            record.product_subtotal = record.product_qty * record.price_unit
