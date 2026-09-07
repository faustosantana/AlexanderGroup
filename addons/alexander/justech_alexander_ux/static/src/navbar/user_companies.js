/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SwitchCompanyMenu } from "@web/webclient/switch_company_menu/switch_company_menu";

function isTechnicalCompany(company) {
    const name = (company?.name || "").toLowerCase();
    return name.includes("plantilla técnica") || name.includes("plantilla tecnica");
}

patch(SwitchCompanyMenu.prototype, {
    computeVisibleCompanies() {
        return super
            .computeVisibleCompanies()
            .filter((entry) => !isTechnicalCompany(entry.company));
    },
});
