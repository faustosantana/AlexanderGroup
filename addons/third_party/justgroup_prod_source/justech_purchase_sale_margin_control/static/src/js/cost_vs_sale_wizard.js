/** @odoo-module **/

/**
 * UX-only: make operation filter cards clickable and reflect checkbox state.
 * Does not alter filter fields or backend logic.
 */

function syncJmReportFilterCards(root = document) {
    root.querySelectorAll(".jm_report_filter_card").forEach((card) => {
        const input = card.querySelector('input[type="checkbox"]');
        if (!input) {
            return;
        }
        card.classList.toggle("is-checked", Boolean(input.checked));
    });
}

function onJmReportCardClick(ev) {
    const wizard = ev.target.closest(".jm_cost_vs_sale_wizard");
    if (!wizard) {
        return;
    }

    const checkRow = ev.target.closest(".jm_report_check_row");
    if (checkRow && ev.target.closest("label")) {
        const input = checkRow.querySelector('input[type="checkbox"]');
        if (input && !input.disabled && ev.target !== input) {
            ev.preventDefault();
            input.click();
        }
        return;
    }

    const card = ev.target.closest(".jm_report_filter_card");
    if (!card) {
        return;
    }
    if (ev.target.closest('input[type="checkbox"], a, button')) {
        return;
    }
    const input = card.querySelector('input[type="checkbox"]');
    if (!input || input.disabled) {
        return;
    }
    input.click();
    card.classList.toggle("is-checked", Boolean(input.checked));
}

function onJmReportCardChange(ev) {
    const input = ev.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "checkbox") {
        return;
    }
    const card = input.closest(".jm_report_filter_card");
    if (!card) {
        return;
    }
    card.classList.toggle("is-checked", Boolean(input.checked));
}

document.addEventListener("click", onJmReportCardClick, true);
document.addEventListener("change", onJmReportCardChange, true);

const _observer = new MutationObserver(() => {
    if (document.querySelector(".jm_cost_vs_sale_wizard")) {
        syncJmReportFilterCards();
    }
});
_observer.observe(document.documentElement, { childList: true, subtree: true });

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => syncJmReportFilterCards());
} else {
    syncJmReportFilterCards();
}
