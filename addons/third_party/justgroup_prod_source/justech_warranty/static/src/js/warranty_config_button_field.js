/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const STATUS_LABELS = {
    none: _t("Sin garantía"),
    pending: _t("Pendiente de configurar"),
    configured: _t("Configurada"),
};

const HIDDEN_LINE_TYPES = new Set(["line_section", "line_note", "line_subsection"]);
const WIZARD_MODEL = "justech.warranty.line.config.wizard";

export class WarrantyConfigButtonField extends Component {
    static template = xml`
        <button t-if="visible"
                type="button"
                t-att-class="buttonClass"
                t-att-title="tooltip"
                t-att-disabled="disabled"
                t-on-click.prevent.stop="onClick">
            <i class="fa fa-shield" role="img" t-att-aria-label="tooltip"/>
        </button>`;
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
    }

    get visible() {
        const displayType = this.props.record.data.display_type;
        return !displayType || !HIDDEN_LINE_TYPES.has(displayType);
    }

    /** Botón habilitado en cuanto haya producto (línea guardada o `NewId`). */
    get disabled() {
        if (!this._productId) {
            return true;
        }
        const marker = this.props.record.data?.warranty_config_btn;
        if (marker === "draft") {
            return false;
        }
        return !this.lineId && !marker;
    }

    get lineId() {
        const record = this.props.record;
        const raw = record.data?.warranty_config_btn;
        if (raw && raw !== "draft") {
            const parsed = parseInt(raw, 10);
            if (parsed) return parsed;
        }
        const resId = record.resId;
        if (typeof resId === "number" && resId) {
            return resId;
        }
        return 0;
    }

    get status() {
        return this.props.record.data.warranty_status || "none";
    }

    get tooltip() {
        return STATUS_LABELS[this.status] || STATUS_LABELS.none;
    }

    get buttonClass() {
        const base = "btn btn-link o_warranty_config_btn p-0 border-0";
        if (this.disabled) {
            return `${base} text-muted opacity-50`;
        }
        if (this.status === "configured") {
            return `${base} text-success`;
        }
        if (this.status === "pending") {
            return `${base} text-warning`;
        }
        return `${base} text-muted`;
    }

    get _productId() {
        return this._getRelId(this.props.record.data.product_id);
    }

    _getRelId(field) {
        if (!field) return false;
        if (typeof field === "number") return field;
        if (Array.isArray(field)) return field[0] || false;
        if (typeof field === "object") return field.id || false;
        return false;
    }

    _getRelName(field) {
        if (!field) return "";
        if (Array.isArray(field)) return field[1] || "";
        if (typeof field === "object") return field.display_name || "";
        return "";
    }

    async onClick() {
        if (this.disabled) {
            return;
        }
        const record = this.props.record;
        const resModel = record.resModel || record.config?.resModel;

        if (this.lineId) {
            // Línea ya persistida: usamos el método de servidor tradicional.
            const act = await this.orm.call(
                resModel,
                "action_open_warranty_config_wizard",
                [[this.lineId]],
            );
            if (act) {
                await this.action.doAction(act);
            }
            return;
        }

        // Línea sin guardar (NewId): abrimos el wizard con defaults tomados
        // del record local y, al cerrarse, aplicamos los valores devueltos.
        await this._openDraftWizard(resModel, record);
    }

    async _openDraftWizard(resModel, record) {
        const data = record.data || {};
        const productId = this._productId;
        if (!productId) {
            return;
        }
        const productName = this._getRelName(data.product_id);
        const expected = parseInt(
            data.warranty_expected_units || data.product_uom_qty || data.quantity || 1,
            10,
        );
        const defaults = {
            line_model: resModel,
            line_id: 0,
            product_id: productId,
            warranty_apply: !!data.warranty_apply,
            warranty_months: parseInt(data.warranty_months || 0, 10) || 12,
            warranty_type_id: this._getRelId(data.warranty_type_id),
            warranty_notes: data.warranty_notes || false,
            warranty_expected_units: Math.max(expected || 1, 1),
            warranty_vendor_id: this._getRelId(data.warranty_vendor_id),
            warranty_planned_serials: data.warranty_planned_serials || false,
        };
        // La `product_id` es readonly en el wizard; no la incluimos si no aplica.
        Object.keys(defaults).forEach((k) => {
            if (defaults[k] === undefined) delete defaults[k];
        });

        const wizardIds = await this.orm.create(WIZARD_MODEL, [defaults]);
        const wizId = Array.isArray(wizardIds) ? wizardIds[0] : wizardIds;

        const action = {
            type: "ir.actions.act_window",
            name: _t("Configurar garantía"),
            res_model: WIZARD_MODEL,
            res_id: wizId,
            views: [[false, "form"]],
            view_mode: "form",
            target: "new",
            context: { dialog_size: "extra-large" },
        };

        const applyToRecord = async (vals) => {
            if (!vals) return;
            const updateVals = {};
            const passThrough = [
                "warranty_apply",
                "warranty_months",
                "warranty_notes",
                "warranty_expected_units",
                "warranty_planned_serials",
            ];
            for (const key of passThrough) {
                if (key in vals) updateVals[key] = vals[key];
            }
            if ("warranty_type_id" in vals) {
                updateVals.warranty_type_id = vals.warranty_type_id || false;
            }
            if ("warranty_vendor_id" in vals) {
                updateVals.warranty_vendor_id = vals.warranty_vendor_id || false;
            }
            try {
                await record.update(updateVals);
            } catch (err) {
                console.warn("[justech_warranty] No se pudo aplicar el wizard al record local", err);
            }
        };

        // `product_name` solo para el label. Se ignora si no cabe.
        void productName;

        await this.action.doAction(action, {
            onClose: async (closeInfo) => {
                if (closeInfo && closeInfo.applied && closeInfo.vals) {
                    await applyToRecord(closeInfo.vals);
                }
            },
        });
    }
}

registry.category("fields").add("warranty_config_button", {
    component: WarrantyConfigButtonField,
    supportedTypes: ["char"],
    fieldDependencies: [
        { name: "product_id", type: "many2one" },
        { name: "display_type", type: "char" },
        { name: "warranty_apply", type: "boolean" },
        { name: "warranty_months", type: "integer" },
        { name: "warranty_status", type: "selection" },
        { name: "warranty_notes", type: "text" },
        { name: "warranty_type_id", type: "many2one" },
        { name: "warranty_expected_units", type: "integer" },
        { name: "warranty_vendor_id", type: "many2one" },
        { name: "warranty_planned_serials", type: "text" },
    ],
});
