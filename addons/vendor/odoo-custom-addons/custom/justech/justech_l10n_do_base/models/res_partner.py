# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Códigos: 1 RNC, 2 Cédula, 3 Pasaporte, 4 Otro,
    # 5 ID fiscal extranjera, 6 Registro mercantil extranjero
    justech_do_partner_id_type = fields.Selection(
        selection=[
            ("1", "RNC"),
            ("2", "Cédula"),
            ("3", "Pasaporte"),
            ("4", "Otro"),
            ("5", "Identificación fiscal extranjera"),
            ("6", "Registro mercantil extranjero"),
        ],
        string="Tipo de identificación",
        compute="_compute_justech_do_partner_id_type",
        store=True,
        readonly=False,
    )
    justech_do_vat_label = fields.Char(
        string="Etiqueta identificación",
        compute="_compute_justech_do_vat_label",
    )
    justech_do_is_dominican = fields.Boolean(
        compute="_compute_justech_do_is_dominican",
    )
    justech_do_show_rnc_validation = fields.Boolean(
        compute="_compute_justech_do_fiscal_visibility",
    )
    justech_do_rnc_valid = fields.Boolean(
        string="RNC formato válido",
        compute="_compute_justech_do_rnc_valid",
        store=True,
    )
    justech_do_default_document_type_id = fields.Many2one(
        "justech.do.fiscal.document.type",
        string="Comprobante fiscal por defecto",
        domain="[('is_sale_document', '=', True), ('move_type', '=', 'out_invoice')]",
        help="Comprobante preferido del cliente. Se conserva desde el histórico "
        "cuando es consistente; en clientes nuevos se asigna al validar el RNC.",
    )
    justech_do_fiscal_config_state = fields.Selection(
        [
            ("pending_new", "Pendiente de validar — cliente nuevo"),
            ("validated_padron", "Validado por padrón"),
            ("confirmed_history", "Confirmado por histórico"),
            ("needs_review", "Requiere revisión — histórico inconsistente"),
            ("not_applicable", "No aplica"),
        ],
        string="Estado configuración fiscal",
        default="pending_new",
        copy=False,
        index=True,
        help="Separa clientes históricos (confirmados por facturación) de clientes nuevos.",
    )
    justech_do_fiscal_config_source = fields.Char(
        string="Fuente configuración fiscal",
        copy=False,
        help="Ej. Confirmado por historial de facturación / Validado por padrón DGII.",
    )
    justech_do_historical_document_prefix = fields.Char(
        string="Comprobante histórico principal",
        copy=False,
        help="Prefijo (B01/B02/…) reconstruido desde facturas publicadas consistentes.",
    )
    justech_do_suggested_document_type_id = fields.Many2one(
        "justech.do.fiscal.document.type",
        string="Comprobante sugerido",
        compute="_compute_justech_do_document_suggestion",
    )
    justech_do_document_suggestion_hint = fields.Char(
        string="Sugerencia de comprobante",
        compute="_compute_justech_do_document_suggestion",
    )

    justech_do_show_company_fiscal = fields.Boolean(
        compute="_compute_justech_do_fiscal_visibility",
    )
    justech_do_show_personal_id = fields.Boolean(
        compute="_compute_justech_do_fiscal_visibility",
    )
    justech_do_show_default_document_type = fields.Boolean(
        compute="_compute_justech_do_fiscal_visibility",
    )

    justech_do_rnc_status = fields.Selection(
        [
            ("pending", "Pendiente de validar"),
            ("valid", "Validado"),
            ("not_found", "No encontrado"),
            ("invalid", "RNC inválido"),
            ("duplicate", "RNC duplicado"),
            ("error", "Error de consulta"),
            # legado (ya no se usa como resultado principal)
            ("stale", "Padrón desactualizado"),
        ],
        string="Resultado validación RNC",
        default="pending",
        copy=False,
    )
    justech_do_padron_source_state = fields.Selection(
        [
            ("ok", "Padrón actualizado"),
            ("stale", "Padrón desactualizado"),
            ("empty", "Sin padrón cargado"),
        ],
        string="Estado del padrón",
        copy=False,
    )
    justech_do_padron_source_info = fields.Char(
        string="Fuente del padrón",
        copy=False,
    )
    justech_do_rnc_padron_id = fields.Many2one(
        "justech.do.rnc.padron",
        string="Registro padrón",
        copy=False,
    )
    justech_do_rnc_official_name = fields.Char(
        string="Razón social oficial",
        copy=False,
    )
    justech_do_rnc_trade_name = fields.Char(
        string="Nombre comercial (DGII)",
        copy=False,
    )
    justech_do_rnc_contributor_state = fields.Char(
        string="Estado del contribuyente",
        copy=False,
    )
    justech_do_rnc_economic_activity = fields.Char(
        string="Actividad económica",
        copy=False,
    )
    justech_do_rnc_source = fields.Char(string="Fuente RNC", copy=False)
    justech_do_rnc_validated_at = fields.Datetime(
        string="Última validación RNC",
        copy=False,
    )
    justech_do_rnc_name_differs = fields.Boolean(
        compute="_compute_justech_do_rnc_name_differs",
    )
    justech_do_rnc_duplicate_partner_id = fields.Many2one(
        "res.partner",
        string="Contacto con RNC duplicado",
        copy=False,
    )
    justech_do_rnc_duplicate_info = fields.Char(
        string="Detalle duplicado RNC",
        compute="_compute_justech_do_rnc_duplicate_info",
    )

    @api.depends("country_id", "country_id.code")
    def _compute_justech_do_is_dominican(self):
        for partner in self:
            partner.justech_do_is_dominican = bool(
                partner.country_id and partner.country_id.code == "DO"
            )

    @api.depends(
        "is_company",
        "parent_id",
        "type",
        "justech_do_partner_id_type",
        "vat",
        "country_id",
        "justech_do_is_dominican",
    )
    def _compute_justech_do_fiscal_visibility(self):
        for partner in self:
            is_commercial_company = bool(partner.is_company and not partner.parent_id)
            is_child = bool(partner.parent_id)
            is_person = not partner.is_company
            show_doc = bool(is_commercial_company and partner.justech_do_is_dominican)
            if (
                is_person
                and not is_child
                and partner.justech_do_is_dominican
                and partner.justech_do_partner_id_type in ("2", "3", "4")
                and partner.vat
            ):
                show_doc = True
            if is_child or not partner.justech_do_is_dominican:
                if not is_commercial_company:
                    show_doc = False
                elif not partner.justech_do_is_dominican:
                    show_doc = False
            partner.justech_do_show_company_fiscal = is_commercial_company
            partner.justech_do_show_personal_id = bool(
                is_person and (not is_child or partner.type == "contact")
            )
            partner.justech_do_show_default_document_type = show_doc
            # Validación padrón: RNC (empresa DO) o Cédula (persona DO con VAT).
            partner.justech_do_show_rnc_validation = bool(
                partner.justech_do_is_dominican
                and not is_child
                and (
                    (
                        is_commercial_company
                        and partner.justech_do_partner_id_type == "1"
                    )
                    or (
                        is_person
                        and partner.justech_do_partner_id_type == "2"
                        and partner.vat
                    )
                )
            )

    @api.depends(
        "is_company",
        "country_id",
        "country_id.code",
        "justech_do_partner_id_type",
        "justech_do_is_dominican",
        "parent_id",
    )
    def _compute_justech_do_vat_label(self):
        for partner in self:
            if partner.parent_id and not partner.is_company:
                partner.justech_do_vat_label = False
                continue
            idt = partner.justech_do_partner_id_type
            if partner.is_company:
                if partner.justech_do_is_dominican and idt in (False, "1"):
                    partner.justech_do_vat_label = "RNC"
                elif idt == "5":
                    partner.justech_do_vat_label = "Identificación fiscal"
                elif idt == "6":
                    partner.justech_do_vat_label = "Registro mercantil"
                elif idt == "4":
                    partner.justech_do_vat_label = "Otro número de identificación"
                else:
                    partner.justech_do_vat_label = "Identificación fiscal"
            else:
                if idt == "2":
                    partner.justech_do_vat_label = "Cédula"
                elif idt == "3":
                    partner.justech_do_vat_label = "Pasaporte"
                elif idt == "4":
                    partner.justech_do_vat_label = "Otro número de identificación"
                elif idt == "5":
                    partner.justech_do_vat_label = "Identificación fiscal"
                else:
                    partner.justech_do_vat_label = (
                        "Cédula" if partner.justech_do_is_dominican else "Pasaporte"
                    )

    @api.depends(
        "vat",
        "is_company",
        "country_id",
        "country_id.code",
        "justech_do_partner_id_type",
    )
    def _compute_justech_do_partner_id_type(self):
        from odoo.addons.justech_l10n_do_base.validators import rnc_format

        for partner in self:
            is_do = partner.country_id and partner.country_id.code == "DO"
            if partner.is_company:
                if is_do:
                    # Empresa DO: RNC por defecto; respetar extranjero solo si ya elegido.
                    if partner.justech_do_partner_id_type in ("5", "6", "4"):
                        continue
                    partner.justech_do_partner_id_type = "1"
                else:
                    if partner.justech_do_partner_id_type in ("5", "6", "4", "3"):
                        continue
                    partner.justech_do_partner_id_type = "5"
                continue
            # Persona
            if partner.justech_do_partner_id_type in ("2", "3", "4", "5") and not partner.vat:
                continue
            inferred = rnc_format.dgii_id_type_from_vat(partner.vat)
            if inferred == "2":
                partner.justech_do_partner_id_type = "2"
            elif inferred == "1":
                partner.justech_do_partner_id_type = (
                    partner.justech_do_partner_id_type
                    if partner.justech_do_partner_id_type in ("2", "3", "4")
                    else "2"
                )
            elif not partner.justech_do_partner_id_type:
                partner.justech_do_partner_id_type = "2" if is_do else "3"

    @api.depends("vat", "country_id", "country_id.code", "is_company", "justech_do_partner_id_type")
    def _compute_justech_do_rnc_valid(self):
        for partner in self:
            is_do = partner.country_id and partner.country_id.code == "DO"
            if not is_do or not partner.vat:
                partner.justech_do_rnc_valid = False
                continue
            cleaned = self.env["justech.do.fiscal.validator.service"].normalize_vat(
                partner.vat
            )
            if partner.is_company and partner.justech_do_partner_id_type == "1":
                partner.justech_do_rnc_valid = bool(
                    cleaned
                    and len(cleaned) == 9
                    and partner._justech_validate_rnc_format(cleaned)
                )
            elif not partner.is_company and partner.justech_do_partner_id_type == "2":
                partner.justech_do_rnc_valid = bool(
                    cleaned
                    and len(cleaned) == 11
                    and partner._justech_validate_rnc_format(cleaned)
                )
            else:
                partner.justech_do_rnc_valid = False

    @api.depends("name", "justech_do_rnc_official_name")
    def _compute_justech_do_rnc_name_differs(self):
        for partner in self:
            official = (partner.justech_do_rnc_official_name or "").strip().upper()
            current = (partner.name or "").strip().upper()
            partner.justech_do_rnc_name_differs = bool(
                official and current and official != current
            )

    @api.depends(
        "justech_do_rnc_duplicate_partner_id",
        "justech_do_rnc_duplicate_partner_id.name",
        "justech_do_rnc_duplicate_partner_id.active",
    )
    def _compute_justech_do_rnc_duplicate_info(self):
        for partner in self:
            dup = partner.justech_do_rnc_duplicate_partner_id
            if not dup:
                partner.justech_do_rnc_duplicate_info = False
                continue
            state = _("activo") if dup.active else _("archivado")
            partner.justech_do_rnc_duplicate_info = _(
                "Ya existe: %(name)s (ID %(id)s, %(state)s)"
            ) % {"name": dup.display_name, "id": dup.id, "state": state}

    @api.depends(
        "is_company",
        "justech_do_is_dominican",
        "l10n_do_dgii_tax_payer_type",
        "justech_do_rnc_status",
        "justech_do_partner_id_type",
        "parent_id",
    )
    def _compute_justech_do_document_suggestion(self):
        Doc = self.env["justech.do.fiscal.document.type"]
        for partner in self:
            partner.justech_do_suggested_document_type_id = False
            partner.justech_do_document_suggestion_hint = False
            if partner.parent_id or not partner.justech_do_is_dominican:
                continue
            prefix = False
            hint = False
            payer = getattr(partner, "l10n_do_dgii_tax_payer_type", False)
            if partner.is_company and partner.justech_do_partner_id_type == "1":
                if payer == "governmental":
                    # Solo sugerir B15 con clasificación confirmada.
                    prefix, hint = "B15", _("Sugerido: B15 Gubernamental (clasificación confirmada).")
                elif payer == "special":
                    prefix, hint = "B14", _("Sugerido: B14 Régimen especial (clasificación confirmada).")
                elif partner.justech_do_rnc_status == "valid" or payer == "taxpayer":
                    prefix, hint = "B01", _("Sugerido: B01 Crédito Fiscal.")
                elif payer == "non_payer":
                    prefix, hint = "B02", _("Sugerido: B02 Consumo.")
            elif not partner.is_company and partner.justech_do_partner_id_type in (
                "2",
                "3",
                "4",
            ):
                prefix, hint = "B02", _("Sugerido: B02 Consumo (persona / consumidor).")
            if prefix:
                doc = Doc.get_by_prefix(prefix, company=self.env.company)
                partner.justech_do_suggested_document_type_id = doc
                partner.justech_do_document_suggestion_hint = hint

    @api.model
    def _justech_validate_rnc_format(self, vat):
        return self.env["justech.do.fiscal.validator.service"].is_valid_rnc_format(vat)

    @api.constrains("vat", "country_id", "is_company", "justech_do_partner_id_type")
    def _check_do_rnc_format(self):
        Validator = self.env["justech.do.fiscal.validator.service"]
        for partner in self:
            if not partner.vat:
                continue
            cleaned = Validator.normalize_vat(partner.vat)
            if not cleaned:
                continue
            is_do = partner.country_id and partner.country_id.code == "DO"
            if (
                partner.is_company
                and not partner.parent_id
                and is_do
                and partner.justech_do_partner_id_type == "1"
            ):
                if len(cleaned) != 9 or not cleaned.isdigit():
                    raise ValidationError(
                        _("El RNC de una empresa dominicana debe tener 9 dígitos.")
                    )
                Validator.validate_rnc_format(cleaned)
            elif is_do and not partner.is_company and partner.vat:
                if not Validator.is_valid_rnc_format(cleaned):
                    raise ValidationError(
                        _(
                            "La cédula/pasaporte debe tener entre 9 y 11 dígitos "
                            "(sin guiones ni espacios)."
                        )
                    )

    @api.model_create_multi
    def create(self, vals_list):
        Validator = self.env["justech.do.fiscal.validator.service"]
        Padron = self.env["justech.do.rnc.padron"]
        for vals in vals_list:
            if vals.get("vat"):
                vals["vat"] = Validator.normalize_vat(vals["vat"])
            # Empresa nueva sin nombre: completar desde padrón (o VAT) para poder
            # guardar y ejecutar Validar RNC (Odoo guarda antes del botón).
            is_company = vals.get("is_company")
            if "company_type" in vals:
                is_company = vals.get("company_type") == "company"
            if is_company is None:
                is_company = bool(
                    self.env.context.get("default_is_company")
                    or self.env.context.get("default_company_type") == "company"
                )
            if is_company and not (vals.get("name") or "").strip():
                cleaned = vals.get("vat") or ""
                if cleaned and len(cleaned) == 9 and cleaned.isdigit():
                    entry = Padron.lookup(cleaned)
                    vals["name"] = entry.name if entry and entry.name else cleaned
                else:
                    raise ValidationError(
                        _(
                            "Indique el nombre o razón social, o el RNC "
                            "para completar la razón social oficial."
                        )
                    )
        partners = super().create(vals_list)
        partners._justech_block_rnc_duplicate()
        partners._justech_block_cedula_duplicate()
        return partners

    def write(self, vals):
        Validator = self.env["justech.do.fiscal.validator.service"]
        if "vat" in vals and vals.get("vat"):
            vals = dict(vals)
            vals["vat"] = Validator.normalize_vat(vals["vat"])
        to_check_rnc = self.env["res.partner"]
        to_check_cedula = self.env["res.partner"]
        if "vat" in vals:
            new_cleaned = Validator.normalize_vat(vals.get("vat"))
            for partner in self:
                old_cleaned = partner.justech_do_clean_vat() if partner.vat else ""
                if new_cleaned != old_cleaned:
                    to_check_rnc |= partner
                    to_check_cedula |= partner
        elif any(k in vals for k in ("is_company", "company_type", "parent_id")):
            to_check_rnc = self
            to_check_cedula = self
        res = super().write(vals)
        if to_check_rnc:
            to_check_rnc._justech_block_rnc_duplicate()
        if to_check_cedula:
            to_check_cedula._justech_block_cedula_duplicate()
        return res

    def _justech_block_rnc_duplicate(self):
        for partner in self:
            if not partner._justech_is_commercial_company():
                continue
            if not partner.justech_do_is_dominican:
                continue
            if partner.justech_do_partner_id_type != "1":
                continue
            cleaned = partner.justech_do_clean_vat()
            if not cleaned or len(cleaned) != 9:
                continue
            duplicate = partner._justech_find_rnc_duplicate(cleaned)
            if duplicate:
                raise ValidationError(
                    _(
                        "Ya existe un contacto comercial con el RNC %(rnc)s:\n"
                        "%(name)s (ID %(id)s, %(state)s).\n"
                        "Abra el contacto existente en lugar de crear otro."
                    )
                    % {
                        "rnc": cleaned,
                        "name": duplicate.display_name,
                        "id": duplicate.id,
                        "state": _("activo") if duplicate.active else _("archivado"),
                    }
                )

    def _justech_block_cedula_duplicate(self):
        for partner in self:
            if partner.is_company:
                continue
            if partner.parent_id and partner.type != "contact":
                continue
            cleaned = partner.justech_do_clean_vat() if partner.vat else ""
            if not cleaned or len(cleaned) != 11:
                continue
            duplicate = partner._justech_find_cedula_duplicate(cleaned)
            if duplicate:
                raise ValidationError(
                    _(
                        "Ya existe una persona con la cédula %(ced)s:\n"
                        "%(name)s (ID %(id)s)."
                    )
                    % {
                        "ced": cleaned,
                        "name": duplicate.display_name,
                        "id": duplicate.id,
                    }
                )

    def _justech_is_commercial_company(self):
        self.ensure_one()
        return bool(self.is_company and not self.parent_id)

    def _justech_find_rnc_duplicate(self, cleaned_rnc):
        self.ensure_one()
        Partner = self.env["res.partner"].with_context(active_test=False)
        self.env.cr.execute(
            """
            SELECT id
              FROM res_partner
             WHERE is_company IS TRUE
               AND parent_id IS NULL
               AND vat IS NOT NULL
               AND id != %s
               AND regexp_replace(vat, '[^0-9]', '', 'g') = %s
             LIMIT 1
            """,
            (self.id or 0, cleaned_rnc),
        )
        row = self.env.cr.fetchone()
        return Partner.browse(row[0]) if row else Partner.browse()

    def _justech_find_cedula_duplicate(self, cleaned_cedula):
        self.ensure_one()
        Partner = self.env["res.partner"].with_context(active_test=False)
        self.env.cr.execute(
            """
            SELECT id
              FROM res_partner
             WHERE is_company IS FALSE
               AND vat IS NOT NULL
               AND id != %s
               AND (parent_id IS NULL OR type = 'contact')
               AND regexp_replace(vat, '[^0-9]', '', 'g') = %s
             LIMIT 1
            """,
            (self.id or 0, cleaned_cedula),
        )
        row = self.env.cr.fetchone()
        return Partner.browse(row[0]) if row else Partner.browse()

    def justech_do_has_rnc(self):
        self.ensure_one()
        return bool(
            self.is_company
            and self.justech_do_is_dominican
            and self.vat
            and self._justech_validate_rnc_format(self.vat)
        )

    def justech_do_clean_vat(self):
        self.ensure_one()
        return self.env["justech.do.fiscal.validator.service"].normalize_vat(self.vat)

    def justech_do_get_default_sale_document_type(self, company=None):
        if not self:
            return self.env["justech.do.fiscal.document.type"]
        self.ensure_one()
        target = self
        if self.parent_id or not self.is_company:
            commercial = self.commercial_partner_id
            if commercial and commercial != self and commercial.is_company:
                target = commercial
        doc = target.justech_do_default_document_type_id
        if doc and doc.is_sale_document and doc.move_type == "out_invoice":
            return doc
        # Histórico confirmado o reconstruible por empresa (sin sobrescribir BD aquí).
        hist = target.justech_do_get_historical_sale_document_type(company=company)
        if hist:
            return hist
        return self.env["justech.do.fiscal.document.type"]

    def _justech_do_sale_ncf_prefixes(self):
        return ("B01", "B02", "B14", "B15", "B16", "B12")

    def justech_do_analyze_invoice_document_history(self, company=None):
        """Analiza facturas publicadas del cliente (solo lectura).

        Retorna dict por company_id:
        {prefix, count_top, count_total, ratio, status, last_ncf, last_move, last_date}
        """
        self.ensure_one()
        partner = self.commercial_partner_id
        Move = self.env["account.move"].sudo()
        domain = [
            ("partner_id", "child_of", partner.id),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
        ]
        if company:
            domain.append(("company_id", "=", company.id))
        moves = Move.search(domain, order="invoice_date desc, id desc")
        by_co = {}
        for move in moves:
            ncf = move.justech_do_ncf or getattr(move, "l10n_latam_document_number", False) or ""
            if not ncf or str(ncf).upper().startswith("PROFORMA"):
                continue
            prefix = (
                move.justech_do_document_type_id.prefix
                if move.justech_do_document_type_id
                else str(ncf)[:3]
            )
            if prefix not in self._justech_do_sale_ncf_prefixes():
                continue
            cid = move.company_id.id
            bucket = by_co.setdefault(cid, {"counts": {}, "last": None})
            bucket["counts"][prefix] = bucket["counts"].get(prefix, 0) + 1
            if not bucket["last"]:
                bucket["last"] = {
                    "ncf": ncf,
                    "move": move.name,
                    "date": str(move.invoice_date or ""),
                    "prefix": prefix,
                }
        result = {}
        for cid, data in by_co.items():
            counts = data["counts"]
            total = sum(counts.values())
            if not total:
                continue
            top_pref, top_n = max(counts.items(), key=lambda x: x[1])
            ratio = top_n / total
            status = "consistent" if ratio >= 0.8 else "mixed"
            result[cid] = {
                "prefix": top_pref,
                "count_top": top_n,
                "count_total": total,
                "ratio": ratio,
                "status": status,
                "types": counts,
                "last_ncf": data["last"]["ncf"],
                "last_move": data["last"]["move"],
                "last_date": data["last"]["date"],
            }
        return result

    def justech_do_get_historical_sale_document_type(self, company=None):
        """Comprobante histórico consistente para la empresa (o el más fuerte)."""
        self.ensure_one()
        Doc = self.env["justech.do.fiscal.document.type"]
        if (
            self.justech_do_fiscal_config_state == "confirmed_history"
            and self.justech_do_historical_document_prefix
            and not company
        ):
            doc = Doc.get_by_prefix(
                self.justech_do_historical_document_prefix, company=self.env.company
            )
            if doc:
                return doc
        analysis = self.justech_do_analyze_invoice_document_history(company=company)
        if not analysis:
            if self.justech_do_historical_document_prefix:
                return Doc.get_by_prefix(
                    self.justech_do_historical_document_prefix, company=self.env.company
                )
            return Doc
        if company:
            data = analysis.get(company.id)
            if data and data["status"] == "consistent":
                return Doc.get_by_prefix(data["prefix"], company=company)
            return Doc
        # Sin empresa: solo si todas las compañías coherentes apuntan al mismo prefijo.
        prefixes = {d["prefix"] for d in analysis.values() if d["status"] == "consistent"}
        if len(prefixes) == 1:
            return Doc.get_by_prefix(next(iter(prefixes)), company=self.env.company)
        return Doc

    def justech_do_has_fiscal_history_signal(self):
        """True si hay evidencia operativa histórica (factura/NCF, pedido o pago)."""
        self.ensure_one()
        partner = self.commercial_partner_id
        Move = self.env["account.move"].sudo()
        if Move.search_count(
            [
                ("partner_id", "child_of", partner.id),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
            ]
        ):
            return True
        if self.env["sale.order"].sudo().search_count(
            [("partner_id", "child_of", partner.id), ("state", "in", ("sale", "done"))]
        ):
            return True
        if self.env["account.payment"].sudo().search_count(
            [
                ("partner_id", "child_of", partner.id),
                ("state", "not in", ("draft", "cancel")),
            ]
        ):
            return True
        return False

    def justech_do_confirm_fiscal_from_history(self, force=False):
        """Persiste comprobante/estado desde histórico consistente. No toca facturas."""
        Doc = self.env["justech.do.fiscal.document.type"]
        for partner in self:
            if partner.parent_id:
                continue
            if (
                not force
                and partner.justech_do_fiscal_config_state
                in ("validated_padron", "confirmed_history")
                and partner.justech_do_default_document_type_id
            ):
                continue
            if not partner.justech_do_is_dominican and partner.country_id:
                partner.write(
                    {
                        "justech_do_fiscal_config_state": "not_applicable",
                        "justech_do_fiscal_config_source": _(
                            "No aplica — extranjero / fuera de RD"
                        ),
                    }
                )
                continue
            analysis = partner.justech_do_analyze_invoice_document_history()
            if not analysis:
                if partner.justech_do_has_fiscal_history_signal():
                    partner.write(
                        {
                            "justech_do_fiscal_config_state": "needs_review",
                            "justech_do_fiscal_config_source": _(
                                "Histórico sin NCF utilizable — revisión"
                            ),
                        }
                    )
                else:
                    partner.write(
                        {
                            "justech_do_fiscal_config_state": "pending_new",
                            "justech_do_fiscal_config_source": _(
                                "Cliente nuevo — validar RNC/Cédula"
                            ),
                        }
                    )
                continue
            statuses = {d["status"] for d in analysis.values()}
            prefixes = {d["prefix"] for d in analysis.values() if d["status"] == "consistent"}
            if "mixed" in statuses:
                partner.write(
                    {
                        "justech_do_fiscal_config_state": "needs_review",
                        "justech_do_fiscal_config_source": _(
                            "Histórico con tipos mixtos — revisión humana"
                        ),
                        "justech_do_historical_document_prefix": False,
                    }
                )
                continue
            if statuses == {"consistent"} and prefixes:
                vals = {
                    "justech_do_fiscal_config_state": "confirmed_history",
                    "justech_do_fiscal_config_source": _(
                        "Confirmado por historial de facturación"
                    ),
                }
                if len(prefixes) == 1:
                    prefix = next(iter(prefixes))
                    doc = Doc.get_by_prefix(prefix, company=self.env.company)
                    vals["justech_do_historical_document_prefix"] = prefix
                    current = partner.justech_do_default_document_type_id
                    if not current:
                        vals["justech_do_default_document_type_id"] = (
                            doc.id if doc else False
                        )
                    elif current.prefix != prefix:
                        vals["justech_do_fiscal_config_state"] = "needs_review"
                        vals["justech_do_fiscal_config_source"] = _(
                            "Default distinto del histórico (%(cur)s vs %(hist)s)"
                        ) % {"cur": current.prefix, "hist": prefix}
                else:
                    # Tipos legítimos distintos por empresa: no imponer un default global.
                    vals["justech_do_historical_document_prefix"] = False
                    vals["justech_do_fiscal_config_source"] = _(
                        "Confirmado por historial (tipo por empresa)"
                    )
                partner.write(vals)
        return True

    def _commercial_sync_from_company(self):
        commercial_partner = self.commercial_partner_id
        if commercial_partner != self:
            sync_vals = commercial_partner._get_commercial_values()
            if (
                sync_vals
                and not self.is_company
                and self.type == "contact"
                and "vat" in sync_vals
            ):
                sync_vals = dict(sync_vals)
                sync_vals.pop("vat", None)
            if sync_vals:
                self.write(sync_vals)
                self._commercial_sync_to_descendants()
            self._company_dependent_commercial_sync()

    def _commercial_sync_to_descendants(self, fields_to_sync=None):
        commercial_partner = self.commercial_partner_id
        if fields_to_sync is None:
            fields_to_sync = self._commercial_fields()
        contact_children = self.child_ids.filtered(
            lambda c: not c.is_company and c.type == "contact"
        )
        other_children = self.child_ids.filtered(
            lambda c: not c.is_company and c.type != "contact"
        )
        fields_no_vat = [f for f in fields_to_sync if f != "vat"]
        for child in contact_children:
            child._commercial_sync_to_descendants(fields_to_sync)
        if fields_no_vat:
            sync_vals = commercial_partner._convert_fields_to_values(fields_no_vat)
            if sync_vals:
                contact_children.write(sync_vals)
        for child in other_children:
            child._commercial_sync_to_descendants(fields_to_sync)
        if fields_to_sync:
            sync_vals = commercial_partner._convert_fields_to_values(fields_to_sync)
            if sync_vals:
                other_children.write(sync_vals)

    @api.onchange("vat", "company_type", "is_company", "country_id")
    def _onchange_justech_do_vat_lookup(self):
        """Solo normaliza; la consulta al padrón se hace con Validar RNC."""
        if self.vat:
            cleaned = self.env["justech.do.fiscal.validator.service"].normalize_vat(
                self.vat
            )
            self.vat = cleaned
        # No degradar clientes históricos confirmados al editar VAT/país.
        if self.justech_do_fiscal_config_state != "confirmed_history":
            self.justech_do_rnc_status = "pending"
            if self.justech_do_fiscal_config_state not in ("needs_review", "not_applicable"):
                self.justech_do_fiscal_config_state = "pending_new"
        self.justech_do_rnc_duplicate_partner_id = False
        if not self.justech_do_show_rnc_validation:
            self.justech_do_rnc_padron_id = False
            self.justech_do_rnc_official_name = False
            self.justech_do_rnc_trade_name = False
            self.justech_do_rnc_contributor_state = False
            self.justech_do_rnc_economic_activity = False

    def _justech_padron_source_meta(self, info):
        """Separa el estado de la fuente del resultado de validación del RNC."""
        from datetime import timedelta

        if not info.get("count"):
            return "empty", _("Sin padrón cargado")
        sync = info.get("sync_date")
        if not sync:
            return "stale", _("Padrón desactualizado (sin fecha de sincronización)")
        age = fields.Datetime.now() - sync
        date_txt = sync.strftime("%d/%m/%Y")
        if age > timedelta(days=30):
            return "stale", _("Padrón desactualizado al %s") % date_txt
        return "ok", _("Padrón actualizado al %s") % date_txt

    def _justech_set_rnc_vals(self, partner, vals):
        """Aplica vals en registro nuevo (cache) o persistido."""
        if not partner.id:
            for key, value in vals.items():
                if key in partner._fields:
                    partner[key] = value
            return
        partner.write(vals)

    def action_justech_validate_rnc(self):
        """Valida RNC contra padrón local.

        No depende del Nombre. Si Nombre está vacío y el RNC es válido,
        completa automáticamente la razón social oficial en Nombre.
        """
        for partner in self:
            if not partner.justech_do_show_rnc_validation:
                self._justech_set_rnc_vals(
                    partner,
                    {
                        "justech_do_rnc_status": "pending",
                        "justech_do_rnc_duplicate_partner_id": False,
                        "justech_do_padron_source_state": False,
                        "justech_do_padron_source_info": False,
                    },
                )
                continue
            cleaned = ""
            if partner.vat:
                cleaned = self.env["justech.do.fiscal.validator.service"].normalize_vat(
                    partner.vat
                )
            if cleaned and partner.vat != cleaned:
                partner.vat = cleaned
            if not cleaned:
                self._justech_set_rnc_vals(
                    partner,
                    {
                        "justech_do_rnc_status": "pending",
                        "justech_do_rnc_duplicate_partner_id": False,
                        "justech_do_rnc_official_name": False,
                        "justech_do_rnc_trade_name": False,
                        "justech_do_rnc_contributor_state": False,
                        "justech_do_rnc_economic_activity": False,
                    },
                )
                continue
            if not partner._justech_validate_rnc_format(cleaned):
                self._justech_set_rnc_vals(
                    partner,
                    {
                        "justech_do_rnc_status": "invalid",
                        "justech_do_rnc_padron_id": False,
                        "justech_do_rnc_official_name": False,
                        "justech_do_rnc_trade_name": False,
                        "justech_do_rnc_contributor_state": False,
                        "justech_do_rnc_economic_activity": False,
                        "justech_do_rnc_source": False,
                        "justech_do_rnc_duplicate_partner_id": False,
                        "justech_do_rnc_validated_at": fields.Datetime.now(),
                        "justech_do_padron_source_state": False,
                        "justech_do_padron_source_info": False,
                    },
                )
                continue
            # Empresa DO (RNC): exactamente 9. Persona (cédula): exactamente 11.
            expected_len = 9 if partner.is_company else 11
            if partner.is_company and partner.justech_do_partner_id_type == "1":
                expected_len = 9
            elif (
                not partner.is_company
                and partner.justech_do_partner_id_type == "2"
            ):
                expected_len = 11
            if len(cleaned) != expected_len:
                self._justech_set_rnc_vals(
                    partner,
                    {
                        "justech_do_rnc_status": "invalid",
                        "justech_do_rnc_padron_id": False,
                        "justech_do_rnc_official_name": False,
                        "justech_do_rnc_trade_name": False,
                        "justech_do_rnc_contributor_state": False,
                        "justech_do_rnc_economic_activity": False,
                        "justech_do_rnc_source": False,
                        "justech_do_rnc_duplicate_partner_id": False,
                        "justech_do_rnc_validated_at": fields.Datetime.now(),
                        "justech_do_padron_source_state": False,
                        "justech_do_padron_source_info": False,
                    },
                )
                continue
            Padron = self.env["justech.do.rnc.padron"]
            info = Padron.last_sync_info()
            source_state, source_info = self._justech_padron_source_meta(info)
            duplicate = partner._justech_find_rnc_duplicate(cleaned)
            if duplicate:
                self._justech_set_rnc_vals(
                    partner,
                    {
                        "justech_do_rnc_status": "duplicate",
                        "justech_do_rnc_duplicate_partner_id": duplicate.id,
                        "justech_do_rnc_official_name": False,
                        "justech_do_rnc_trade_name": False,
                        "justech_do_rnc_validated_at": fields.Datetime.now(),
                        "justech_do_padron_source_state": source_state,
                        "justech_do_padron_source_info": source_info,
                    },
                )
                continue
            entry = Padron.lookup(cleaned) if info.get("count") else Padron.browse()
            if not info.get("count"):
                vals = {
                    "justech_do_rnc_status": "not_found",
                    "justech_do_rnc_padron_id": False,
                    "justech_do_rnc_official_name": False,
                    "justech_do_rnc_trade_name": False,
                    "justech_do_rnc_contributor_state": False,
                    "justech_do_rnc_economic_activity": False,
                    "justech_do_rnc_source": "local_empty",
                    "justech_do_rnc_duplicate_partner_id": False,
                    "justech_do_rnc_validated_at": fields.Datetime.now(),
                    "justech_do_padron_source_state": source_state,
                    "justech_do_padron_source_info": source_info,
                }
            elif not entry:
                vals = {
                    "justech_do_rnc_status": "not_found",
                    "justech_do_rnc_padron_id": False,
                    "justech_do_rnc_official_name": False,
                    "justech_do_rnc_trade_name": False,
                    "justech_do_rnc_contributor_state": False,
                    "justech_do_rnc_economic_activity": False,
                    "justech_do_rnc_source": info.get("source") or "dgii_txt",
                    "justech_do_rnc_duplicate_partner_id": False,
                    "justech_do_rnc_validated_at": fields.Datetime.now(),
                    "justech_do_padron_source_state": source_state,
                    "justech_do_padron_source_info": source_info,
                }
            else:
                state_label = dict(entry._fields["state"].selection).get(
                    entry.state, entry.state
                )
                vals = {
                    "justech_do_rnc_status": "valid",
                    "justech_do_rnc_padron_id": entry.id,
                    "justech_do_rnc_official_name": entry.name or False,
                    "justech_do_rnc_trade_name": entry.trade_name or False,
                    "justech_do_rnc_contributor_state": state_label or False,
                    "justech_do_rnc_economic_activity": entry.economic_activity or False,
                    "justech_do_rnc_source": entry.source,
                    "justech_do_rnc_duplicate_partner_id": False,
                    "justech_do_rnc_validated_at": fields.Datetime.now(),
                    "justech_do_padron_source_state": source_state,
                    "justech_do_padron_source_info": source_info,
                }
                if (
                    entry.category
                    and "l10n_do_dgii_tax_payer_type" in partner._fields
                    and not partner.l10n_do_dgii_tax_payer_type
                ):
                    cat = (entry.category or "").strip().lower()
                    mapping = {
                        "normal": "taxpayer",
                        "contribuyente": "taxpayer",
                        "gobierno": "governmental",
                        "governmental": "governmental",
                        "exento": "special",
                        "especial": "special",
                    }
                    if cat in mapping:
                        vals["l10n_do_dgii_tax_payer_type"] = mapping[cat]
                # Nombre vacío: completar con razón social oficial (creación nueva).
                if not (partner.name or "").strip() and entry.name:
                    vals["name"] = entry.name
                # Cliente nuevo / sin histórico confirmado: consolidar configuración.
                if partner.justech_do_fiscal_config_state != "confirmed_history":
                    vals["justech_do_fiscal_config_state"] = "validated_padron"
                    vals["justech_do_fiscal_config_source"] = _(
                        "Validado por padrón DGII"
                    )
            self._justech_set_rnc_vals(partner, vals)
            # Asignar comprobante por defecto solo si está vacío y hay sugerencia inequívoca.
            # No tocar históricos confirmados ni casos en revisión.
            if (
                vals.get("justech_do_rnc_status") == "valid"
                and not partner.justech_do_default_document_type_id
                and partner.justech_do_fiscal_config_state
                not in ("needs_review", "confirmed_history")
            ):
                partner.invalidate_recordset(
                    ["justech_do_suggested_document_type_id", "justech_do_document_suggestion_hint"]
                )
                suggested = partner.justech_do_suggested_document_type_id
                if suggested:
                    partner.justech_do_default_document_type_id = suggested.id
        return True

    def action_justech_apply_dgii_data(self):
        """Alias: usar razón social oficial."""
        return self.action_justech_apply_official_name()

    def action_justech_apply_official_name(self):
        """Reemplaza el nombre principal con la razón social oficial (confirmación)."""
        self.ensure_one()
        if not self.justech_do_show_rnc_validation:
            raise ValidationError(
                _("Solo aplica a empresas dominicanas con RNC.")
            )
        if not self.justech_do_rnc_official_name and not self.justech_do_rnc_padron_id:
            self.action_justech_validate_rnc()
        name = self.justech_do_rnc_official_name
        if not name and self.justech_do_rnc_padron_id:
            name = self.justech_do_rnc_padron_id.name
        if not name:
            raise ValidationError(
                _("No hay razón social oficial. Valide el RNC primero.")
            )
        country = self.env.ref("base.do", raise_if_not_found=False)
        vals = {
            "name": name,
            "vat": self.vat
            or (
                self.justech_do_rnc_padron_id.rnc
                if self.justech_do_rnc_padron_id
                else False
            ),
        }
        if country:
            vals["country_id"] = country.id
        self._justech_set_rnc_vals(self, vals)
        return True

    def action_justech_open_rnc_duplicate(self):
        self.ensure_one()
        dup = self.justech_do_rnc_duplicate_partner_id
        if not dup and self.vat:
            dup = self._justech_find_rnc_duplicate(self.justech_do_clean_vat())
        if not dup:
            raise ValidationError(_("No hay contacto duplicado para abrir."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Contacto existente"),
            "res_model": "res.partner",
            "res_id": dup.id,
            "view_mode": "form",
            "target": "current",
            "context": {"active_test": False},
        }

    def action_justech_apply_suggested_document(self):
        """Aplica el comprobante sugerido solo con acción explícita del usuario."""
        self.ensure_one()
        if not self.justech_do_suggested_document_type_id:
            raise ValidationError(_("No hay comprobante sugerido para aplicar."))
        self.justech_do_default_document_type_id = (
            self.justech_do_suggested_document_type_id
        )
        if self.justech_do_fiscal_config_state not in (
            "confirmed_history",
            "validated_padron",
        ):
            self.justech_do_fiscal_config_state = "validated_padron"
            self.justech_do_fiscal_config_source = _("Sugerencia fiscal aplicada manualmente")
        return True

    def action_justech_confirm_fiscal_from_history(self):
        """Acción UI / auditoría: confirmar desde histórico de facturas."""
        self.justech_do_confirm_fiscal_from_history(force=True)
        return True
