# CHANGELOG — justech_vendor_bill_po_control

## 19.0.3.6.2 — Prod release: dual Confirmar + forward-only policy + approve ACL

- Odoo 19 form ships two header `action_post` buttons (`Post` + `Confirm`); xpath patches both.
- `vendor_bill_approval_effective_from` + `vendor_bill_legacy_exempt` (technical): policy applies only forward.
- No historical backfill of approvals/activities; posted/draft pre-effective keep original flow.
- Approve ACL message + self-approval controls (`vendor_bill_allow_self_approval`); Accounting Admin / system contingency.
- `post_init_hook` + migration `19.0.3.6.2` stamp effective datetime idempotently.

## 19.0.3.6.1 — Posted PO bill allows payment (DEV)

- `_justech_is_financially_approved`: treat posted vendor bills with valid OC (or exception) as financially approved.
- `action_post` on PO path sets approval `approved` when still draft under strict mode.

## 19.0.3.6.0 — Vendor Bill UX Final PASS (DEV)

- Alerta funcional cuando la aprobación no puede contabilizar por datos fiscales incompletos.
- Mensaje orienta a completar NCF/tipo/fecha/diario/etc. y pulsar Confirmar (sin nueva aprobación).
- UAT UI completo + evidencias en `docs/vendor_bill_po_final_flow/ux_final_pass/`.
- Sin cambios a la lógica OC / aprobación / auto-post / menús.

## 19.0.3.5.0 — Vendor Bill UX Final (DEV)

- Con OC válida: Confirmar estándar (`action_post`), sin aprobación.
- Sin OC: solo **Enviar a aprobación**; Confirmar oculto.
- Al aprobar: clasificación automática + `action_post()` automático.
- Rechazo: borrador editable + motivo + chatter.
- Bandeja única: Contabilidad → Proveedores → Facturas pendientes de aprobación.
- Menús obsoletos desactivados: Mis pendientes / Aprobadas pendientes de contabilizar.
- Filtros: Pendientes, Aprobadas, Rechazadas, Devueltas.
- Actividades `mail.activity` preparadas para futuro Centro de Trabajo.
- Producción no modificada.
