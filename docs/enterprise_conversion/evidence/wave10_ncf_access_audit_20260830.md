# Auditoría `_check_access` / API Odoo 19

`ODOO19_CHECK_ACCESS_SIGNATURE = def _check_access(self, operation: str) -> tuple[Self, Callable] | None`

`check_access(self, operation: str) -> None` llama a `_check_access(operation)` y lanza la factory.

| MODULE | FILE | CLASS | METHOD | CURRENT_SIGNATURE | ODOO19_EXPECTED_SIGNATURE | COMPATIBLE | ACTION |
|---|---|---|---|---|---|---|---|
| justech_l10n_do_ncf | wizards/ncf_migration_wizard.py | JustechDoNcfMigrationWizard | `_check_access` | era `(self)` | `(self, operation)` | NO → SÍ | hotfix: super + grupos fiscales |
| justech_l10n_do_ncf | wizards/ncf_reconcile_wizard.py | JustechDoNcfReconcileWizard | `_check_access` | era `(self)` | `(self, operation)` | NO → SÍ | hotfix: super + grupos fiscales |
| justech_l10n_do_ncf | wizards/ncf_void_wizard.py | JustechDoNcfVoidWizard | — | no override | — | SÍ | none |
| justech_purchase_sale_margin_control | models/*.py | sale/purchase/move | `_search` | `(self, domain, ..., **kwargs)` | Odoo 19 `_search` + kwargs | SÍ | none |
| resto custom (staging scan) | — | — | `_check_access` / `check_access` | no hay más overrides | — | SÍ | none |

`ROOT_CAUSE_CONFIRMED = YES` — override sin `operation`; Odoo 19 llama `_check_access(operation)` al abrir el wizard (`create`).
