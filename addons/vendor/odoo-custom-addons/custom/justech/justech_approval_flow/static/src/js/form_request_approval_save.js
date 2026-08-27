/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

const REQUEST_METHODS = new Set([
    "action_justech_request_approval",
    "action_justech_open_request_wizard",
]);

patch(FormController.prototype, {
    /**
     * Solicitar aprobación must save first (Odoo 19 default for type=object).
     * This patch only adds a functional error, debounce, and does not skip validations.
     */
    async beforeExecuteActionButton(clickParams) {
        if (!REQUEST_METHODS.has(clickParams.name)) {
            return super.beforeExecuteActionButton(clickParams);
        }
        if (this._justechApprovalBusy) {
            return false;
        }
        this._justechApprovalBusy = true;
        try {
            const saved = await super.beforeExecuteActionButton(clickParams);
            if (saved === false) {
                this.env.services.notification.add(
                    _t(
                        "No se puede solicitar aprobación porque faltan datos obligatorios en el documento."
                    ),
                    { type: "danger" }
                );
            }
            return saved;
        } catch (error) {
            this.env.services.notification.add(
                _t(
                    "No se puede solicitar aprobación porque faltan datos obligatorios en el documento."
                ),
                { type: "danger" }
            );
            throw error;
        } finally {
            this._justechApprovalBusy = false;
        }
    },
});
