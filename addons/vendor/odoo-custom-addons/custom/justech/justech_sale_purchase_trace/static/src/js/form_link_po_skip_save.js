/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

const SKIP_SAVE_METHODS = new Set([
    "action_justech_link_existing_po",
    "action_justech_buy_pending",
    "action_justech_open_purchases",
    "action_justech_open_purchase_coverage",
]);

patch(FormController.prototype, {
    /**
     * Relacionar OC / Compras must not save the quotation first: required
     * header fields (e.g. payment terms) would block read-only actions.
     */
    async beforeExecuteActionButton(clickParams) {
        const resId = this.model.root.resId;
        if (!SKIP_SAVE_METHODS.has(clickParams.name)) {
            return super.beforeExecuteActionButton(clickParams);
        }
        if (!resId) {
            const msg =
                clickParams.name === "action_justech_buy_pending"
                    ? _t("Guarde la cotización antes de generar una Orden de Compra.")
                    : clickParams.name === "action_justech_link_existing_po"
                    ? _t(
                          "Guarde la cotización antes de relacionar una compra existente."
                      )
                    : _t("Guarde la cotización antes de consultar las compras relacionadas.");
            this.env.services.notification.add(msg, { type: "warning" });
            return false;
        }
        return true;
    },
});
