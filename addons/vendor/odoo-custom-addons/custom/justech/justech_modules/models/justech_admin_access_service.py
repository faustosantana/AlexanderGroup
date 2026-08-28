import hashlib
import secrets

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


class JustechAdminAccessService(models.AbstractModel):
    _name = "justech.admin.access.service"
    _description = "Justech Administrative Access Service"

    SCOPE_PLATFORM = "platform"
    SCOPE_GOVERNANCE = "governance"
    SCOPE_ADMIN = "admin"
    CRITICAL_PLATFORM_MUTATION = "platform_mutation"
    CRITICAL_LICENSE_CHANGE = "license_change"

    # ------------------------------------------------------------------ groups
    @api.model
    def user_is_settings_admin(self, user=None):
        user = user or self.env.user
        return user.has_group("base.group_system")

    @api.model
    def require_settings_admin(self, user=None):
        user = user or self.env.user
        if not self.user_is_settings_admin(user=user):
            raise AccessError(
                "You are not authorized to access Justech configuration."
            )

    @api.model
    def user_can_access_justech_settings(self, user=None):
        user = user or self.env.user
        return self.user_is_settings_admin(user=user) or self.user_is_internal(user=user)

    @api.model
    def require_justech_settings_access(self, user=None):
        user = user or self.env.user
        if not self.with_user(user).user_can_access_justech_settings(user=user):
            raise AccessError(
                "You are not authorized to access Justech configuration."
            )

    @api.model
    def user_is_internal(self, user=None):
        user = user or self.env.user
        internal_groups = [
            "justech_modules.group_justech_internal_admin",
            "justech_modules.group_justech_license_manager",
            "justech_modules.group_justech_support",
            "justech_admin.group_justech_admin_user",
            "hellenia_governance.group_governance_manager",
        ]
        return any(user.has_group(xmlid) for xmlid in internal_groups)

    @api.model
    def require_internal_user(self, user=None):
        if not self.user_is_internal(user=user):
            raise AccessError(
                "You are not authorized for Justech internal administration."
            )

    # ------------------------------------------------------------------ access record
    @api.model
    def get_user_access(self, user=None, company=None):
        user = user or self.env.user
        company = company or self.env.company
        return (
            self.env["justech.admin.access"]
            .sudo()
            .search(
                [
                    ("user_id", "=", user.id),
                    ("company_id", "=", company.id),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )

    @api.model
    def ensure_user_access(self, user=None, company=None):
        user = user or self.env.user
        company = company or self.env.company
        return self.env["justech.admin.access"].ensure_access_shell(user, company=company)

    @api.model
    def user_has_key(self, user=None, company=None):
        access = self.get_user_access(user=user, company=company)
        return bool(access and access.has_key)

    # ------------------------------------------------------------------ session
    @api.model
    def _session_token_param(self, scope):
        return f"justech_admin_session_{scope}"

    @api.model
    def _get_request_ip(self):
        try:
            from odoo.http import request

            if request:
                return request.httprequest.remote_addr
        except Exception:
            pass
        return False

    @api.model
    def _hash_session_token(self, token):
        pepper = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("justech_modules.admin_session_pepper", "justech-session-pepper-v1")
        )
        return hashlib.sha256(f"{pepper}:{token}".encode()).hexdigest()

    @api.model
    def _hash_critical_token(self, token):
        pepper = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("justech_modules.admin_critical_pepper", "justech-critical-pepper-v1")
        )
        return hashlib.sha256(f"{pepper}:{token}".encode()).hexdigest()

    @api.model
    def _session_storage_key(self, scope, user_id=None):
        uid = user_id or self.env.uid
        return f"justech.session.{uid}.{scope}"

    @api.model
    def is_session_valid(self, scope=None):
        scope = scope or self.SCOPE_PLATFORM
        if not self.user_has_key():
            return False
        token = self.env.context.get(self._session_token_param(scope))
        if not token:
            token = self.env["ir.config_parameter"].sudo().get_param(
                self._session_storage_key(scope)
            )
        if not token:
            return False
        token_hash = self._hash_session_token(token)
        session = self.env["justech.admin.session"].find_valid(
            self.env.user, scope, token_hash
        )
        return bool(session)

    @api.model
    def require_session(self, scope=None):
        self.require_justech_settings_access()
        scope = scope or self.SCOPE_PLATFORM
        if not self.user_has_key():
            raise AccessError(
                _("Debe crear una Clave Administrativa Justech antes de continuar.")
            )
        if not self.is_session_valid(scope=scope):
            raise AccessError(self._session_reauth_message(scope))

    @api.model
    def _session_reauth_message(self, scope=None):
        scope = scope or self.SCOPE_PLATFORM
        Session = self.env["justech.admin.session"].sudo()
        if Session.search_count([("user_id", "=", self.env.uid), ("scope", "=", scope)]):
            return _(
                "La sesión administrativa ha expirado. "
                "Introduzca nuevamente la Clave Administrativa para continuar."
            )
        return _("Introduzca la Clave Administrativa Justech para continuar.")

    @api.model
    def verify_key_only(self, admin_key, action="verify"):
        """Verify key for step-up / rotate without opening a session."""
        self.require_justech_settings_access()
        access = self.get_user_access()
        ip = self._get_request_ip()
        if not access or not access.has_key:
            self._audit("verify_key", action, False, ip, {"reason": "not_configured"})
            raise UserError(
                _("Debe crear una Clave Administrativa Justech antes de continuar.")
            )
        ok, reason = access.verify_key(admin_key)
        if not ok:
            self._audit("verify_key", action, False, ip, {"reason": reason})
            if reason == "locked":
                raise UserError(
                    _("Administrative key locked due to failed attempts. Try again later.")
                )
            raise UserError(_("Invalid Justech Administrative Key."))
        self._audit("verify_key", action, True, ip, {"step_up": True})
        return True

    @api.model
    def open_session(self, admin_key, scope=None):
        self.require_justech_settings_access()
        scope = scope or self.SCOPE_PLATFORM
        user = self.env.user
        access = self.get_user_access()
        ip = self._get_request_ip()
        if not access or not access.has_key:
            self._audit("verify_key", scope, False, ip, {"reason": "not_configured"})
            raise UserError(
                _("Debe crear una Clave Administrativa Justech antes de continuar.")
            )
        ok, reason = access.verify_key(admin_key)
        if not ok:
            self._audit("verify_key", scope, False, ip, {"reason": reason})
            if reason == "locked":
                raise UserError(
                    _("Administrative key locked due to failed attempts. Try again later.")
                )
            raise UserError(_("Invalid Justech Administrative Key."))
        session_token = secrets.token_urlsafe(32)
        token_hash = self._hash_session_token(session_token)
        self.env["justech.admin.session"].create_session(user, scope, token_hash, ip)
        self.env["ir.config_parameter"].sudo().set_param(
            self._session_storage_key(scope), session_token
        )
        self._audit("verify_key", scope, True, ip, {"access_level": access.access_level})
        return session_token

    @api.model
    def revoke_all_sessions(self, user=None, scope=None, all_users=False):
        Session = self.env["justech.admin.session"].sudo()
        ICP = self.env["ir.config_parameter"].sudo()
        if all_users:
            Session.search([("active", "=", True)]).write({"active": False})
            for param in ICP.search([("key", "like", "justech.session.%")]):
                param.unlink()
            return True
        user = user or self.env.user
        domain = [("user_id", "=", user.id), ("active", "=", True)]
        if scope:
            domain.append(("scope", "=", scope))
            ICP.set_param(self._session_storage_key(scope, user.id), False)
        else:
            for sc in (self.SCOPE_PLATFORM, self.SCOPE_GOVERNANCE, self.SCOPE_ADMIN):
                ICP.set_param(self._session_storage_key(sc, user.id), False)
        Session.search(domain).write({"active": False})
        return True

    # ------------------------------------------------------------------ critical step-up
    @api.model
    def issue_critical_grant(self, action):
        token = secrets.token_urlsafe(24)
        self.env["justech.admin.critical.grant"].issue(self.env.user, action, token)
        return token

    @api.model
    def consume_critical_grant(self, action, token):
        if not token:
            return False
        return self.env["justech.admin.critical.grant"].consume(
            self.env.user, action, token
        )

    @api.model
    def require_critical_step_up(self, action):
        if self.env.su:
            return
        token = self.env.context.get("justech_critical_token")
        if token and self.consume_critical_grant(action, token):
            return
        raise AccessError(
            "Critical action requires Justech Administrative Key verification."
        )

    @api.model
    def prompt_step_up(self, res_model, res_id, method_name, critical_action):
        return {
            "type": "ir.actions.act_window",
            "name": _("Confirm Administrative Key"),
            "res_model": "justech.admin.stepup.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_res_model": res_model,
                "default_res_id": res_id,
                "default_method_name": method_name,
                "default_critical_action": critical_action,
            },
        }

    # ------------------------------------------------------------------ navigation
    @api.model
    def _resolve_action(self, action_xmlid):
        action_rec = self.env.ref(action_xmlid)
        if action_rec._name == "ir.actions.server":
            return action_rec.run()
        return action_rec.read()[0]

    @api.model
    def _action_setup_key_required(self, target_action_xmlid=None, scope=None):
        ctx = {}
        if target_action_xmlid:
            ctx["default_target_action_xmlid"] = target_action_xmlid
        if scope:
            ctx["default_scope"] = scope
        return {
            "type": "ir.actions.act_window",
            "name": _("Crear Clave Administrativa Justech"),
            "res_model": "justech.admin.key.setup.wizard",
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }

    @api.model
    def _protected_wizard_action(self, scope, title, target_method=None, target_action_xmlid=None):
        ctx = {
            "default_scope": scope,
            "default_prompt_message": self._session_reauth_message(scope),
        }
        if target_method:
            ctx["default_target_method"] = target_method
        if target_action_xmlid:
            ctx["default_target_action_xmlid"] = target_action_xmlid
        return {
            "type": "ir.actions.act_window",
            "name": title or _("Clave Administrativa Justech"),
            "res_model": "justech.admin.key.wizard",
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }

    @api.model
    def open_protected(self, action_xmlid, scope=None, name=None, target_method=None):
        self.require_justech_settings_access()
        scope = scope or self.SCOPE_PLATFORM
        if not self.user_has_key():
            return self._action_setup_key_required(action_xmlid, scope)
        if self.is_session_valid(scope=scope):
            if target_method:
                return getattr(self, target_method)()
            return self._resolve_action(action_xmlid)
        return self._protected_wizard_action(
            scope,
            name,
            target_method=target_method,
            target_action_xmlid=action_xmlid,
        )

    @api.model
    def action_open_module_activation(self):
        return self.open_protected(
            "justech_modules.action_justech_module_activation_wizard",
            self.SCOPE_PLATFORM,
            _("Module Activation"),
        )

    @api.model
    def action_open_licenses(self):
        return self.open_protected(
            "justech_modules.action_justech_license",
            self.SCOPE_PLATFORM,
            _("Licenses"),
        )

    @api.model
    def action_open_features(self):
        return self.open_protected(
            "justech_modules.action_justech_feature",
            self.SCOPE_PLATFORM,
            _("Features"),
        )

    @api.model
    def action_open_modules(self):
        return self.open_protected(
            "justech_modules.action_justech_module",
            self.SCOPE_PLATFORM,
            _("Modules"),
        )

    @api.model
    def action_open_activation_keys(self):
        return self.open_protected(
            "justech_modules.action_justech_activation_key",
            self.SCOPE_PLATFORM,
            _("Activation Keys"),
        )

    @api.model
    def action_open_admin_dashboard(self):
        scope = self.SCOPE_ADMIN
        if not self.user_has_key():
            return self._action_setup_key_required(
                "justech_admin.action_justech_admin_dashboard_launcher", scope
            )
        if self.is_session_valid(scope):
            return self._launch_admin_dashboard()
        return self.open_protected(
            "justech_admin.action_justech_admin_dashboard_launcher",
            scope,
            _("Centro de Control"),
        )

    @api.model
    def _launch_admin_dashboard(self):
        self.require_session(self.SCOPE_ADMIN)
        action = self.env.ref("justech_admin.action_justech_admin_dashboard").read()[0]
        dashboard = self.env["justech.admin.dashboard"].create({})
        action["res_id"] = dashboard.id
        return action

    @api.model
    def action_open_governance_roles(self):
        return self.open_protected(
            "hellenia_governance.action_hellenia_role",
            self.SCOPE_GOVERNANCE,
            _("Roles"),
        )

    @api.model
    def action_open_governance_permissions(self):
        return self.open_protected(
            "hellenia_governance.action_hellenia_permission",
            self.SCOPE_GOVERNANCE,
            _("Permisos"),
        )

    @api.model
    def action_open_governance_user_profiles(self):
        return self.open_protected(
            "hellenia_governance.action_hellenia_user_profile",
            self.SCOPE_GOVERNANCE,
            _("Perfiles de usuario"),
        )

    @api.model
    def action_open_governance_feature_policies(self):
        return self.open_protected(
            "hellenia_governance.action_hellenia_feature_policy",
            self.SCOPE_GOVERNANCE,
            _("Políticas de features"),
        )

    @api.model
    def action_open_governance_menu_policies(self):
        return self.open_protected(
            "hellenia_governance.action_hellenia_menu_policy",
            self.SCOPE_GOVERNANCE,
            _("Políticas de menú"),
        )

    @api.model
    def action_open_governance_audit(self):
        return self.open_protected(
            "hellenia_governance.action_hellenia_governance_audit",
            self.SCOPE_GOVERNANCE,
            _("Auditoría"),
        )

    @api.model
    def action_open_license_audit(self):
        return self.open_protected(
            "justech_modules.action_justech_license_audit",
            self.SCOPE_PLATFORM,
            _("Audit Log"),
        )

    @api.model
    def action_open_commercial_modules(self):
        self.require_session(self.SCOPE_ADMIN)
        return self.env["justech.client.module.control"].action_open()

    @api.model
    def action_open_control_licenses(self):
        self.require_justech_settings_access()
        return self.env["justech.control.licenses"].action_open()

    @api.model
    def _launch_control_security(self):
        self.require_session(self.SCOPE_ADMIN)
        return self.env["justech.control.security"].action_open()

    @api.model
    def _launch_control_audit(self):
        self.require_session(self.SCOPE_ADMIN)
        return self.env["justech.control.audit"].action_open()

    @api.model
    def action_open_control_security(self):
        return self.open_protected(
            "justech_admin.action_justech_control_security_launcher",
            self.SCOPE_ADMIN,
            _("Seguridad Justech"),
            target_method="_launch_control_security",
        )

    @api.model
    def action_open_control_audit(self):
        return self.open_protected(
            "justech_admin.action_justech_control_audit_launcher",
            self.SCOPE_ADMIN,
            _("Auditoría Justech"),
            target_method="_launch_control_audit",
        )

    @api.model
    def action_open_control_integrations(self):
        self.require_session(self.SCOPE_ADMIN)
        return self.env["justech.control.integrations"].action_open()

    @api.model
    def action_open_control_system(self):
        self.require_session(self.SCOPE_ADMIN)
        return self.env["justech.control.system"].action_open()

    @api.model
    def action_open_control_internal_users(self):
        self.require_session(self.SCOPE_ADMIN)
        return self.env["justech.control.internal.users"].action_open()

    @api.model
    def action_open_client_modules(self):
        """Open Módulos del Cliente without key popup (view-only landing)."""
        self.require_justech_settings_access()
        return self.env["justech.client.module.control"].action_open()

    @api.model
    def _audit(self, action, scope, success, ip, details=None):
        self.env["justech.admin.access.audit"].sudo().create(
            {
                "user_id": self.env.uid,
                "company_id": self.env.company.id,
                "action": action,
                "scope": scope,
                "success": success,
                "ip_address": ip,
                "details": details or {},
            }
        )
