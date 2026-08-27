from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _
import re


UAT_PATTERN = re.compile(
    r"(uat|test|ux\s*shot|shot_admin|padr[oó]n|std\b|prueba)",
    re.IGNORECASE,
)

ROLE_HINTS = {
    "uat_admin_fiscal": "Administrador Fiscal",
    "uat_responsable_fiscal": "Responsable Fiscal",
    "uat_usuario_fiscal": "Usuario Fiscal",
    "uat_contador": "Contador / reportes",
    "uat_compras": "Compras / padrón",
    "uat_ventas": "Ventas / padrón",
    "shot_admin": "Administrador (capturas UX)",
}


class ResUsers(models.Model):
    _inherit = "res.users"

    justech_is_test_user = fields.Boolean(
        string="Usuario de prueba Justech",
        compute="_compute_justech_test_flags",
        search="_search_justech_is_test_user",
    )
    justech_test_classification = fields.Selection(
        selection=[
            ("required_temp", "Cuenta de prueba requerida temporalmente"),
            ("evidence", "Cuenta de evidencia"),
            ("obsolete", "Cuenta obsoleta"),
            ("real", "Usuario real"),
        ],
        compute="_compute_justech_test_flags",
        string="Clasificación",
    )
    justech_test_role_label = fields.Char(
        compute="_compute_justech_test_flags",
        string="Rol probado",
    )

    justech_admin_center_role = fields.Selection(
        selection=[
            ("none", "Sin acceso"),
            ("justech_admin", "Administrador Justech"),
        ],
        string="Administración Justech",
        compute="_compute_justech_admin_center_role",
        inverse="_inverse_justech_admin_center_role",
        store=False,
        groups="base.group_system,justech_admin_center.group_justech_admin_center_manager",
    )
    justech_role_explanation = fields.Char(
        compute="_compute_justech_admin_center_role",
        string="Este rol permite",
    )
    justech_fiscal_role_explanation = fields.Char(
        compute="_compute_justech_fiscal_role_explanation",
        string="Este rol permite",
    )
    justech_ecf_role = fields.Selection(
        selection=[
            ("none", "Sin acceso"),
            ("ecf_readonly", "Solo lectura e-CF"),
            ("ecf_operator", "Operador e-CF"),
            ("ecf_responsible", "Responsable e-CF"),
            ("ecf_admin", "Administrador e-CF"),
        ],
        string="Rol e-CF",
        compute="_compute_justech_ecf_role",
        inverse="_inverse_justech_ecf_role",
        store=False,
        groups="base.group_system,justech_admin_center.group_justech_admin_center_manager",
    )
    justech_ecf_role_explanation = fields.Char(
        compute="_compute_justech_ecf_role",
        string="Este rol permite",
    )
    justech_finance_role = fields.Selection(
        selection=[
            ("none", "Sin acceso"),
            ("finance_user", "Usuario Finanzas"),
            ("finance_admin", "Administrador Finanzas"),
        ],
        string="Rol finanzas",
        compute="_compute_justech_finance_role",
        inverse="_inverse_justech_finance_role",
        store=False,
        groups="base.group_system,justech_admin_center.group_justech_admin_center_manager",
    )
    justech_finance_role_explanation = fields.Char(
        compute="_compute_justech_finance_role",
        string="Este rol permite",
    )
    justech_warranty_role = fields.Selection(
        selection=[
            ("none", "Sin acceso"),
            ("warranty_user", "Usuario Garantías"),
            ("warranty_manager", "Administrador Garantías"),
        ],
        string="Rol garantías",
        compute="_compute_justech_warranty_role",
        inverse="_inverse_justech_warranty_role",
        store=False,
        groups="base.group_system,justech_admin_center.group_justech_admin_center_manager",
    )
    justech_warranty_role_explanation = fields.Char(
        compute="_compute_justech_warranty_role",
        string="Este rol permite",
    )
    justech_cap_admin_console = fields.Boolean(
        string="Administrar consola Justech",
        compute="_compute_justech_caps",
        inverse="_inverse_cap_admin_console",
        groups="base.group_system,justech_admin_center.group_justech_admin_center_manager",
    )
    justech_cap_install_modules = fields.Boolean(
        string="Instalar módulos Justech",
        compute="_compute_justech_caps",
        inverse="_inverse_cap_install",
        groups="base.group_system,justech_admin_center.group_justech_admin_center_manager",
    )

    def _compute_justech_test_flags(self):
        for user in self:
            blob = "%s %s" % (user.login or "", user.name or "")
            is_test = bool(UAT_PATTERN.search(blob))
            user.justech_is_test_user = is_test
            if not is_test:
                user.justech_test_classification = "real"
                user.justech_test_role_label = False
                continue
            login = (user.login or "").lower()
            role = "Prueba controlada"
            for key, label in ROLE_HINTS.items():
                if key in login:
                    role = label
                    break
            user.justech_test_role_label = role
            if not user.active:
                user.justech_test_classification = "obsolete"
            elif "shot" in login or "ux" in login:
                user.justech_test_classification = "evidence"
            else:
                user.justech_test_classification = "required_temp"

    def _search_justech_is_test_user(self, operator, value):
        """Dominio estable por login/nombre — evita inconsistencias del compute en search."""
        test_domain = [
            "|",
            "|",
            "|",
            ("login", "ilike", "uat"),
            ("login", "ilike", "shot_"),
            ("name", "ilike", "UAT"),
            ("name", "ilike", "UX Shot"),
        ]
        # Odoo puede usar '=', '!=', 'in', 'not in' sobre booleanos
        truthy = {True, 1, "1", "true", "True"}
        if operator in ("=", "=="):
            want_test = value in truthy
        elif operator in ("!=", "<>"):
            want_test = value not in truthy
        elif operator == "in":
            want_test = bool(set(value or []) & truthy)
        elif operator == "not in":
            want_test = not bool(set(value or []) & truthy)
        else:
            want_test = bool(value)
        if want_test:
            return test_domain
        return ["!"] + test_domain

    def _role_from_groups(self, order):
        """order: list of (code, xmlid, explain) highest privilege first."""
        for code, xmlid, text in order:
            try:
                group = self.env.ref(xmlid)
            except ValueError:
                continue
            if group in self.all_group_ids:
                return code, text
        return "none", "Sin acceso."

    @api.depends_context("uid")
    def _compute_justech_admin_center_role(self):
        for user in self:
            role, explain = user._role_from_groups(
                [
                    (
                        "justech_admin",
                        "justech_admin_center.group_justech_admin_center_manager",
                        "Administrar la consola Justech, productos, empresas autorizadas y diagnósticos.",
                    ),
                ]
            )
            if role == "none":
                explain = "Sin acceso a Administración Justech."
            user.justech_admin_center_role = role
            user.justech_role_explanation = explain

    @api.depends_context("uid")
    def _compute_justech_fiscal_role_explanation(self):
        explanations = {
            "admin": "Administrar Centro Fiscal, NCF, e-CF, padrón, reportes y retenciones.",
            "officer": "Revisar, aprobar y diagnosticar sin cambiar secretos críticos.",
            "user": "Operar y consultar funciones fiscales cotidianas.",
            "none": "Sin acceso fiscal Justech.",
        }
        for user in self:
            role = "none"
            if "justech_fiscal_role" in user._fields:
                role = user.justech_fiscal_role or "none"
            else:
                if user.has_group("justech_fiscal_admin.group_justech_fiscal_admin_manager"):
                    role = "admin"
                elif user.has_group("justech_l10n_do_base.group_justech_do_fiscal_manager"):
                    role = "officer"
                elif user.has_group("justech_l10n_do_base.group_justech_do_fiscal_user"):
                    role = "user"
            user.justech_fiscal_role_explanation = explanations.get(role, explanations["none"])

    @api.depends_context("uid")
    def _compute_justech_ecf_role(self):
        for user in self:
            role, explain = user._role_from_groups(
                [
                    (
                        "ecf_admin",
                        "justech_ecf_core.group_ecf_admin",
                        "Configurar empresas e-CF, certificados, ambientes, asistentes y colas.",
                    ),
                    (
                        "ecf_responsible",
                        "justech_ecf_core.group_ecf_responsible",
                        "Operar y supervisar e-CF; validar sin cambiar secretos críticos.",
                    ),
                    (
                        "ecf_operator",
                        "justech_ecf_core.group_ecf_operator",
                        "Emitir y gestionar documentos e-CF.",
                    ),
                    (
                        "ecf_readonly",
                        "justech_ecf_core.group_ecf_readonly",
                        "Consultar e-CF sin modificar.",
                    ),
                ]
            )
            if role == "none":
                explain = "Sin acceso e-CF."
            user.justech_ecf_role = role
            user.justech_ecf_role_explanation = explain

    @api.depends_context("uid")
    def _compute_justech_finance_role(self):
        for user in self:
            # Finanzas: marcar vía account groups si no hay grupo Justech dedicado.
            role = "none"
            explain = "Sin acceso finanzas Justech (próximo módulo)."
            if user.has_group("account.group_account_manager"):
                role = "finance_admin"
                explain = "Administrar cobros, pagos, tesorería y conciliación."
            elif user.has_group("account.group_account_invoice") or user.has_group(
                "account.group_account_user"
            ):
                role = "finance_user"
                explain = "Operar cobros, pagos y tesorería según permisos contables."
            user.justech_finance_role = role
            user.justech_finance_role_explanation = explain

    @api.depends_context("uid")
    def _compute_justech_warranty_role(self):
        for user in self:
            role, explain = user._role_from_groups(
                [
                    (
                        "warranty_manager",
                        "justech_warranty.group_warranty_manager",
                        "Administrar garantías, roles y parámetros.",
                    ),
                    (
                        "warranty_user",
                        "justech_warranty.group_warranty_user",
                        "Registrar y dar seguimiento a garantías.",
                    ),
                ]
            )
            if role == "none":
                explain = "Sin acceso a Garantías."
            user.justech_warranty_role = role
            user.justech_warranty_role_explanation = explain

    # Campos espejo (compute+inverse) heredados del formulario. La pestaña
    # «Permisos» (Security UX) es la única vía autorizada para mutar grupos.
    _JX_MIRROR_ROLE_FIELDS = (
        "justech_ecf_role",
        "justech_warranty_role",
        "justech_admin_center_role",
        "justech_finance_role",
        "justech_cap_admin_console",
        "justech_cap_install_modules",
    )

    def _jx_refuse_duplicate_role_write(self):
        """Tercera vía de asignación deshabilitada — usar pestaña Permisos."""
        raise UserError(
            _(
                "La asignación de roles e-CF / Garantías / Admin Justech / Finanzas "
                "desde Administración Justech está deshabilitada.\n"
                "Use la pestaña «Permisos» del usuario (escribe directo en group_ids)."
            )
        )

    def _write_exclusive_groups(self, xml_map, selected_code):
        # Conservado por compatibilidad; no debe mutar group_ids.
        self._jx_refuse_duplicate_role_write()

    def _jx_ecf_role_from_groups(self):
        code, _ = self._role_from_groups(
            [
                ("ecf_admin", "justech_ecf_core.group_ecf_admin", ""),
                ("ecf_responsible", "justech_ecf_core.group_ecf_responsible", ""),
                ("ecf_operator", "justech_ecf_core.group_ecf_operator", ""),
                ("ecf_readonly", "justech_ecf_core.group_ecf_readonly", ""),
            ]
        )
        return code

    def _jx_warranty_role_from_groups(self):
        code, _ = self._role_from_groups(
            [
                ("warranty_manager", "justech_warranty.group_warranty_manager", ""),
                ("warranty_user", "justech_warranty.group_warranty_user", ""),
            ]
        )
        return code

    def _jx_admin_center_role_from_groups(self):
        code, _ = self._role_from_groups(
            [
                (
                    "justech_admin",
                    "justech_admin_center.group_justech_admin_center_manager",
                    "",
                ),
            ]
        )
        return code

    def _jx_finance_role_from_groups(self):
        if self.has_group("account.group_account_manager"):
            return "finance_admin"
        if self.has_group("account.group_account_invoice") or self.has_group(
            "account.group_account_user"
        ):
            return "finance_user"
        return "none"

    def _jx_inverse_no_op_or_refuse(self, desired, current):
        """Allow form re-sends that match groups; refuse real role changes."""
        if (desired or "none") == (current or "none"):
            return
        self._jx_refuse_duplicate_role_write()

    def _inverse_justech_ecf_role(self):
        for user in self:
            user._jx_inverse_no_op_or_refuse(
                user.justech_ecf_role, user._jx_ecf_role_from_groups()
            )

    def _inverse_justech_warranty_role(self):
        for user in self:
            user._jx_inverse_no_op_or_refuse(
                user.justech_warranty_role, user._jx_warranty_role_from_groups()
            )

    def _inverse_justech_finance_role(self):
        for user in self:
            user._jx_inverse_no_op_or_refuse(
                user.justech_finance_role, user._jx_finance_role_from_groups()
            )

    def _inverse_justech_admin_center_role(self):
        for user in self:
            user._jx_inverse_no_op_or_refuse(
                user.justech_admin_center_role,
                user._jx_admin_center_role_from_groups(),
            )

    def _compute_justech_caps(self):
        try:
            mgr = self.env.ref("justech_admin_center.group_justech_admin_center_manager")
        except ValueError:
            mgr = self.env["res.groups"]
        for user in self:
            user.justech_cap_admin_console = bool(mgr and mgr in user.all_group_ids) or user.has_group(
                "base.group_system"
            )
            user.justech_cap_install_modules = user.has_group("base.group_system") or user.justech_cap_admin_console

    def _jx_cap_admin_console_from_groups(self):
        try:
            mgr = self.env.ref("justech_admin_center.group_justech_admin_center_manager")
        except ValueError:
            mgr = self.env["res.groups"]
        return bool(mgr and mgr in self.all_group_ids) or self.has_group("base.group_system")

    def _inverse_cap_admin_console(self):
        for user in self:
            desired = bool(user.justech_cap_admin_console)
            current = user._jx_cap_admin_console_from_groups()
            if desired == current:
                continue
            self._jx_refuse_duplicate_role_write()

    def _inverse_cap_install(self):
        for user in self:
            desired = bool(user.justech_cap_install_modules)
            current = user.has_group("base.group_system") or user._jx_cap_admin_console_from_groups()
            if desired == current:
                continue
            self._jx_refuse_duplicate_role_write()

    @api.model_create_multi
    def create(self, vals_list):
        """Strip mirror role fields so CREATE does not trip inverses.

        The web form may still send justech_*_role='none' even when the
        Admin Center block is invisible. Mutating those fields must go
        through Security UX (group_ids), never through these inverses.
        """
        clean = []
        for vals in vals_list:
            vals = dict(vals)
            for fname in self._JX_MIRROR_ROLE_FIELDS:
                vals.pop(fname, None)
            clean.append(vals)
        return super().create(clean)
