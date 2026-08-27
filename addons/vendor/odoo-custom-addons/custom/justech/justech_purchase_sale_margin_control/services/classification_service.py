# -*- coding: utf-8 -*-
from odoo import api, models


class PurchaseSaleClassificationService(models.AbstractModel):
    """Suggests a cost_usage_type for a purchase.order.line based on the audit
    approved rules:

    - Linked (directly or by trace) to a sale order line -> resale_direct
    - Stockable product with no sale link yet -> inventory_pending
      (never administrative_expense: rule "stock without sale = inventory_pending")
    - Service/expense product with no sale link, posted to an expense account
      not tied to inventory -> administrative_expense
    - Product flagged as an asset category -> asset
    - Product used only for internal consumption (no resale, no stock) ->
      internal_service
    - Ambiguous signals (partially linked, partially not) -> mixed
    - Nothing applies -> not_sales_related
    """

    _name = "purchase.sale.classification.service"
    _description = "Servicio de clasificación de costos compra-venta"

    @api.model
    def suggest_cost_usage_type(self, purchase_line):
        """Return a tuple (cost_usage_type, confidence, reason)."""
        if not purchase_line or not purchase_line.product_id:
            return "not_sales_related", 30, "sin_producto"

        product = purchase_line.product_id
        rules = self.env["purchase.sale.reconciliation.rule"].get_classification_rules(
            purchase_line.company_id or self.env.company
        )
        for rule in rules:
            if rule.matches_purchase_line(purchase_line) and rule.cost_usage_type:
                return rule.cost_usage_type, max(rule.min_confidence, 70), "regla:%s" % rule.name

        has_sale_link = bool(
            getattr(purchase_line, "sale_line_id", False)
            or self.env["purchase.sale.cost.link"].search_count(
                [
                    ("purchase_line_id", "=", purchase_line.id),
                    ("sale_id", "!=", False),
                    ("state", "in", ("suggested", "confirmed")),
                ]
            )
        )
        if has_sale_link:
            return "resale_direct", 90, "linea_venta_detectada"

        is_stockable = bool(getattr(product, "is_storable", False))

        if is_stockable:
            # Rule: stock purchased with no sale yet is pending inventory,
            # never administrative expense.
            return "inventory_pending", 75, "producto_almacenable_sin_venta"

        if product.type == "service":
            categ_name = (product.categ_id.name or "").lower()
            if any(token in categ_name for token in ("activo", "asset", "fijo")):
                return "asset", 60, "categoria_activo"
            if any(
                token in categ_name
                for token in ("interno", "internal", "soporte", "mantenimiento")
            ):
                return "internal_service", 55, "categoria_servicio_interno"
            return "administrative_expense", 65, "servicio_sin_venta"

        return "not_sales_related", 40, "sin_regla_aplicable"

    @api.model
    def apply_classification(self, purchase_line, force=False):
        """Write the suggested cost_usage_type unless it was manually confirmed."""
        if purchase_line.classification_is_manual and not force:
            return False
        usage_type, confidence, reason = self.suggest_cost_usage_type(purchase_line)
        purchase_line.write(
            {
                "cost_usage_type": usage_type,
                "classification_confidence": confidence,
                "classification_reason": reason,
            }
        )
        return True
