/** @odoo-module **/

function showLoginForm() {
    const form = document.querySelector("form.oe_login_form");
    const switcher = document.querySelector("owl-component[name='web.user_switch']");
    if (!form) {
        return;
    }
    const switcherMounted = Boolean(
        switcher && switcher.querySelector(".o_user_switch, .o_user_switch_btn, button")
    );
    if (!switcherMounted) {
        form.classList.remove("d-none");
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showLoginForm);
} else {
    showLoginForm();
}
setTimeout(showLoginForm, 400);
setTimeout(showLoginForm, 2000);
