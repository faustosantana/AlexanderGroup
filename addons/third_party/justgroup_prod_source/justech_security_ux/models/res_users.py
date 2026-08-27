# -*- coding: utf-8 -*-
"""Pestaña «Permisos» — editor visual directo de res.users.group_ids.

Sin campos espejo jx_lvl_*/jx_cap_*, sin compute/inverse de sincronización.
Cada acción escribe únicamente (4)/(3) sobre los xmlids del control editado.
La matriz nativa de grupos no se muestra en la ficha del usuario.
"""
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.translate import _

from .modules_registry import JX_MODULES


class ResUsers(models.Model):
    _inherit = "res.users"

    # Conservado por compatibilidad de columnas; no se muestra en la UI unificada.
    jx_help = fields.Char(
        string="Ayuda",
        default="Editor visual de grupos Odoo reales (group_ids).",
        readonly=True,
    )

    # ------------------------------------------------------------------ catalog helpers

    @api.model
    def _jx_modules(self):
        return JX_MODULES

    @api.model
    def _jx_module_installed(self, module_name):
        return bool(
            self.env["ir.module.module"]
            .sudo()
            .search([("name", "=", module_name), ("state", "=", "installed")], limit=1)
        )

    @api.model
    def _jx_section_visible(self, section):
        for mod in section.get("modules") or ():
            if not self._jx_module_installed(mod):
                return False
        return True

    @api.model
    def _jx_level_visible(self, level):
        for mod in level.get("modules") or ():
            if not self._jx_module_installed(mod):
                return False
        return True

    @api.model
    def _jx_cap_visible(self, cap):
        for mod in cap.get("modules") or ():
            if not self._jx_module_installed(mod):
                return False
        # Hide caps whose xmlids do not exist in this DB
        for xmlid in cap.get("xmlids") or ():
            if not self.env.ref(xmlid, raise_if_not_found=False):
                return False
        return True

    @api.model
    def _jx_section_by_key(self, key):
        for section in JX_MODULES:
            if section["key"] == key:
                return section
        return None

    @api.model
    def _jx_cap_by_code(self, code):
        for section in JX_MODULES:
            for cap in section.get("caps") or ():
                if cap["code"] == code:
                    return cap, section
        return None, None

    @api.model
    def _jx_ladder_xmlids(self, section):
        xmlids = list(section.get("ladder_extra_xmlids") or ())
        for level in section.get("levels") or ():
            xmlids.extend(level.get("xmlids") or ())
        # unique preserve order
        seen = set()
        out = []
        for xid in xmlids:
            if xid not in seen:
                seen.add(xid)
                out.append(xid)
        return out

    def _jx_assert_can_edit(self):
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "justech_admin_center.group_justech_admin_center_manager"
            )
        ):
            raise AccessError(
                _("Solo Administradores del Sistema o Administradores Justech "
                  "pueden editar la pestaña Permisos.")
            )

    # ------------------------------------------------------------------ public API (UI)

    @api.model
    def jx_catalog(self):
        """Catálogo de UI (labels → xmlids). No escribe nada."""
        self._jx_assert_can_edit()
        catalog = []
        for section in JX_MODULES:
            if not self._jx_section_visible(section):
                continue
            levels = []
            for level in section.get("levels") or ():
                if not self._jx_level_visible(level):
                    continue
                # Skip levels whose xmlids are all missing (except "none")
                xmlids = level.get("xmlids") or ()
                if xmlids and not any(
                    self.env.ref(x, raise_if_not_found=False) for x in xmlids
                ):
                    continue
                levels.append(
                    {
                        "code": level["code"],
                        "label": level["label"],
                        "warning": level.get("warning") or "",
                        "default_caps": list(level.get("default_caps") or ()),
                    }
                )
            caps = []
            for cap in section.get("caps") or ():
                if not self._jx_cap_visible(cap):
                    continue
                caps.append(
                    {
                        "code": cap["code"],
                        "label": cap["label"],
                        "warning": cap.get("warning") or "",
                    }
                )
            catalog.append(
                {
                    "key": section["key"],
                    "label": section["label"],
                    "levels": levels,
                    "caps": caps,
                    "caps_title": section.get("caps_title") or "Adicionales",
                    "notes": list(section.get("notes") or ()),
                }
            )
        return catalog

    @api.model
    def jx_default_permission_state(self):
        """Defaults seguros para CREATE MODE (sin res.users).

        Prefiere nivel «none» cuando existe; si no, el primer nivel del catálogo.
        Caps apagados. No lee otro usuario.
        """
        self._jx_assert_can_edit()
        state = {}
        for section in JX_MODULES:
            if not self._jx_section_visible(section):
                continue
            levels = [
                L
                for L in (section.get("levels") or ())
                if self._jx_level_visible(L)
            ]
            level_code = "none"
            if not any(L["code"] == "none" for L in levels):
                level_code = levels[0]["code"] if levels else "none"
            caps = {}
            for cap in section.get("caps") or ():
                if not self._jx_cap_visible(cap):
                    continue
                caps[cap["code"]] = False
            state[section["key"]] = {"level": level_code, "caps": caps}
        return state

    def jx_permission_state(self):
        """Estado efectivo (has_group) para radios/checks. Solo lectura."""
        self.ensure_one()
        self._jx_assert_can_edit()
        state = {}
        for section in JX_MODULES:
            if not self._jx_section_visible(section):
                continue
            level_code = "none"
            for level in reversed(list(section.get("levels") or ())):
                if level["code"] == "none":
                    continue
                if not self._jx_level_visible(level):
                    continue
                xmlids = level.get("xmlids") or ()
                if xmlids and all(
                    self.env.ref(x, raise_if_not_found=False) and self.has_group(x)
                    for x in xmlids
                ):
                    level_code = level["code"]
                    break
            caps = {}
            for cap in section.get("caps") or ():
                if not self._jx_cap_visible(cap):
                    continue
                xmlids = cap.get("xmlids") or ()
                caps[cap["code"]] = bool(
                    xmlids
                    and all(
                        self.env.ref(x, raise_if_not_found=False) and self.has_group(x)
                        for x in xmlids
                    )
                )
            state[section["key"]] = {"level": level_code, "caps": caps}
        return state

    def jx_apply_permission_state(self, state):
        """Aplica un mapa completo {section: {level, caps}} vía motor autorizado.

        Usado tras CREATE (pending client state) y para re-sincronizar.
        No acepta group_ids arbitrarios desde el cliente.
        """
        self.ensure_one()
        self._jx_assert_can_edit()
        if not isinstance(state, dict):
            raise UserError(_("Estado de permisos inválido."))
        for section in JX_MODULES:
            if not self._jx_section_visible(section):
                continue
            key = section["key"]
            st = state.get(key) or {}
            visible_levels = [
                L
                for L in (section.get("levels") or ())
                if self._jx_level_visible(L)
            ]
            level_codes = {L["code"] for L in visible_levels}
            level_code = st.get("level") or "none"
            if level_codes:
                if level_code not in level_codes:
                    if "none" in level_codes:
                        level_code = "none"
                    else:
                        level_code = visible_levels[0]["code"]
                self.jx_apply_level(key, level_code)
            desired_caps = st.get("caps") or {}
            for cap in section.get("caps") or ():
                if not self._jx_cap_visible(cap):
                    continue
                enabled = bool(desired_caps.get(cap["code"]))
                self.jx_apply_cap(cap["code"], enabled)
        return self.jx_permission_state()

    # Mirror role fields that the web form may still POST on create/write.
    # Stripped so Admin Center / Fiscal inverses are not the write path.
    _JX_STRIP_ON_CREATE = (
        "justech_ecf_role",
        "justech_warranty_role",
        "justech_admin_center_role",
        "justech_finance_role",
        "justech_fiscal_role",
        "justech_cap_admin_console",
        "justech_cap_install_modules",
    )

    @api.model_create_multi
    def create(self, vals_list):
        clean = []
        for vals in vals_list:
            vals = dict(vals)
            for fname in self._JX_STRIP_ON_CREATE:
                vals.pop(fname, None)
            # Usuarios→Nuevo posts related color_scheme=false; coerce before settings create.
            if "color_scheme" in vals and not vals.get("color_scheme"):
                vals["color_scheme"] = "system"
            vals = self._jx_normalize_company_vals(vals)
            clean.append(vals)
        return super().create(clean)

    def write(self, vals):
        vals = dict(vals)
        if "color_scheme" in vals and not vals.get("color_scheme"):
            vals["color_scheme"] = "system"
        if any(k in vals for k in ("company_id", "company_ids")):
            self._jx_assert_can_edit_companies()
            vals = self._jx_normalize_company_vals(vals, records=self)
        return super().write(vals)

    def _jx_assert_can_edit_companies(self):
        """Solo admin de sistema / Admin Justech puede cambiar empresas de usuarios."""
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "justech_admin_center.group_justech_admin_center_manager"
            )
        ):
            raise AccessError(
                _(
                    "No tiene permiso para modificar las empresas de un usuario. "
                    "Contacte a un administrador."
                )
            )

    @api.model
    def _jx_normalize_company_vals(self, vals, records=None):
        """Mantén coherencia company_id ∈ company_ids cuando es posible en vals."""
        if "company_id" not in vals and "company_ids" not in vals:
            return vals

        company_ids = None
        cmds = vals.get("company_ids")
        if (
            isinstance(cmds, (list, tuple))
            and len(cmds) == 1
            and isinstance(cmds[0], (list, tuple))
            and cmds[0]
            and cmds[0][0] == 6
        ):
            company_ids = list(cmds[0][2] or [])

        company_id = vals.get("company_id")
        if company_id is False:
            return vals

        if company_ids is not None:
            if company_id and company_id not in company_ids:
                if company_ids:
                    vals["company_id"] = company_ids[0]
                else:
                    vals["company_id"] = False
            elif not company_id and company_ids:
                vals["company_id"] = company_ids[0]
            return vals

        # Solo company_id en vals: asegurar vínculo en company_ids
        if company_id and records is not None:
            missing = records.filtered(lambda u: company_id not in u.company_ids.ids)
            if missing:
                vals["company_ids"] = [(4, company_id)]
        elif company_id and records is None:
            vals.setdefault("company_ids", [(4, company_id)])
        return vals

    @api.constrains("company_id", "company_ids")
    def _jx_check_company_id_in_company_ids(self):
        for user in self:
            if user.company_id and user.company_ids and user.company_id not in user.company_ids:
                raise ValidationError(
                    _(
                        "La empresa principal debe estar entre las empresas permitidas."
                    )
                )

    @api.onchange("company_id")
    def _jx_onchange_company_id(self):
        if self.company_id and self.company_id not in self.company_ids:
            self.company_ids = self.company_ids | self.company_id

    @api.onchange("company_ids")
    def _jx_onchange_company_ids(self):
        if self.company_ids and self.company_id not in self.company_ids:
            self.company_id = self.company_ids[0]
        elif not self.company_ids:
            self.company_id = False

    def jx_summary(self):
        """Resumen compacto bajo demanda (no campos compute persistentes)."""
        self.ensure_one()
        self._jx_assert_can_edit()
        modules = []
        can = []
        cannot = []
        warnings = []
        tech = []
        full_state = self.jx_permission_state() or {}
        for section in JX_MODULES:
            if not self._jx_section_visible(section):
                continue
            st = full_state.get(section["key"]) or {}
            level_code = st.get("level") or "none"
            level = next(
                (L for L in (section.get("levels") or ()) if L["code"] == level_code),
                None,
            )
            if level and level_code != "none":
                modules.append("• %s: %s" % (section["label"], level["label"]))
                can.extend("• %s" % c for c in (level.get("can") or ()))
                cannot.extend("• %s" % c for c in (level.get("cannot") or ()))
                if level.get("warning"):
                    warnings.append("• %s: %s" % (section["label"], level["warning"]))
                tech.append(
                    "• %s → %s"
                    % (section["label"], ", ".join(level.get("xmlids") or ()) or "—")
                )
            for cap in section.get("caps") or ():
                if (st.get("caps") or {}).get(cap["code"]):
                    can.extend("• %s" % c for c in (cap.get("can") or ()))
                    if cap.get("warning"):
                        warnings.append("• %s" % cap["warning"])
                    tech.append(
                        "• cap %s → %s"
                        % (cap["code"], ", ".join(cap.get("xmlids") or ()))
                    )
        if len(self.company_ids) > 1:
            warnings.append(
                "• El usuario tiene acceso a %s empresas." % len(self.company_ids)
            )
        return {
            "modules": "\n".join(modules) or "—",
            "can": "\n".join(can) or "—",
            "cannot": "\n".join(cannot) or "—",
            "warnings": "\n".join(warnings) or "—",
            "tech": "\n".join(tech) or "—",
        }

    def jx_apply_level(self, section_key, level_code):
        """Asigna el nivel: (4) xmlids deseados, (3) resto del ladder si están explícitos.

        Si el nivel define ``default_caps``, también aplica ese preset de caps
        (y limpia el resto de caps de la sección).
        """
        self.ensure_one()
        self._jx_assert_can_edit()
        section = self._jx_section_by_key(section_key)
        if not section or not self._jx_section_visible(section):
            raise UserError(_("Sección de permisos no disponible: %s") % section_key)
        level = next(
            (L for L in (section.get("levels") or ()) if L["code"] == level_code),
            None,
        )
        if not level:
            raise UserError(
                _("Nivel desconocido «%s» en %s") % (level_code, section_key)
            )
        if not self._jx_level_visible(level):
            raise UserError(_("Nivel no disponible en esta base: %s") % level_code)

        desired = set(level.get("xmlids") or ())
        # Resolve default_caps → xmlids (preset)
        caps_by_code = {c["code"]: c for c in (section.get("caps") or ())}
        for cap_code in level.get("default_caps") or ():
            cap = caps_by_code.get(cap_code)
            if not cap:
                continue
            desired.update(cap.get("xmlids") or ())
            for implied in cap.get("implies_caps") or ():
                icap = caps_by_code.get(implied)
                if icap:
                    desired.update(icap.get("xmlids") or ())

        ladder = self._jx_ladder_xmlids(section)
        # Also manage every cap xmlid of this section (clear when not in preset)
        for cap in section.get("caps") or ():
            for xid in cap.get("xmlids") or ():
                if xid not in ladder:
                    ladder.append(xid)

        cmds = []
        for xmlid in ladder:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                continue
            if xmlid in desired:
                if group not in self.group_ids:
                    cmds.append((4, group.id))
            else:
                if group in self.group_ids:
                    cmds.append((3, group.id))
        if cmds:
            self.write({"group_ids": cmds})
        return self.jx_permission_state()

    def jx_apply_cap(self, cap_code, enabled):
        """Activa/desactiva capacidad: solo (4)/(3) de sus xmlids."""
        self.ensure_one()
        self._jx_assert_can_edit()
        cap, section = self._jx_cap_by_code(cap_code)
        if not cap or not self._jx_cap_visible(cap):
            raise UserError(_("Capacidad no disponible: %s") % cap_code)
        codes = [cap_code]
        if enabled:
            codes.extend(cap.get("implies_caps") or ())
        else:
            # Disabling a view-cap also disables manage-caps that imply it
            for other in (section or {}).get("caps") or ():
                if cap_code in (other.get("implies_caps") or ()):
                    codes.append(other["code"])
        cmds = []
        seen = set()
        for code in codes:
            c = cap if code == cap_code else (self._jx_cap_by_code(code)[0] or {})
            if not c:
                continue
            for xmlid in c.get("xmlids") or ():
                if xmlid in seen:
                    continue
                seen.add(xmlid)
                group = self.env.ref(xmlid, raise_if_not_found=False)
                if not group:
                    continue
                if enabled:
                    if group not in self.group_ids:
                        cmds.append((4, group.id))
                else:
                    if group in self.group_ids:
                        cmds.append((3, group.id))
        if cmds:
            self.write({"group_ids": cmds})
        return self.jx_permission_state()
