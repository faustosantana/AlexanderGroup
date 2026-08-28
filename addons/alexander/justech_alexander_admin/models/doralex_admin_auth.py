import hashlib
import hmac
import logging
import os

from odoo import api, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

ENV_HASH = "DORALEX_ADMIN_KEY_HASH"
ENV_HASH_ALT = "JUSTECH_ADMIN_KEY_HASH"
ENV_HASH_FILE = "DORALEX_ADMIN_KEY_HASH_FILE"
DEFAULT_HASH_FILE = "/opt/doralex/dev/secrets/doralex_admin_key.hash"
ICP_HASH = "doralex.admin_key_hash"
SCOPE = "admin"


class JustechAdminAccessServiceDoralex(models.AbstractModel):
    _inherit = "justech.admin.access.service"

    @api.model
    def user_has_key(self, user=None, company=None):
        if super().user_has_key(user=user, company=company):
            return True
        return self.env["doralex.admin.auth.service"].shared_hash_configured()

    @api.model
    def open_session(self, admin_key, scope=None):
        access = self.get_user_access()
        doralex = self.env["doralex.admin.auth.service"]
        if (not access or not access.has_key) and doralex._verify_shared(admin_key):
            access = self.ensure_user_access()
            access.set_key_hash(admin_key)
        return super().open_session(admin_key, scope=scope)


class DoralexAdminAuthService(models.AbstractModel):
    _name = "doralex.admin.auth.service"
    _description = "Autenticación Administración Doralex"

    @api.model
    def _justech(self):
        return self.env["justech.admin.access.service"]

    @api.model
    def _read_hash_file(self, path):
        try:
            if not path or not os.path.isfile(path):
                return ""
            with open(path, "rb") as handle:
                return handle.read().decode("utf-8").strip()
        except OSError:
            _logger.info("Doralex admin hash file not readable")
            return ""

    @api.model
    def _shared_hashes(self):
        hashes = []
        icp = self.env["ir.config_parameter"].sudo()
        for key in (ICP_HASH, "justech_modules.admin_key_hash"):
            value = (icp.get_param(key) or "").strip()
            if value:
                hashes.append(value)
        for env_key in (ENV_HASH, ENV_HASH_ALT):
            value = (os.environ.get(env_key) or "").strip()
            if value:
                hashes.append(value)
        path = os.environ.get(ENV_HASH_FILE) or DEFAULT_HASH_FILE
        file_hash = self._read_hash_file(path)
        if file_hash:
            hashes.append(file_hash)
        return hashes

    @api.model
    def shared_hash_configured(self):
        return bool(self._shared_hashes())

    @api.model
    def _hash_plain(self, plain):
        pepper = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("justech_modules.admin_key_pepper", "justech-admin-pepper-v1")
        )
        payload = f"{pepper}:{plain.strip()}".encode()
        return hashlib.sha256(payload).hexdigest()

    @api.model
    def _verify_shared(self, plain):
        if not plain:
            return False
        candidate = self._hash_plain(plain)
        for stored in self._shared_hashes():
            if hmac.compare_digest(candidate, stored):
                return True
        return False

    @api.model
    def key_is_configured(self):
        justech = self._justech()
        return bool(justech.user_has_key()) or self.shared_hash_configured()

    @api.model
    def is_session_valid(self):
        return bool(self._justech().is_session_valid(scope=SCOPE))

    @api.model
    def require_session(self):
        justech = self._justech()
        justech.require_justech_settings_access()
        if self.is_session_valid():
            return True
        raise AccessError(
            "Debe reautenticarse con la clave administrativa para Administración Doralex."
        )

    @api.model
    def open_session(self, admin_key):
        justech = self._justech()
        justech.require_justech_settings_access()
        if justech.user_has_key():
            return justech.open_session(admin_key, scope=SCOPE)
        if self._verify_shared(admin_key):
            access = justech.ensure_user_access()
            if not access.has_key:
                access.set_key_hash(admin_key)
            return justech.open_session(admin_key, scope=SCOPE)
        raise UserError("Clave administrativa inválida.")

    @api.model
    def open_protected(self, action_xmlid, name=None):
        justech = self._justech()
        justech.require_justech_settings_access()
        if not self.key_is_configured():
            return justech._action_setup_key_required(action_xmlid, SCOPE)
        if self.is_session_valid():
            return justech._resolve_action(action_xmlid)
        return justech._protected_wizard_action(
            SCOPE,
            name or "Administración Doralex",
            target_action_xmlid=action_xmlid,
        )

    @api.model
    def action_open_dashboard(self):
        return self.open_protected(
            "justech_alexander_admin.action_doralex_admin_dashboard",
            "Estado del sistema",
        )

    @api.model
    def action_open_modules(self):
        return self.open_protected(
            "justech_alexander_admin.action_doralex_admin_dashboard",
            "Módulos Justech",
        )

    @api.model
    def action_open_diagnosis(self):
        return self.open_protected(
            "justech_alexander_admin.action_doralex_admin_dashboard",
            "Diagnóstico",
        )
