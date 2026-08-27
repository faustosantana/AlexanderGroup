# Changelog — justech_quotation_client_dedup

## 19.0.1.0.0

- Inherit `sale.report_saleorder_document` and clear `t-set="address"` so the
  customer is not printed under the company header via `web.address_layout`.
- Preserve the customer box under the Cotización title (`#informations` /
  `customer_info`).
- No changes to `web.external_layout_bubble`, `web.address_layout`, invoices,
  purchases, deliveries, or fiscal reports.
