/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import "@web/webclient/switch_company_menu/switch_company_menu";

const systray = registry.category("systray");
if (systray.contains("SwitchCompanyMenu")) {
    systray.remove("SwitchCompanyMenu");
}

function isTechnicalCompany(company) {
    const name = (company.name || "").toLowerCase();
    return name.includes("plantilla técnica") || name.includes("plantilla tecnica");
}

function operationalCompanies() {
    return (user.allowedCompanies || []).filter((company) => !isTechnicalCompany(company));
}

const companies = operationalCompanies();
if (companies.length > 1) {
    registry.category("user_menuitems").add(
        "dx_company_sep",
        () => ({
            type: "separator",
            sequence: 4,
        }),
        { force: true }
    );
    companies.forEach((company, index) => {
        registry.category("user_menuitems").add(
            `dx_company_${company.id}`,
            () => {
                const active = user.activeCompany && user.activeCompany.id === company.id;
                return {
                    type: "item",
                    id: `dx_company_${company.id}`,
                    description: active ? _t("%s (actual)", company.name) : company.name,
                    callback: () => {
                        user.activateCompanies([company.id], {
                            includeChildCompanies: false,
                            reload: true,
                        });
                    },
                    sequence: 4.01 + index / 100,
                };
            },
            { force: true }
        );
    });
}
